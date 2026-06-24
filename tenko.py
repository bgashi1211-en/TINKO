import os
import random
import subprocess
import threading
import time
from pathlib import Path
import gdown

TMP = Path("/tmp/rain")
TMP.mkdir(parents=True, exist_ok=True)

SCENE_FOLDER  = "1ZZw4iNgd8VOoIpko_qSQZK5nakH2_FEu"
BREEZE_FOLDER = "1L67IkEkItNkkkB2k1QJctimw5zIBjU7W"
BIRDS_FOLDER  = "1giqnOS32SeedqFB93Xh872BrfOW-oIVH"

MIN_SIZE_BYTES    = 1_000_000_000
MAX_SIZE_BYTES    = int(1.99 * 1024 ** 3)
TARGET_SIZE_BYTES = random.randint(int(1.05 * 1024 ** 3), int(1.93 * 1024 ** 3))
DURATION          = random.randint(18000, 28800)
AUDIO_BITRATE_K   = 128
VIDEO_BITRATE_K   = int((TARGET_SIZE_BYTES * 8) / DURATION / 1000)

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm"}
AUDIO_EXT = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}

TARGET_SCENE_NAME = os.environ.get("TARGET_SCENE_NAME", "").strip()
if not TARGET_SCENE_NAME:
    raise SystemExit("[FATAL] TARGET_SCENE_NAME env var not set.")


def run_with_timeout(fn, timeout_sec=1800, label="operation"):
    result = [None]; error = [None]
    def worker():
        try: result[0] = fn()
        except Exception as e: error[0] = e
    t = threading.Thread(target=worker, daemon=True)
    t.start(); t.join(timeout_sec)
    if t.is_alive():
        raise TimeoutError(f"[TIMEOUT] {label} exceeded {timeout_sec}s")
    if error[0]: raise error[0]
    return result[0]


def dl_folder(folder_id, dest_dir, label, retries=3, timeout=900):
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            print(f"[DL] {label} attempt {attempt}/{retries}")
            run_with_timeout(
                lambda: gdown.download_folder(id=folder_id, output=str(dest_dir), quiet=False),
                timeout_sec=timeout, label=label,
            )
            print(f"[OK] {label} downloaded.")
            return
        except Exception as e:
            print(f"[WARN] {label} attempt {attempt} failed: {e}")
            if attempt < retries:
                time.sleep(30 * attempt)
    raise SystemExit(f"[FATAL] Could not download {label}.")


def check_disk(path, min_gb, label="disk check"):
    stat = os.statvfs(str(path))
    free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
    print(f"[DISK] {label}: {free_gb:.1f} GB free")
    if free_gb < min_gb:
        raise SystemExit(f"[FATAL] Need {min_gb} GB, only {free_gb:.1f} GB free.")
    return free_gb


# ── Downloads ──────────────────────────────────────────────────────────────────
check_disk(TMP, 4.0, "before downloads")

scene_dir  = TMP / "scene"
breeze_dir = TMP / "breeze"
birds_dir  = TMP / "birds"

dl_folder(SCENE_FOLDER,  scene_dir,  "scene")
dl_folder(BREEZE_FOLDER, breeze_dir, "breeze")
dl_folder(BIRDS_FOLDER,  birds_dir,  "birds")

# ── Locate scene ───────────────────────────────────────────────────────────────
matches = list(scene_dir.rglob(TARGET_SCENE_NAME))
if not matches:
    raise SystemExit(f"[FATAL] {TARGET_SCENE_NAME} not found in scene folder.")
scene_path = matches[0]

# Sanitize filename
safe_name = "".join(c if c.isalnum() or c in "._-" else "_" for c in scene_path.name)
safe_path = scene_path.parent / safe_name
if safe_name != scene_path.name:
    scene_path.rename(safe_path)
    scene_path = safe_path
    print(f"[OK] Renamed scene to: {scene_path.name}")

scene_ext = scene_path.suffix.lower()
is_image  = scene_ext in IMAGE_EXT
is_video  = scene_ext in VIDEO_EXT
if not is_image and not is_video:
    raise SystemExit(f"[FATAL] Unsupported file type: {scene_ext}")
print(f"[OK] Scene: {scene_path.name} ({'image' if is_image else 'video'})")

# ── Locate breeze audio ────────────────────────────────────────────────────────
breeze_files = sorted(p for p in breeze_dir.rglob("*") if p.suffix.lower() in AUDIO_EXT and p.is_file())
if not breeze_files:
    raise SystemExit("[FATAL] No audio found in breeze folder.")
breeze_path = breeze_files[0]
print(f"[OK] Breeze: {breeze_path.name} @ 22%")

# ── Locate bird tracks ─────────────────────────────────────────────────────────
bird1 = next(iter(birds_dir.rglob("1.mp3")), None)
bird2 = next(iter(birds_dir.rglob("2.mp3")), None)
if not bird1:
    raise SystemExit("[FATAL] 1.mp3 not found in birds folder.")
if not bird2:
    raise SystemExit("[FATAL] 2.mp3 not found in birds folder.")
print(f"[OK] Bird1: {bird1.name} @ 80%  |  Bird2: {bird2.name} @ 53%")

check_disk(TMP, 2.0, "after downloads")

output_path = TMP / f"OUT_{scene_path.stem}.mp4"

print(f"""
=== RENDER JOB ===
  SCENE        : {scene_path.name} ({'image' if is_image else 'video'})
  BREEZE       : {breeze_path.name} @ 22%
  BIRD1        : {bird1.name} @ 80%
  BIRD2        : {bird2.name} @ 53%
  DURATION     : {DURATION}s ({DURATION//3600}h {(DURATION%3600)//60}m)
  TARGET SIZE  : {TARGET_SIZE_BYTES / 1e9:.2f} GB
  VIDEO BITRATE: {VIDEO_BITRATE_K}k
""")

# ── FFmpeg inputs ──────────────────────────────────────────────────────────────
if is_image:
    scene_args = ["-loop", "1", "-framerate", "1", "-i", str(scene_path)]
else:
    scene_args = ["-stream_loop", "-1", "-i", str(scene_path)]

# input 0 = scene, 1 = bird1, 2 = bird2, 3 = breeze
filter_complex = (
    "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p[outv];"
    "[1:a]volume=0.80[b1];"
    "[2:a]volume=0.53[b2];"
    "[3:a]volume=0.22[bz];"
    "[b1][b2][bz]amix=inputs=3:duration=longest:normalize=0[outa]"
)

cmd = [
    "ffmpeg", "-y", "-hide_banner", "-fflags", "+genpts",
    *scene_args,
    "-stream_loop", "-1", "-i", str(bird1),
    "-stream_loop", "-1", "-i", str(bird2),
    "-stream_loop", "-1", "-i", str(breeze_path),
    "-filter_complex", filter_complex,
    "-map", "[outv]",
    "-map", "[outa]",
    "-t", str(DURATION),
    "-c:v", "libx264",
    "-preset", "ultrafast",
    "-b:v", f"{VIDEO_BITRATE_K}k",
    "-bufsize", f"{VIDEO_BITRATE_K * 2}k",
    "-maxrate", f"{int(VIDEO_BITRATE_K * 1.2)}k",
    "-c:a", "aac",
    "-b:a", f"{AUDIO_BITRATE_K}k",
    "-ar", "44100",
    "-pix_fmt", "yuv420p",
    "-r", "30",
    "-g", "60",
    "-profile:v", "high",
    "-level", "4.1",
    "-movflags", "+faststart",
    str(output_path),
]

print("=== Starting FFmpeg ===")
proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
stopped_by_watcher = False


def size_watcher():
    global stopped_by_watcher
    while proc.poll() is None:
        time.sleep(10)
        if output_path.exists():
            size = output_path.stat().st_size
            print(f"[SIZE] {size/1024**2:.0f} MB  ({size/1024**3:.3f} GB)", flush=True)
            if size >= MAX_SIZE_BYTES:
                print("[SIZE] Reached cap — stopping FFmpeg.", flush=True)
                stopped_by_watcher = True
                proc.terminate()
                try:
                    proc.wait(timeout=15)
                except subprocess.TimeoutExpired:
                    proc.kill()
                break


watcher_thread = threading.Thread(target=size_watcher, daemon=True)
watcher_thread.start()

for line in proc.stdout:
    print(line, end="", flush=True)

proc.wait()
watcher_thread.join(timeout=30)

if not stopped_by_watcher and proc.returncode not in (0, -15, 255):
    raise SystemExit(f"[FATAL] FFmpeg exited with code {proc.returncode}")

if not output_path.exists() or output_path.stat().st_size == 0:
    raise SystemExit("[FATAL] Output file missing or empty.")

final_size    = output_path.stat().st_size
final_size_mb = final_size / (1024 ** 2)
final_size_gb = final_size / (1024 ** 3)
stop_reason   = "size cap" if stopped_by_watcher else "duration reached"

if final_size < MIN_SIZE_BYTES:
    raise SystemExit(f"[FATAL] Output only {final_size_gb:.3f} GB — below 1 GB minimum.")

print(f"""
=== RENDER COMPLETE ===
  Output    : {output_path}
  Stop      : {stop_reason}
  Size      : {final_size_mb:.1f} MB ({final_size_gb:.3f} GB)
  OK        : {'YES' if MIN_SIZE_BYTES <= final_size <= MAX_SIZE_BYTES else 'OUT OF RANGE'}
""")

github_output = os.environ.get("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a") as f:
        f.write(f"output_path={output_path}\n")
        f.write(f"scene_name={scene_path.name}\n")
        f.write(f"duration_seconds={DURATION}\n")
        f.write(f"final_size_mb={final_size_mb:.1f}\n")
        f.write(f"stop_reason={stop_reason}\n")
