import subprocess
import sys
from pathlib import Path

# --------------------------------------------------
# FILES
# --------------------------------------------------

playlist_file = Path("playlist.txt")
urls_file = Path("urls.txt")


# --------------------------------------------------
# READ PLAYLIST URL
# --------------------------------------------------

if not playlist_file.exists():
    print("ERROR: playlist.txt was not found.")
    sys.exit()

playlist_url = playlist_file.read_text(encoding="utf-8").strip()

if not playlist_url:
    print("ERROR: playlist.txt is empty.")
    sys.exit()


# --------------------------------------------------
# GET ALL CURRENT PLAYLIST URLs
# --------------------------------------------------

print("Reading playlist...")

result = subprocess.run(
    [
        sys.executable,
        "-m",
        "yt_dlp",
        "--flat-playlist",
        "--print",
        "webpage_url",
        playlist_url
    ],
    capture_output=True,
    text=True,
    encoding="utf-8"
)

if result.returncode != 0:
    print("\nERROR while reading playlist:")
    print(result.stderr)
    sys.exit()


# --------------------------------------------------
# CLEAN PLAYLIST URLS
# --------------------------------------------------

playlist_urls = []

for line in result.stdout.splitlines():

    line = line.strip()

    if line and line not in playlist_urls:
        playlist_urls.append(line)


# --------------------------------------------------
# READ EXISTING URLS
# --------------------------------------------------

existing_urls = []

if urls_file.exists():

    for line in urls_file.read_text(
        encoding="utf-8"
    ).splitlines():

        line = line.strip()

        if line and line not in existing_urls:
            existing_urls.append(line)


# --------------------------------------------------
# FIND NEW URLS
# --------------------------------------------------

new_urls = []

for url in playlist_urls:

    if url not in existing_urls:
        new_urls.append(url)


# --------------------------------------------------
# APPEND NEW URLS
# --------------------------------------------------

if new_urls:

    with urls_file.open(
        "a",
        encoding="utf-8"
    ) as f:

        for url in new_urls:
            f.write(url + "\n")

    print(f"\nAdded {len(new_urls)} new URLs.")

else:

    print("\nNo new URLs found.")


# --------------------------------------------------
# SUMMARY
# --------------------------------------------------

print(f"Total unique URLs stored: {len(existing_urls) + len(new_urls)}")
print(f"Saved in: {urls_file.resolve()}")