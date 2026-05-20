from config import *  # noqa: F403
from processing import display_stream, generate_frames, switch_stream
from processing import _start_processing_thread
import state
from vision import (  # noqa: F401
    _box_centroid,
    _build_detections,
    _centroid_crossed_line,
    _draw_count,
    _draw_neon_line,
    _draw_track,
    _line_side,
    _update_tracks,
    get_stream_url,
)
from webapp import app


if __name__ == "__main__":
    _start_processing_thread(state.ACTIVE_STREAM)
    app.run(host="127.0.0.1", port=8080, threaded=True)
