# AudioSwitcher

Replace the audio track of a single long video with MP3 audio using ffmpeg. Video is copied without re-encoding.

## Requirements

- Python 3
- ffmpeg (includes ffprobe)

## Folders

- `video/` contains the video(s) to process
- `audio/` contains the MP3 to use
- `audio-input/` contains MP3s to combine if `audio/` is empty

## Usage

```bash
./switch_audio.py
```

Common options:

- `--list-audio-lengths` list durations of MP3 files in `audio/`
- `--list-audio-input-lengths` list durations of MP3 files in `audio-input/`
- `--list-audio-sort name|date` sort order for `--list-audio-lengths`
- `--combine-only` combine `audio-input/` into a single MP3 in `audio/` and exit
- `--shuffle-audio-input` randomize MP3 order when combining from `audio-input/`
- `--audio-file /path/to/file.mp3` use a specific MP3
- `--audio-pick latest|oldest|name` choose which MP3 to use when multiple exist
- `--audio-name myfile.mp3` used with `--audio-pick name` (extension optional)
- `--video-input /path/to/video.mp4` use a single video file instead of the `video/` folder
- `--in-place` replace the video file after successful export

Behavior:

- If `audio/` has multiple MP3s, the newest is used.
- If `audio/` has no MP3s, MP3s from `audio-input/` are combined and saved to `audio/YYYY.MM.DD-HH.MM.SS.mp3`.
- When combining, a tracklist text file is written next to the combined MP3 with start times per song (filename extensions are omitted; leading two-digit prefixes like `01 ` are stripped).
- With `--shuffle-audio-input`, MP3s that start with two digits are kept first in numeric order, and the remaining files are shuffled randomly.
  Naming examples for fixed order: `00 Intro.mp3`, `01 Theme.mp3`, `02 Outro.mp3` (two digits + space/underscore/dash).
  Naming examples for shuffled items: `Song A.mp3`, `My Track.mp3` (no two-digit prefix).
- If audio is longer than the video, it is trimmed to the video length.
- If audio is shorter than the video, it loops from the start to fill the full video length.
- Audio codec is chosen automatically based on container unless `--audio-codec` is set (`.webm` -> `opus`, `.mp4/.mov/.m4v/.mkv` -> `aac`, `.avi` -> `mp3`).
- If multiple videos are present, failures are reported and processing continues for the rest.

## Examples

```bash
# Combine automatically (when audio/ is empty) and replace audio
./switch_audio.py

# Show MP3 durations in audio/
./switch_audio.py --list-audio-lengths

# Only combine MP3s in audio-input/ into audio/
./switch_audio.py --combine-only

# Combine with shuffle, but keep two-digit prefixes first (00, 01, ...)
./switch_audio.py --combine --shuffle-audio-input
```
