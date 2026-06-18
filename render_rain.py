import random
import subprocess
from pathlib import Path
import gdown

# ── Config ────────────────────────────────────────────────────────────────────
TMP             = Path("/tmp/rain")
DURATION        = random.randint(2700, 3600)   # 45–60 min
VIDEO_KBPS      = 2500
AUDIO_BITRATE_K = 128

SONGS_FOLDER  = "1giqnOS32SeedqFB93Xh872BrfOW-oIVH"
IMAGES_FOLDER = "1ZZw4iNgd8VOoIpko_qSQZK5nakH2_FEu"
SUB_FOLDER    = "1mpk5rcZRtVcjrKwrsrSIyfu6TzDWZiTl"

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

images = list((TMP / "images").glob("*.jpg")) + list((TMP / "images").glob("*.png"))
if not images:
    raise SystemExit("No images found.")

subs = list((TMP / "sub").glob("*.mp4")) + list((TMP / "sub").glob("*.mov")) + list((TMP / "sub").glob("*.webm"))
if not subs:
    raise SystemExit("No subscribe button video found.")

song_path   = random.choice(songs)
image_path  = random.choice(images)
sub_path    = subs[0]
output_path = TMP / f"OUT_{image_path.stem}.mp4"

print(f"Using image    : {image_path.name}")
print(f"Using song     : {song_path.name}")
print(f"Using sub btn  : {sub_path.name}")
print(f"Duration       : {DURATION}s ({DURATION//60}m {DURATION%60}s)")

# ── Subscribe overlay timing (every 3 min, shows 4 sec) ──────────────────────
intervals = []
t = 30
while t < DURATION - 10:
    intervals.append(t)
    t += 180

enable_parts = "+".join([f"between(t,{s},{s+4})" for s in intervals])

filter_complex = (
    f"[1:v]scale=220:-1,"
    f"chromakey=0x00ff00:0.3:0.1[sub];"
    f"[0:v][sub]overlay=W-w-30:H-h-30:enable='{enable_parts}',"
    f"format=yuv420p[outv]"
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
result = subprocess.run(cmd)

if result.returncode != 0:
    raise SystemExit("FFmpeg failed — check output above.")

size_mb = output_path.stat().st_size / (1024 * 1024)
print(f"\nDONE — {output_path}")
print(f"Size     : {size_mb:.1f} MB")
print(f"Duration : {DURATION//60}m {DURATION%60}s")
