import cv2
import numpy as np

from config import (
    BOX_COLOR,
    CENTROID_COLOR,
    CROSSING_PADDING,
    DENO_PATH,
    PANEL_COLOR,
    TEXT_COLOR,
    TRACK_MAX_DISTANCE,
    TRACK_MAX_MISSED,
)


def get_stream_url(youtube_url: str) -> tuple[str, str]:
    try:
        import yt_dlp
    except ImportError as exc:
        raise RuntimeError(
            "yt_dlp is required for YouTube streams. Install it with `pip install yt-dlp`."
        ) from exc

    ydl_opts = {
        'format': 'best[height<=720]/best',
        'quiet': True,
        'no_warnings': True,
        'skip_download': True,
        'noplaylist': True,
        'extractor_args': {'youtube': {'js_runtimes': [f'deno:{DENO_PATH}']}},
    }
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(youtube_url, download=False)

    if 'entries' in info:
        info = next((entry for entry in info['entries'] if entry), None)

    if not info:
        raise RuntimeError(f'Could not resolve YouTube stream for: {youtube_url}')

    user_agent = info.get('http_headers', {}).get('User-Agent', '')

    direct_url = info.get('url')
    if direct_url:
        return direct_url, user_agent

    formats = [fmt for fmt in info.get('formats', []) if fmt.get('url')]
    formats.sort(
        key=lambda fmt: (
            fmt.get('height') or 0,
            fmt.get('tbr') or 0,
        ),
        reverse=True,
    )

    if not formats:
        raise RuntimeError(f'No playable YouTube stream found for: {youtube_url}')

    selected_format = formats[0]
    user_agent = selected_format.get('http_headers', {}).get('User-Agent', user_agent)
    return selected_format['url'], user_agent


# ---------------------------------------------------------------------------
# Animated neon sine-wave line
# ---------------------------------------------------------------------------

def _generate_sine_wave_points(pt1, pt2, num_points, amplitude, frequency, phase):
    """Return OpenCV polyline points forming a sine wave between two endpoints."""
    x1, y1 = pt1
    x2, y2 = pt2

    t = np.linspace(0.0, 1.0, num_points)

    dx, dy = float(x2 - x1), float(y2 - y1)
    length = np.hypot(dx, dy) + 1e-9
    tx, ty = dx / length, dy / length
    nx, ny = -ty, tx

    sine = amplitude * np.sin(2.0 * np.pi * frequency * t + phase)

    xs = x1 + t * dx + sine * nx
    ys = y1 + t * dy + sine * ny

    return np.stack([xs, ys], axis=1).astype(np.int32).reshape(-1, 1, 2)


def _draw_neon_line(frame, pts, flash_active):
    """Draw a layered glowing line on the frame in-place."""
    if flash_active:
        color_outer = (255, 255, 255)
        color_mid = (255, 255, 255)
        color_core = (255, 255, 255)
    else:
        color_outer = (255, 190, 0)
        color_mid = (255, 225, 35)
        color_core = (255, 255, 210)

    overlay = np.zeros_like(frame)

    cv2.polylines(
        overlay, [pts], isClosed=False, color=color_outer, thickness=10, lineType=cv2.LINE_AA
    )
    cv2.addWeighted(overlay, 0.14, frame, 1.0, 0, frame)

    overlay[:] = 0
    cv2.polylines(
        overlay, [pts], isClosed=False, color=color_mid, thickness=4, lineType=cv2.LINE_AA
    )
    cv2.addWeighted(overlay, 0.42, frame, 1.0, 0, frame)

    cv2.polylines(frame, [pts], isClosed=False, color=color_core, thickness=2, lineType=cv2.LINE_AA)


# ---------------------------------------------------------------------------
# Centroid tracking and line-crossing detection
# ---------------------------------------------------------------------------

def _box_centroid(box):
    x1, y1, x2, y2 = box
    return int((x1 + x2) / 2), int((y1 + y2) / 2)


def _line_side(point, pt1, pt2):
    px, py = point
    x1, y1 = pt1
    x2, y2 = pt2
    return (px - x1) * (y2 - y1) - (py - y1) * (x2 - x1)


def _point_on_line_segment(point, pt1, pt2, padding=CROSSING_PADDING):
    px, py = point
    x1, y1 = pt1
    x2, y2 = pt2
    dx = x2 - x1
    dy = y2 - y1
    length_sq = dx * dx + dy * dy

    if length_sq == 0:
        return False

    projection = ((px - x1) * dx + (py - y1) * dy) / length_sq
    min_projection = -padding / np.sqrt(length_sq)
    max_projection = 1.0 + padding / np.sqrt(length_sq)
    return min_projection <= projection <= max_projection


def _centroid_crossed_line(previous, current, pt1, pt2):
    if previous is None or current is None:
        return False

    prev_side = _line_side(previous, pt1, pt2)
    curr_side = _line_side(current, pt1, pt2)

    if prev_side == 0 or curr_side == 0:
        side_changed = prev_side != curr_side
    else:
        side_changed = (prev_side < 0 < curr_side) or (prev_side > 0 > curr_side)

    if not side_changed:
        return False

    denom = prev_side - curr_side
    if denom == 0:
        crossing_point = current
    else:
        ratio = prev_side / denom
        crossing_point = (
            previous[0] + ratio * (current[0] - previous[0]),
            previous[1] + ratio * (current[1] - previous[1]),
        )

    return _point_on_line_segment(crossing_point, pt1, pt2)


def _build_detections(result, model):
    boxes = result.boxes.xyxy.cpu().numpy()
    confidences = result.boxes.conf.cpu().numpy()
    class_ids = result.boxes.cls.cpu().numpy().astype(int)
    names = model.names

    detections = []
    for box, confidence, class_id in zip(boxes, confidences, class_ids):
        if hasattr(names, "get"):
            label = names.get(class_id, str(class_id))
        elif 0 <= class_id < len(names):
            label = names[class_id]
        else:
            label = str(class_id)

        detections.append({
            "box": box,
            "centroid": _box_centroid(box),
            "confidence": float(confidence),
            "label": label,
        })
    return detections


def _update_tracks(tracks, detections, next_track_id):
    for track in tracks.values():
        track["missed"] += 1
        track["updated"] = False

    pairs = []
    for track_id, track in tracks.items():
        for det_index, detection in enumerate(detections):
            distance = np.hypot(
                track["centroid"][0] - detection["centroid"][0],
                track["centroid"][1] - detection["centroid"][1],
            )
            pairs.append((distance, track_id, det_index))

    matched_tracks = set()
    matched_detections = set()

    for distance, track_id, det_index in sorted(pairs, key=lambda item: item[0]):
        if distance > TRACK_MAX_DISTANCE:
            break
        if track_id in matched_tracks or det_index in matched_detections:
            continue

        detection = detections[det_index]
        track = tracks[track_id]
        track["previous_centroid"] = track["centroid"]
        track["centroid"] = detection["centroid"]
        track["box"] = detection["box"]
        track["confidence"] = detection["confidence"]
        track["label"] = detection["label"]
        track["missed"] = 0
        track["updated"] = True
        matched_tracks.add(track_id)
        matched_detections.add(det_index)

    for det_index, detection in enumerate(detections):
        if det_index in matched_detections:
            continue

        tracks[next_track_id] = {
            "box": detection["box"],
            "centroid": detection["centroid"],
            "previous_centroid": None,
            "confidence": detection["confidence"],
            "label": detection["label"],
            "missed": 0,
            "updated": True,
            "counted": False,
        }
        next_track_id += 1

    expired_tracks = [
        track_id
        for track_id, track in tracks.items()
        if track["missed"] > TRACK_MAX_MISSED
    ]
    for track_id in expired_tracks:
        del tracks[track_id]

    return next_track_id


def _draw_track(frame, track_id, track):
    x1, y1, x2, y2 = track["box"].astype(int)
    cx, cy = track["centroid"]
    label = f"#{track_id} {track['label']} {track['confidence']:.2f}"

    cv2.rectangle(frame, (x1, y1), (x2, y2), BOX_COLOR, 1, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), 4, CENTROID_COLOR, -1, cv2.LINE_AA)
    cv2.circle(frame, (cx, cy), 8, TEXT_COLOR, 1, cv2.LINE_AA)

    (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.48, 1)
    label_y = max(18, y1 - 8)
    cv2.rectangle(frame, (x1, label_y - th - 8), (x1 + tw + 10, label_y + 4), PANEL_COLOR, -1)
    cv2.putText(frame, label, (x1 + 5, label_y - 2), cv2.FONT_HERSHEY_SIMPLEX, 0.48, TEXT_COLOR, 1, cv2.LINE_AA)


def _draw_count(frame, count, fps=None):
    """Draw the vehicle count and frame rate in the top-right corner."""
    label = "VEHICLES"
    text = str(count)
    fps_text = "FPS --" if fps is None else f"FPS {fps:.1f}"
    font = cv2.FONT_HERSHEY_SIMPLEX
    x = frame.shape[1] - 220
    y = 24

    overlay = frame.copy()
    cv2.rectangle(overlay, (x, y), (x + 190, y + 124), PANEL_COLOR, -1)
    cv2.addWeighted(overlay, 0.78, frame, 0.22, 0, frame)
    cv2.rectangle(frame, (x, y), (x + 190, y + 124), (255, 225, 35), 1, cv2.LINE_AA)
    cv2.putText(frame, label, (x + 18, y + 28), font, 0.55, (185, 200, 210), 1, cv2.LINE_AA)
    cv2.putText(frame, text, (x + 18, y + 76), font, 1.55, TEXT_COLOR, 2, cv2.LINE_AA)
    cv2.putText(frame, fps_text, (x + 18, y + 108), font, 0.62, (185, 200, 210), 1, cv2.LINE_AA)
