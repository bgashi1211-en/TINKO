import os
import random
import subprocess
import threading
import time
from pathlib import Path
import gdown

# ── Config ─────────────────────────────────────────────────────────────────────
TMP = Path("/tmp/rain")
TMP.mkdir(parents=True, exist_ok=True)

_F1 = "1ZZw4iNgd8VOoIpko_qSQZK5nakH2_FEu"  # scene
_F2 = "1giqnOS32SeedqFB93Xh872BrfOW-oIVH"  # birds
_F3 = "1L67IkEkItNkkkB2k1QJctimw5zIBjU7W"  # breeze
_F4 = "1n-tXny5mhhYmeWEnZl_xi2aXWHnSAqGw"  # sub

AUDIO_BITRATE_K   = 128
MIN_SIZE_BYTES    = 1_000_000_000
MAX_SIZE_BYTES    = int(1.99 * 1024 ** 3)
TARGET_SIZE_BYTES = random.randint(
    int(1.05 * 1024 ** 3),
    int(1.93 * 1024 ** 3),
)
DURATION        = random.randint(18000, 28800)
VIDEO_BITRATE_K = int((TARGET_SIZE_BYTES * 8) / DURATION / 1000)

TARGET_SCENE_NAME = os.environ.get("TARGET_SCENE_NAME", "").strip()
if not TARGET_SCENE_NAME:
    raise SystemExit("[FATAL] TARGET_SCENE_NAME env var not set.")

IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXT = {".mp4", ".mov", ".webm"}


# ── Helpers ────────────────────────────────────────────────────────────────────
def run_with_timeout(fn, timeout_sec=1800, label="operation"):
    result = [None]
    error  = [None]
    def worker():
        try:
            result[0] = fn()
        except Exception as e:
            error[0] = e
    t = threading.Thread(target=worker, daemon=True)
    t.start()
    t.join(timeout_sec)
    if t.is_alive():
        raise TimeoutError(f"[TIMEOUT] {label} exceeded {timeout_sec}s")
    if error[0]:
        raise error[0]
    return result[0]


def dl_file(file_id, dest, label, retries=3, timeout=600):
    dest = Path(dest)
    if dest.exists() and dest.stat().st_size > 0:
        print(f"[SKIP] {label} already exists ({dest.stat().st_size / 1e6:.1f} MB)")
        return
    for attempt in range(1, retries + 1):
        try:
            print(f"[DL] {label} attempt {attempt}/{retries}")
            run_with_timeout(
                lambda: gdown.download(id=file_id, output=str(dest), quiet=False),
                timeout_sec=timeout, label=label,
            )
            if dest.exists() and dest.stat().st_size > 0:
                print(f"[OK] {label} — {dest.stat().st_size / 1e6:.1f} MB")
                return
            dest.unlink(missing_ok=True)
        except Exception as e:
            print(f"[WARN] {label} attempt {attempt} failed: {e}")
            dest.unlink(missing_ok=True)
            if attempt < retries:
                time.sleep(20 * attempt)
    raise SystemExit(f"[FATAL] Could not download {label}.")


def dl_folder(folder_id, dest_dir, label, retries=3, timeout=1800):
    dest_dir = Path(dest_dir)
    dest_dir.mkdir(parents=True, exist_ok=True)
    for attempt in range(1, retries + 1):
        try:
            print(f"[DL FOLDER] {label} attempt {attempt}/{retries}")
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
    raise SystemExit(f"[FATAL] Could not download folder {label}.")


def probe_duration(path):
    try:
        out = subprocess.check_output([
            "ffprobe", "-v", "error",
            "-show_entries", "format=duration",
            "-of", "default=noprint_wrappers=1:nokey=1",
            str(path),
        ], stderr=subprocess.DEVNULL, text=True).strip()
        return float(out)
    except Exception as e:
        print(f"[WARN] ffprobe failed on {path}: {e} — defaulting to 5s")
        return 5.0


def check_disk(path, min_gb, label="disk check"):
    stat    = os.statvfs(str(path))
    free_gb = (stat.f_bavail * stat.f_frsize) / (1024 ** 3)
    print(f"[DISK] {label}: {free_gb:.1f} GB free")
    if free_gb < min_gb:
        raise SystemExit(f"[FATAL] Need {min_gb} GB, only {free_gb:.1f} GB free.")
    return free_gb


# ── Disk check ─────────────────────────────────────────────────────────────────
check_disk(TMP, 4.0, "before downloads")

# ── Download everything ────────────────────────────────────────────────────────
print("\n=== Downloading scene folder ===")
scene_dir = TMP / "s1"
dl_folder(_F1, scene_dir, label="s1", timeout=900)

print("\n=== Downloading birds folder ===")
birds_dir = TMP / "s2"
dl_folder(_F2, birds_dir, label="s2", timeout=900)

print("\n=== Downloading breeze folder ===")
breeze_dir = TMP / "s3"
dl_folder(_F3, breeze_dir, label="s3", timeout=900)

print("\n=== Downloading sub overlay ===")
sub_path = TMP / "s4.mp4"
dl_file(_F4, sub_path, label="s4")

# ── Locate scene file ──────────────────────────────────────────────────────────
matches = list(scene_dir.rglob(TARGET_SCENE_NAME))
if not matches:
    raise SystemExit(f"[FATAL] {TARGET_SCENE_NAME} not found in scene folder.")
scene_path = matches[0]
scene_ext  = scene_path.suffix.lower()
is_image   = scene_ext in IMAGE_EXT
is_video   = scene_ext in VIDEO_EXT
if not is_image and not is_video:
    raise SystemExit(f"[FATAL] Unsupported file type: {scene_ext}")
print(f"[OK] Scene: {scene_path.name} ({'image' if is_image else 'video'})")

# ── Locate bird tracks ─────────────────────────────────────────────────────────
bird1 = next(iter(birds_dir.rglob("1.mp3")), None)
bird2 = next(iter(birds_dir.rglob("2.mp3")), None)
if not bird1:
    raise SystemExit("[FATAL] 1.mp3 not found in birds folder.")
if not bird2:
    raise SystemExit("[FATAL] 2.mp3 not found in birds folder.")
print(f"[OK] Birds: {bird1.name} (80%) + {bird2.name} (52%)")

# ── Locate breeze clip ─────────────────────────────────────────────────────────
breeze_clips = sorted(p for p in breeze_dir.rglob("*") if p.suffix.lower() in VIDEO_EXT)
if not breeze_clips:
    raise SystemExit("[FATAL] No video found in breeze folder.")
breeze_path = breeze_clips[0]
print(f"[OK] Breeze: {breeze_path.name} (20% vol, looped)")

# ── Probe sub duration ─────────────────────────────────────────────────────────
SUB_DURATION = probe_duration(sub_path)
print(f"[INFO] Sub duration: {SUB_DURATION:.2f}s")

# ── SUB overlay schedule ───────────────────────────────────────────────────────
# Every 5-10 min, unique scale/opacity/position per appearance
sub_appearances = []
t = random.randint(300, 600)
while t < DURATION - SUB_DURATION - 10:
    end_t    = round(t + SUB_DURATION, 2)
    position = random.choice(["bl", "br"])
    scale    = round(random.uniform(0.18, 0.26), 3)
    opacity  = round(random.uniform(0.85, 1.0), 3)
    offset_x = random.randint(20, 50)
    offset_y = random.randint(20, 50)
    sub_appearances.append((t, end_t, position, scale, opacity, offset_x, offset_y))
    t += random.randint(300, 600)

print(f"[INFO] Sub appearances: {len(sub_appearances)}")

# ── Build filter graph ─────────────────────────────────────────────────────────
filter_parts = [
    "[0:v]scale=1920:1080:force_original_aspect_ratio=decrease,"
    "pad=1920:1080:(ow-iw)/2:(oh-ih)/2,fps=30,format=yuv420p[base]"
]

n = len(sub_appearances)

if n == 0:
    filter_parts.append("[base]copy[outv]")
else:
    split_outs = "".join(f"[sc{i}]" for i in range(n))
    filter_parts.append(f"[1:v]split={n}{split_outs}")

    for i, (s, e, pos, scale, opacity, ox, oy) in enumerate(sub_appearances):
        in_label  = "base" if i == 0 else f"v{i-1}"
        out_label = f"v{i}" if i < n - 1 else "outv"
        enable    = f"between(t,{s},{e})"

        filter_parts.append(
            f"[sc{i}]chromakey=0x00FF00:0.25:0.1,"
            f"scale=iw*{scale}:-1,"
            f"colorchannelmixer=aa={opacity}[sk{i}]"
        )

        x = ox if pos == "bl" else f"W-w-{ox}"
        y = f"H-h-{oy}"

        filter_parts.append(
            f"[{in_label}][sk{i}]overlay={x}:{y}:enable='{enable}'[{out_label}]"
        )

# Audio mix
audio_filter = (
    "[2:a]volume=0.80[b1];"
    "[3:a]volume=0.52[b2];"
    "[4:a]volume=0.20[bz];"
    "[b1][b2][bz]amix=inputs=3:duration=longest:normalize=0[outa]"
)

full_filter = ";".join(filter_parts) + ";" + audio_filter

output_path = TMP / f"OUT_{scene_path.stem}.mp4"

print(f"""
=== RENDER JOB ===
  SCENE        : {scene_path.name} ({'image looped' if is_image else 'video looped'})
  BREEZE       : {breeze_path.name} (20% vol, looped)
  BIRDS        : 1.mp3 @ 80% + 2.mp3 @ 52% (looped, mixed)
  DURATION     : {DURATION}s  ({DURATION//3600}h {(DURATION%3600)//60}m)
  TARGET SIZE  : {TARGET_SIZE_BYTES / 1e9:.2f} GB
  HARD CAP     : {MAX_SIZE_BYTES / 1e9:.2f} GB
  VIDEO BITRATE: {VIDEO_BITRATE_K}k
  SUB          : {len(sub_appearances)} appearances, unique each time
""")

check_disk(TMP, 2.0, "after downloads")

# ── FFmpeg ─────────────────────────────────────────────────────────────────────
if is_image:
    scene_args = ["-loop", "1", "-framerate", "1", "-i", str(scene_path)]
else:
    scene_args = ["-stream_loop", "-1", "-i", str(scene_path)]

cmd = [
    "ffmpeg", "-y", "-hide_banner", "-fflags", "+genpts",
    *scene_args,                                            # [0] scene
    "-stream_loop", "-1", "-i", str(sub_path),             # [1] sub
    "-stream_loop", "-1", "-i", str(bird1),                # [2] bird1
    "-stream_loop", "-1", "-i", str(bird2),                # [3] bird2
    "-stream_loop", "-1", "-i", str(breeze_path),          # [4] breeze
    "-filter_complex", full_filter,
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
            mb   = size / (1024 ** 2)
            gb   = size / (1024 ** 3)
            print(f"[SIZE] {mb:.0f} MB  ({gb:.3f} GB)", flush=True)
            if size >= MAX_SIZE_BYTES:
                print("[SIZE] Reached 1.99 GB cap — stopping FFmpeg.", flush=True)
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

# ── Validate ───────────────────────────────────────────────────────────────────
if not stopped_by_watcher and proc.returncode not in (0, 255):
    raise SystemExit(f"[FATAL] FFmpeg exited with code {proc.returncode}")

if not output_path.exists():
    raise SystemExit("[FATAL] Output file does not exist.")

final_size = output_path.stat().st_size
if final_size == 0:
    raise SystemExit("[FATAL] Output file is 0 bytes.")

final_size_mb = final_size / (1024 ** 2)
final_size_gb = final_size / (1024 ** 3)
stop_reason   = "size cap (1.99 GB)" if stopped_by_watcher else "duration reached"

if final_size < MIN_SIZE_BYTES:
    raise SystemExit(f"[FATAL] Output only {final_size_gb:.3f} GB — below 1 GB minimum.")

print(f"""
=== RENDER COMPLETE ===
  Output       : {output_path}
  Stop reason  : {stop_reason}
  Final size   : {final_size_mb:.1f} MB  ({final_size_gb:.3f} GB)
  Size OK      : {'✅ YES' if MIN_SIZE_BYTES <= final_size <= MAX_SIZE_BYTES else '❌ OUT OF RANGE'}
  Bitrate used : {VIDEO_BITRATE_K}k
  Sub overlays : {len(sub_appearances)} (unique scale/pos/opacity each)
  Scene        : {scene_path.name}
""")

# ── GitHub Actions outputs ─────────────────────────────────────────────────────
github_output = os.environ.get("GITHUB_OUTPUT")
if github_output:
    with open(github_output, "a") as f:
        f.write(f"output_path={output_path}\n")
        f.write(f"scene_name={scene_path.name}\n")
        f.write(f"duration_seconds={DURATION}\n")
        f.write(f"final_size_mb={final_size_mb:.1f}\n")
        f.write(f"video_bitrate_k={VIDEO_BITRATE_K}\n")
        f.write(f"stop_reason={stop_reason}\n")
