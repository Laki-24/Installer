# Repository Guidelines

## Project Structure & Module Organization

- `app.py` is the Tkinter UI; `downloader.py` runs the per-item yt-dlp pipeline and `history.py` tracks playlist results by URL and format.
- `metadata.py` defines the shared media and music metadata models and normalizes yt-dlp JSON without coupling fields to MP3 or MP4.
- `mp3_writer.py` and `mp4_writer.py` map that model to container-specific tags. `requirements.txt` lists runtime Python dependencies.
- `playlist_urls.py` is a command-line utility that reads `playlist.txt` and appends unique entries to `urls.txt`.
- `download_audio.py` downloads the URLs in `urls.txt` as MP3 files.
- `AudioArchiver.spec` and `app_icon.ico` configure the Windows executable. Do not version generated `build/`, `dist/`, `App_Data/`, or downloads.

## Build, Test, and Development Commands

Use Python 3 and install the required download tools in your active environment:

```powershell
python -m pip install -r requirements.txt pyinstaller
python app.py
python playlist_urls.py
python download_audio.py
pyinstaller AudioArchiver.spec
```

`app.py` launches the GUI. The next two commands run the legacy playlist and download workflows. The final command creates the Windows executable in `dist/`. FFmpeg must be available at the path configured by `download_audio.py`; the GUI fetches its own copy on first run.

## Coding Style & Naming Conventions

Follow the existing Python style: four-space indentation, `snake_case` for variables and functions, `UPPER_SNAKE_CASE` for module constants, and `PascalCase` for classes such as `AudioDownloaderApp`. Keep filesystem paths as `pathlib.Path` objects where practical. Use clear status/error messages because these scripts are user-facing. Avoid adding secrets, personal URLs, or machine-specific paths to source files.

## Testing Guidelines

Tests use built-in `unittest`. Before submitting changes, run syntax checks, metadata tests, and exercise the affected workflow manually:

```powershell
python -m py_compile app.py downloader.py history.py metadata.py mp3_writer.py mp4_writer.py
python -m unittest discover -s tests
python app.py
```

For download-related changes, use media you are authorized to access and verify duplicate URL handling plus output-folder behavior. Add focused `unittest` tests in a new `tests/` directory when introducing logic that can be separated from the GUI or subprocess calls.

## Commit & Pull Request Guidelines

The history currently contains a short imperative subject (`First commit, just the playlist to mp3`). Continue with concise, imperative commit titles, for example `Add playlist URL validation`. Keep commits scoped to one change.

Pull requests should explain the user-visible impact, list manual verification performed, and link relevant issues. Include screenshots for GUI changes and call out any new external dependency, download source, or configuration requirement.
