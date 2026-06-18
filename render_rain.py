import random
import subprocess
from pathlib import Path
import gdown

# ── Config ────────────────────────────────────────────────────────────────────
TMP             = Path("/tmp/rain")
DURATION        = random.randint(1800, 3000)   # 30–50 min
VIDEO_KBPS      = 2500
AUDIO_BITRATE_K = 128

SONGS_FOLDER = "1giqnOS32SeedqFB93Xh872BrfOW-oIVH"
IMAGES_FOLDER = "1ZZw4iNgd8VOoIpko_qSQZK5nakH2_FEu"

# ── Setup dirs ────────────────────────────────────────────────────────────────
TMP.mkdir(exist_ok=True)
(TMP / "songs").mkdir(exist_ok=True)
(TMP / "images").mkdir(exist_ok=True)

# ── Download assets ───────────────────────────────────────────────────────────
print("Downloading songs...")
gdown.download_folder(id=SONGS_FOLDER, output=str(TMP / "songs"), quiet=False)

print("Downloading images...")
gdown.download_folder(id=IMAGES_FOLDER, output=str(TMP / "images"), quiet=False)

# ── Pick files ────────────────────────────────────────────────────────────────
songs = list((TMP / "songs").glob("*.mp3"))
if not songs:
    raise SystemExit("No songs found in songs folder.")

images = list((TMP / "images").glob("*.jpg")) + list((TMP / "images").glob("*.png"))
if not images:
    raise SystemExit("No images found in images folder.")

song_path   = random.choice(songs)
image_path  = random.choice(images)
output_path = TMP / f"OUT_{image_path.stem}.mp4"

print(f"Using image : {image_path.name}")
print(f"Using song  : {song_path.name}")
print(f"Duration    : {DURATION}s ({DURATION//60}m {DURATION%60}s)")

# ── FFmpeg ────────────────────────────────────────────────────────────────────
cmd = [
    "ffmpeg", "-y",
    "-loop", "1", "-i", str(image_path),
    "-stream_loop", "-1", "-i", str(song_path),
    "-t", str(DURATION),
    "-c:v", "libx264", "-preset", "ultrafast",
    "-crf", "23",
    "-b:v", f"{VIDEO_KBPS}k", "-maxrate", f"{VIDEO_KBPS}k", "-bufsize", f"{VIDEO_KBPS * 2}k",
    "-profile:v", "high", "-level", "4.1", "-pix_fmt", "yuv420p", "-r", "1", "-g", "2",
    "-c:a", "aac", "-b:a", f"{AUDIO_BITRATE_K}k", "-ar", "44100",
    "-movflags", "+faststart",
    "-shortest",
    str(output_path),
]

print("Running FFmpeg...")
result = subprocess.run(cmd)

if result.returncode != 0:
    raise SystemExit("FFmpeg failed — check output above for details.")

size_mb = output_path.stat().st_size / (1024 * 1024)
print(f"\nDONE — {output_path}")
print(f"Size     : {size_mb:.1f} MB")
print(f"Duration : {DURATION//60}m {DURATION%60}s")
