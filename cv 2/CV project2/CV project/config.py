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
        "line_pt1": (300, 443),
        "line_pt2": (1500, 443),
    },
    "japan": {
        "name": "Shinjuku, Japan",
        "url": "https://www.youtube.com/watch?v=6dp-bvQ7RWo",
        "line_pt1": (510, 718),
        "line_pt2": (990, 248),
    },
    "jackson": {
        "name": "Jackson Hole, Wyoming",
        "url": "https://www.youtube.com/watch?v=1EiC9bvVGnk",
        "line_pt1": (300, 550),
        "line_pt2": (1350, 670),
    },
    "watertown": {
        "name": "Watertown, New York",
        "url": "https://www.youtube.com/watch?v=ttKqOg9w4Ss",
        "line_pt1": (235, 460),
        "line_pt2": (515, 410),
    },
}
ACTIVE_STREAM = "fresno"

# -------- STREAM OUTPUT --------
TARGET_FPS = 15

# -------- COUNTING LINE (tune these for your scene) --------
LINE_PT1 = STREAMS[ACTIVE_STREAM]["line_pt1"]
LINE_PT2 = STREAMS[ACTIVE_STREAM]["line_pt2"]

# -------- LINE VISUAL PARAMETERS --------
LINE_FLASH_DURATION = 15      # frames the line stays white after a crossing
LINE_NUM_POINTS = 96          # resolution of the animated sine-wave line
LINE_FREQUENCY = 2.0          # number of sine cycles along the counting line
LINE_WAVE_AMPLITUDE = 7       # wave height in pixels
LINE_PHASE_STEP = 0.34        # animation speed per processed frame

# -------- CENTROID TRACKER PARAMETERS --------
TRACK_MAX_DISTANCE = 160      # max centroid jump allowed between frames (increased for lower FPS)
TRACK_MAX_MISSED = 12         # frames before an unmatched track is dropped
CROSSING_PADDING = 24         # line-end tolerance for centroid crossing

# -------- UI COLORS (BGR) --------
BOX_COLOR = (42, 220, 255)
CENTROID_COLOR = (255, 80, 80)
TEXT_COLOR = (245, 248, 255)
PANEL_COLOR = (18, 22, 28)
