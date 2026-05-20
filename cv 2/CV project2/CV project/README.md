# Vehicle Detection and Counting Web App

This project runs YOLOv8 on live YouTube traffic cameras, tracks detections across frames using centroid matching, and counts vehicles when a tracked centroid crosses a configured counting line segment.

The UI is a small Flask web app (dark theme) that shows the live processed stream and the current vehicle count. Switching locations restarts the ffmpeg stream and resets the count.

## Web UI + API

Routes:
- `GET /` serves the main HTML UI
- `GET /video_feed` streams processed frames as MJPEG (`multipart/x-mixed-replace`)
- `GET /count` returns JSON: `{"count": X}`
- `POST /switch` accepts JSON: `{"stream_id": "fresno"}` and switches the active stream (resets count/state)
- `POST /shutdown` stops the ffmpeg process and exits the Flask program

Example switch call:

```bash
curl -X POST http://127.0.0.1:8080/switch -H "Content-Type: application/json" -d '{"stream_id":"japan"}'
```

Example shutdown call:

```bash
curl -X POST http://127.0.0.1:8080/shutdown
```

## Stream Configs

Configured in `config.py` under `STREAMS`:
- `fresno` (Fresno, California)
- `japan` (Shinjuku, Japan)
- `jackson` (Jackson Hole, Wyoming)
- `watertown` (Watertown, New York)

Each stream config includes:
- `url` (YouTube watch URL)
- `line_pt1` and `line_pt2` (counting line endpoints in 1280x720 coordinates)

## How It Works

1. `yt-dlp` resolves a direct playable stream URL (`vision.py:get_stream_url()`).
2. `ffmpeg` decodes the stream to a 1280x720 `bgr24` frame pipe (`processing.py`).
3. YOLOv8 runs inference on each frame (vehicle classes only).
4. Detections are tracked using centroid distance matching.
5. The counter increments once per track when the centroid crosses the configured line segment.
6. The latest annotated frame is published to `/video_feed`, and the count is available at `/count`.

## Project Layout

- `extraction.py`: entrypoint that starts the background processing thread and runs Flask on port `8080`
- `webapp.py`: Flask app + routes (`/`, `/video_feed`, `/count`, `/switch`, `/shutdown`)
- `processing.py`: background YOLO + ffmpeg loop, shared state updates, MJPEG frame generator
- `vision.py`: detection parsing, tracking helpers, centroid crossing logic, and drawing helpers
- `state.py`: shared in-memory state (`latest_frame`, `vehicle_count`, tracks, process handle, etc.)
- `config.py`: constants, stream configs, paths, colors, and parameters
- `templates/index.html`: UI template
- `static/styles.css`: UI styling
- `static/app.js`: UI logic (poll count, call `/switch`, call `/shutdown`)
- `yolov8m.pt`: YOLOv8 weights

Dependencies are listed in `requirements.txt`.

## Requirements

Python deps (installed via `requirements.txt`):
- `numpy`, `opencv-python`, `ultralytics`, `yt-dlp`, `Flask`

System deps:
- `ffmpeg`
- `deno` (used by `yt-dlp` for YouTube extraction in this setup)

## Run

1. Activate the venv:

```bash
source venv/bin/activate
```

2. Install Python dependencies:

```bash
pip install -r requirements.txt
```

3. Start the web app:

```bash
python extraction.py
```

Then open `http://127.0.0.1:8080/`.

Note: this project is configured to use port `8080`; you can change it in `extraction.py` if needed.
