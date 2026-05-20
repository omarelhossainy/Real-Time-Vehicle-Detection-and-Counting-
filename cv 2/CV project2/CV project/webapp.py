from flask import Flask, Response, jsonify, render_template, request

import state
from config import STREAMS
from processing import generate_frames, stop_application, switch_stream


app = Flask(__name__)

BUTTON_LABELS = {
    "fresno": "Fresno CA",
    "japan": "Shinjuku Japan",
    "jackson": "Jackson Hole WY",
    "watertown": "Watertown NY",
}


@app.get("/")
def index():
    with state.state_lock:
        active_stream = state.ACTIVE_STREAM

    return render_template(
        "index.html",
        streams=STREAMS,
        button_labels=BUTTON_LABELS,
        active_stream=active_stream,
    )


@app.get("/video_feed")
def video_feed():
    return Response(generate_frames(), mimetype="multipart/x-mixed-replace; boundary=frame")


@app.get("/count")
def count():
    with state.state_lock:
        count_value = state.vehicle_count
    return jsonify({"count": count_value})


@app.get("/count_since")
def count_since():
    """Returns count, stream id, and whether the stream is currently producing frames."""
    with state.state_lock:
        count_value = state.vehicle_count
        stream_id   = state.ACTIVE_STREAM
        is_ready    = state.latest_frame is not None
    return jsonify({"count": count_value, "stream": stream_id, "ready": is_ready})


@app.get("/stream_ready")
def stream_ready():
    """Lightweight poll endpoint — returns ready flag + current frame_seq.
    The JS game waits for the frame_seq to match the one captured at game-start
    so it is never fooled by a stale frame from a previous stream.
    """
    with state.state_lock:
        ready = state.latest_frame is not None
        seq   = state.frame_seq
    return jsonify({"ready": ready, "seq": seq})


@app.get("/game_snapshot")
def game_snapshot():
    """Atomic snapshot of count + stream + frame_seq for the game baseline."""
    with state.state_lock:
        count     = state.vehicle_count
        stream_id = state.ACTIVE_STREAM
        seq       = state.frame_seq
        ready     = state.latest_frame is not None
    return jsonify({"count": count, "stream": stream_id, "seq": seq, "ready": ready})


@app.post("/switch")
def switch():
    data = request.get_json(silent=True) or {}
    stream_id = data.get("stream_id")
    config = switch_stream(stream_id)

    if config is None:
        return jsonify({"error": "Unknown stream"}), 400

    return jsonify({"stream_id": stream_id, "name": config["name"]})


@app.post("/shutdown")
def shutdown():
    stop_application()
    return jsonify({"status": "stopping"})


if __name__ == "__main__":
    # Start the default stream on launch
    from config import ACTIVE_STREAM
    switch_stream(ACTIVE_STREAM)
    
    # Run the Flask app
    app.run(host="127.0.0.1", port=8080, debug=False)
