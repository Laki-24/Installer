import sys
import subprocess
from pathlib import Path

# Paths
FFMPEG_BIN_PATH = r"C:\ffmpeg\bin"
URLS_FILE = "urls.txt"
OUTPUT_DIR = Path("mp3_output")

# Ensure the output directory exists
OUTPUT_DIR.mkdir(exist_ok=True)

# Build the yt-dlp command
command = [
    sys.executable, "-m", "yt_dlp",
    "--ffmpeg-location", FFMPEG_BIN_PATH,
    "-x",                                     # Extract audio only
    "--audio-format", "mp3",                   # Convert to MP3
    "--audio-quality", "0",                    # 0 = Best VBR quality (~250-320 kbps)
    "-a", URLS_FILE,                           # Read URLs from urls.txt
    "-o", str(OUTPUT_DIR / "%(title)s.%(ext)s"), # Output filename template
    "--no-overwrites",                         # Don't re-download if file already exists
    "--ignore-errors"                          # Continue downloading rest if one fails
]

print("Starting audio download and conversion...")
subprocess.run(command)
print("\nDone! Check the 'mp3_output' folder.")