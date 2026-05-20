import os
import subprocess
import threading
import time

import cv2
import numpy as np
from ultralytics import YOLO

import state
from config import (
    FFMPEG_PATH,
    LINE_FLASH_DURATION,
    LINE_FREQUENCY,
    LINE_NUM_POINTS,
    LINE_PHASE_STEP,
    LINE_WAVE_AMPLITUDE,
    MODEL_PATH,
    STREAMS,
    TARGET_FPS,
)
from vision import (
    _build_detections,
    _centroid_crossed_line,
    _draw_count,
    _draw_neon_line,
    _draw_track,
    _generate_sine_wave_points,
    _update_tracks,
    get_stream_url,
)


def _reset_counting_state():
    state.latest_frame = None
    state.latest_raw_frame = None
    state.latest_raw_frame_seq = 0
    state.latest_output_frame_seq = 0
    state.last_processed_frame_id = None
    state.vehicle_count = 0
    state.tracks = {}
    state.next_track_id = 1
    state.flash_frames_remaining = 0
    state.frame_count = 0
    state.frame_seq += 1   # new stream → new sequence number


def _ffmpeg_reader_thread(process, generation, frame_size, width, height):
    """Continuously reads frames from ffmpeg stdout and updates the latest raw frame."""
    while True:
        with state.state_lock:
            if generation != state.processing_generation or state.current_process is not process:
                break
        
        try:
            raw_frame = process.stdout.read(frame_size)
            if len(raw_frame) != frame_size:
                break
            
            frame = np.frombuffer(raw_frame, dtype=np.uint8).reshape((height, width, 3))
            
            with state.state_lock:
                state.latest_raw_frame = frame
                state.latest_raw_frame_seq += 1
        except Exception:
            break


def _terminate_process(process):
    if process is None:
        return

    process.terminate()
    try:
        process.wait(timeout=3)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=3)


def _start_processing_thread(stream_id):
    config = STREAMS[stream_id]

    with state.state_lock:
        generation = state.processing_generation

    state.processing_thread = threading.Thread(
        target=display_stream,
        args=(config["url"], stream_id, generation),
        daemon=True,
    )
    state.processing_thread.start()


def switch_stream(stream_id):
    if stream_id not in STREAMS:
        return None

    config = STREAMS[stream_id]

    with state.state_lock:
        state.processing_generation += 1
        process = state.current_process
        state.current_process = None
        state.ACTIVE_STREAM = stream_id
        state.LINE_PT1 = config["line_pt1"]
        state.LINE_PT2 = config["line_pt2"]
        _reset_counting_state()

    _terminate_process(process)
    _start_processing_thread(stream_id)

    return config


def stop_application(exit_process=True):
    with state.state_lock:
        state.processing_generation += 1
        process = state.current_process
        state.current_process = None
        _reset_counting_state()

    _terminate_process(process)

    if exit_process:
        threading.Timer(0.25, lambda: os._exit(0)).start()


def generate_frames():
    last_sent_seq = -1
    frame_interval = 1 / TARGET_FPS

    while True:
        with state.state_lock:
            frame = state.latest_frame.copy() if state.latest_frame is not None else None
            frame_seq = state.latest_output_frame_seq

        if frame is not None and frame_seq != last_sent_seq:
            ret, buffer = cv2.imencode('.jpg', frame)
            if ret:
                last_sent_seq = frame_seq
                yield (b'--frame\r\nContent-Type: image/jpeg\r\n\r\n' + buffer.tobytes() + b'\r\n')
            time.sleep(frame_interval)
        else:
            time.sleep(0.02)


def display_stream(youtube_url: str, stream_id: str | None = None, generation: int = 0):
    print("Loading YOLOv8 model...")
    model = YOLO(MODEL_PATH)

    print("Fetching stream URL...")
    stream_url, user_agent = get_stream_url(youtube_url)
    print("Got stream URL. Starting ffmpeg pipe...")

    with state.state_lock:
        if generation != state.processing_generation:
            return

    width, height = 1280, 720

    ffmpeg_cmd = [
        FFMPEG_PATH,
        '-loglevel', 'quiet',
        '-re',
    ]
    if user_agent:
        ffmpeg_cmd.extend(['-user_agent', user_agent])

    ffmpeg_cmd.extend([
        '-i', stream_url,
        '-r', str(TARGET_FPS),
        '-vf', f'scale={width}:{height}',
        '-f', 'rawvideo',
        '-pix_fmt', 'bgr24',
        '-an',
        'pipe:1'
    ])

    process = subprocess.Popen(ffmpeg_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    with state.state_lock:
        if generation != state.processing_generation:
            _terminate_process(process)
            return

        state.current_process = process
        state.latest_raw_frame = None
        state.latest_raw_frame_seq = 0
        state.latest_output_frame_seq = 0
        state.last_processed_frame_id = None

    frame_size = width * height * 3
    print("Stream started! Press 'q' to quit.")

    reader_thread = threading.Thread(
        target=_ffmpeg_reader_thread,
        args=(process, generation, frame_size, width, height),
        daemon=True
    )
    reader_thread.start()
    measured_fps = None
    last_output_time = None

    try:
        while True:
            with state.state_lock:
                if generation != state.processing_generation:
                    break
                frame = state.latest_raw_frame
                raw_frame_seq = state.latest_raw_frame_seq
                already_processed = raw_frame_seq == state.last_processed_frame_id
                if frame is not None and not already_processed:
                    state.last_processed_frame_id = raw_frame_seq

            if frame is None or already_processed:
                time.sleep(0.01)
                if process.poll() is not None and frame is None:
                    print("Stream ended or connection lost.")
                    break
                continue

            # Run YOLOv8 detection on the frame
            # COCO vehicle class IDs: 2=car, 3=motorcycle, 5=bus, 7=truck
            results = model.predict(source=frame, conf=0.45, classes=[2, 3, 5, 7], imgsz=416, verbose=False, device="cpu")
            detections = _build_detections(results[0], model)

            # ----------------------------------------------------------
            # Centroid tracking and crossing-based vehicle counting
            # ----------------------------------------------------------
            with state.state_lock:
                if generation != state.processing_generation:
                    break

                state.next_track_id = _update_tracks(state.tracks, detections, state.next_track_id)

                for track in state.tracks.values():
                    previous = track["previous_centroid"]
                    current  = track["centroid"]

                    if (
                        track["updated"]
                        and not track["counted"]
                        and _centroid_crossed_line(previous, current, state.LINE_PT1, state.LINE_PT2)
                    ):
                        state.vehicle_count += 1
                        track["counted"] = True
                        state.flash_frames_remaining = LINE_FLASH_DURATION

                # ----------------------------------------------------------
                # Draw the animated neon line
                # ----------------------------------------------------------
                state.frame_count += 1

                flash_active = state.flash_frames_remaining > 0
                frame_count = state.frame_count
                line_pt1 = state.LINE_PT1
                line_pt2 = state.LINE_PT2
                count_value = state.vehicle_count
                tracks_to_draw = [
                    (track_id, track.copy())
                    for track_id, track in state.tracks.items()
                    if track["updated"]
                ]
                if state.flash_frames_remaining > 0:
                    state.flash_frames_remaining -= 1

            annotated_frame = frame.copy()

            for track_id, track in tracks_to_draw:
                _draw_track(annotated_frame, track_id, track)

            phase = frame_count * LINE_PHASE_STEP
            line_pts = _generate_sine_wave_points(
                line_pt1,
                line_pt2,
                LINE_NUM_POINTS,
                LINE_WAVE_AMPLITUDE,
                LINE_FREQUENCY,
                phase,
            )
            _draw_neon_line(annotated_frame, line_pts, flash_active)

            now = time.monotonic()
            if last_output_time is not None:
                elapsed = now - last_output_time
                if elapsed > 0:
                    instant_fps = 1 / elapsed
                    measured_fps = (
                        instant_fps
                        if measured_fps is None
                        else (0.85 * measured_fps) + (0.15 * instant_fps)
                    )
            last_output_time = now

            _draw_count(annotated_frame, count_value, measured_fps or TARGET_FPS)

            with state.state_lock:
                if generation != state.processing_generation:
                    break
                state.latest_frame = annotated_frame
                state.latest_output_frame_seq += 1
    finally:
        with state.state_lock:
            if state.current_process is process:
                state.current_process = None
            count_value = state.vehicle_count

        _terminate_process(process)

    print(f"Stream closed. Total vehicles counted: {count_value}")
