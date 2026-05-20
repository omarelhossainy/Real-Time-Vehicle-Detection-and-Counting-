import threading

from config import ACTIVE_STREAM as DEFAULT_ACTIVE_STREAM
from config import LINE_PT1 as DEFAULT_LINE_PT1
from config import LINE_PT2 as DEFAULT_LINE_PT2

state_lock = threading.Lock()

ACTIVE_STREAM = DEFAULT_ACTIVE_STREAM
LINE_PT1 = DEFAULT_LINE_PT1
LINE_PT2 = DEFAULT_LINE_PT2

latest_frame = None
latest_raw_frame = None
latest_raw_frame_seq = 0
latest_output_frame_seq = 0
last_processed_frame_id = None
vehicle_count = 0
tracks: dict[int, dict] = {}
next_track_id = 1
flash_frames_remaining = 0
frame_count = 0
current_process = None
processing_thread = None
processing_generation = 0

# Incremented each time a new stream produces its very first processed frame.
# The game JS waits for this value to change before starting the countdown,
# which prevents the timer firing on a stale frame from the previous stream.
frame_seq = 0
