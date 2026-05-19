import os
import shutil
from pathlib import Path


os.environ['PATH'] = '/opt/homebrew/bin:/usr/local/bin:' + os.environ.get('PATH', '')

FFMPEG_PATH = shutil.which('ffmpeg') or r'C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe'
DENO_PATH = shutil.which('deno') or r'C:\Users\Lenovo\AppData\Local\Microsoft\WinGet\Packages\DenoLand.Deno_Microsoft.Winget.Source_8wekyb3d8bbwe\deno.exe'

MODEL_PATH = str(Path("yolov8n.pt"))

STREAMS = {
    "fresno": {
        "name": "Fresno, California",
        "url": "https://www.youtube.com/watch?v=sTF-6_xinUU",
        # Road-only horizontal line at ~55 % height across active lanes
        "line_pt1": (80, 390),
        "line_pt2": (1200, 390),
    },
    "japan": {
        "name": "Shinjuku, Japan",
        "url": "https://www.youtube.com/watch?v=6dp-bvQ7RWo",
        # Straight horizontal line across the intersection
        "line_pt1": (150, 80),
        "line_pt2": (900, 160),
},
    "jackson": {
        "name": "Jackson Hole, Wyoming",
        "url": "https://www.youtube.com/watch?v=1EiC9bvVGnk",
        # Horizontal across road lanes at mid-frame, avoiding kerb zones
        "line_pt1": (130, 470),
        "line_pt2": (1300, 300),
    },
    "watertown": {
        "name": "Watertown, New York",
        "url": "https://www.youtube.com/watch?v=ttKqOg9w4Ss",
        # Horizontal mid-road, trimmed inward from frame edges
        "line_pt1": (110, 415),
        "line_pt2": (700, 415),
    },
}
ACTIVE_STREAM = "fresno"

# -------- COUNTING LINE (tune these for your scene) --------
LINE_PT1 = STREAMS[ACTIVE_STREAM]["line_pt1"]
LINE_PT2 = STREAMS[ACTIVE_STREAM]["line_pt2"]

# -------- LINE VISUAL PARAMETERS --------
LINE_FLASH_DURATION = 15      # frames the line stays white after a crossing

# -------- CENTROID TRACKER PARAMETERS --------
TRACK_MAX_DISTANCE = 160      # max centroid jump allowed between frames (increased for lower FPS)
TRACK_MAX_MISSED = 12         # frames before an unmatched track is dropped
CROSSING_PADDING = 24         # line-end tolerance for centroid crossing

# -------- UI COLORS (BGR) --------
BOX_COLOR = (42, 220, 255)
CENTROID_COLOR = (255, 80, 80)
TEXT_COLOR = (245, 248, 255)
PANEL_COLOR = (18, 22, 28)
