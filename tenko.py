import os
import random
import subprocess
import threading
import time
import urllib.request
import re
from pathlib import Path
import gdown

# ── Config ────────────────────────────────────────────────────────────────────
TMP             = Path("/tmp/rain")
DURATION        = random.randint(2700, 3600)
VIDEO_KBPS      = 2500
AUDIO_BITRATE_K = 128
MIN_SIZE_BYTES  = int(1.0 * 1024 * 1024 * 1024)
MAX_SIZE_BYTES  = int(1.99 * 1024 * 1024 * 1024)

SONGS_FOLDER  = "1giqnOS32SeedqFB93Xh872BrfOW-oIVH"
IMAGES_FOLDER = "1ZZw4iNgd8VOoIpko_qSQZK5nakH2_FEu"
SUB_FOLDER    = "1mpk5rcZRtVcjrKwrsrSIyfu6TzDWZiTl"

IMAGE_INDEX = int(os.environ["IMAGE_INDEX"])

# ── Setup dirs ────────────────────────────────────────────────────────────────
TMP.mkdir(exist_ok=True)
(TMP / "songs").mkdir(exist_ok=True)
(TMP / "images").mkdir(exist_ok=True)
(TMP / "sub").mkdir(exist_ok=True)

# ── Download assets ───────────────────────────────────────────────────────────
print("Downloading songs...")
gdown.download_folder(id=SONGS_FOLDER, output=str(TMP / "songs"), quiet=False)

print("Downloading images...")
gdown.download_folder(id=IMAGES_FOLDER, output=str(TMP / "images"), quiet=False)

print("Downloading subscribe button...")
gdown.download_folder(id=SUB_FOLDER, output=str(TMP / "sub"), quiet=False)

# ── Pick files ────────────────────────────────────────────────────────────────
songs = list((TMP / "songs").glob("*.mp3")) + list((TMP / "songs").glob("*.wav"))
if not songs:
    raise SystemExit("No songs found.")

images = sorted(
    list((TMP / "images").glob("*.jpg")) +
    list((TMP / "images").glob("*.png"))
)
if not images:
    raise SystemExit("No images found.")

subs = list((TMP / "sub").glob("*.mp4")) + list((TMP / "sub").glob("*.mov")) + list((TMP / "sub").glob("*.webm"))
if not subs:
    raise SystemExit("No subscribe button video found.")

if IMAGE_INDEX >= len(images):
    raise SystemExit(f"IMAGE_INDEX {IMAGE_INDEX} out of range — only {len(images)} images found.")

image_path  = images[IMAGE_INDEX]
song_path   = random.choice(songs)
sub_path    = subs[0]
output_path = TMP / f"OUT_{IMAGE_INDEX}_{image_path.stem}.mp4"

print(f"Using image    : {image_path.name}")
print(f"Using song     : {song_path.name}")
print(f"Using sub btn  : {sub_path.name}")
print(f"Duration       : {DURATION}s ({DURATION//60}m {DURATION%60}s)")

# ── Save image name for summary ───────────────────────────────────────────────
(TMP / f"image_name_{IMAGE_INDEX}.txt").write_text(image_path.name)

# ── Try to get Drive file ID for image preview ────────────────────────────────
try:
    req = urllib.request.Request(
        f"https://drive.google.com/drive/folders/{IMAGES_FOLDER}",
        headers={"User-Agent": "Mozilla/5.0"}
    )
    html = urllib.request.urlopen(req).read().decode("utf-8")
    name_id_matches = re.findall(r'"(1[a-zA-Z0-9_-]{25,})"[^}]*?"([^"]+\.(?:jpg|jpeg|png))"', html, re.IGNORECASE)
    file_id = None
    for fid, fname in name_id_matches:
        if fname.lower() == image_path.name.lower():
            file_id = fid
            break
    if file_id:
        (TMP / f"image_id_{IMAGE_INDEX}.txt").write_text(file_id)
        print(f">>> Drive file ID: {file_id}")
    else:
        print(">>> Could not extract Drive file ID — summary will show filename only")
except Exception as e:
    print(f">>> Drive ID lookup failed: {e}")

# ── Sub overlay length: probe the clip's own duration, let it play in full ───
def get_clip_duration(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        capture_output=True, text=True
    )
    return float(result.stdout.strip())

sub_duration = get_clip_duration(sub_path)
print(f"Sub clip length: {sub_duration:.2f}s — plays in full on each appearance")

# ── Sub overlay timing: appears every 8-14 min, full natural length, random left/right ──
intervals_left  = []
intervals_right = []
t = random.randint(480, 840)
while t < DURATION - 10:
    end_t = t + sub_duration
    if random.random() < 0.5:
        intervals_left.append((t, end_t))
    else:
        intervals_right.append((t, end_t))
    t += random.randint(480, 840)

def make_enable(intervals):
    if not intervals: return "0"
    return "+".join([f"between(t,{s},{e})" for s, e in intervals])

enable_left  = make_enable(intervals_left)
enable_right = make_enable(intervals_right)
print(f"Sub overlay: {len(intervals_left)} left, {len(intervals_right)} right appearances")

filter_complex = (
    f"[1:v]scale=220:-1,chromakey=0x00ff00:0.3:0.1[sub_clean];"
    f"[sub_clean]split[sl][sr];"
    f"[0:v][sl]overlay=30:H-h-30:enable='{enable_left}'[mid];"
    f"[mid][sr]overlay=W-w-30:H-h-30:enable='{enable_right}',format=yuv420p[outv]"
)

# ── FFmpeg ────────────────────────────────────────────────────────────────────
cmd = [
    "ffmpeg", "-y",
    "-loop", "1", "-i", str(image_path),
    "-stream_loop", "-1", "-i", str(sub_path),
    "-stream_loop", "-1", "-i", str(song_path),
    "-t", str(DURATION),
    "-filter_complex", filter_complex,
    "-map", "[outv]",
    "-map", "2:a",
    "-c:v", "libx264", "-preset", "ultrafast",
    "-crf", "23",
    "-b:v", f"{VIDEO_KBPS}k", "-maxrate", f"{VIDEO_KBPS}k", "-bufsize", f"{VIDEO_KBPS * 2}k",
    "-profile:v", "high", "-level", "4.1", "-r", "24", "-g", "48",
    "-c:a", "aac", "-b:a", f"{AUDIO_BITRATE_K}k", "-ar", "44100",
    "-movflags", "+faststart",
    "-shortest",
    str(output_path),
]

print("Running FFmpeg...")
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
stopped_by_watcher = False
under_minimum = False

def size_watcher():
    global stopped_by_watcher
    while proc.poll() is None:
        time.sleep(10)
        if output_path.exists():
            size = output_path.stat().st_size
            mb = size / (1024 * 1024)
            print(f"[SIZE] {mb:.1f} MB", flush=True)
            if size >= MAX_SIZE_BYTES:
                print("[SIZE] Cap reached — stopping.", flush=True)
                stopped_by_watcher = True
                proc.terminate()
                break

watcher = threading.Thread(target=size_watcher, daemon=True)
watcher.start()
for line in proc.stdout:
    print(line, end="", flush=True)
proc.wait()
watcher.join()

if not stopped_by_watcher and proc.returncode != 0:
    raise SystemExit("FFmpeg failed — check output above.")
if not output_path.exists() or output_path.stat().st_size == 0:
    raise SystemExit("No output produced.")

final_size    = output_path.stat().st_size
final_size_mb = final_size / (1024 * 1024)
final_size_gb = final_size / (1024 * 1024 * 1024)

if final_size < MIN_SIZE_BYTES:
    print(f"[SIZE] ⚠️ Under 1 GB ({final_size_gb:.3f} GB).")
    under_minimum = True

stop_reason = "cap reached" if stopped_by_watcher else "duration reached"
print(f"\nDONE — {output_path}")
print(f"Stop     : {stop_reason}")
print(f"Size     : {final_size_mb:.1f} MB ({final_size_gb:.3f} GB)")
print(f"1-2 GB   : {'✅' if MIN_SIZE_BYTES <= final_size <= MAX_SIZE_BYTES else '❌'}")
print(f"Duration : {DURATION//60}m {DURATION%60}s")
print(f"Image    : {image_path.name}")
