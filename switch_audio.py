#!/usr/bin/env python3
import argparse
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime
from pathlib import Path

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".avi", ".m4v", ".webm"}


def which_or_die(tool):
    if shutil.which(tool) is None:
        raise SystemExit(f"Missing required tool: {tool}")


def run(cmd, *, check=True):
    result = subprocess.run(cmd, check=check)
    return result.returncode


def ffprobe_duration(path: Path) -> float:
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-show_entries",
        "format=duration",
        "-of",
        "default=nw=1:nk=1",
        str(path),
    ]
    out = subprocess.check_output(cmd, text=True).strip()
    try:
        return float(out)
    except ValueError:
        raise SystemExit(f"Could not parse duration for {path}: {out}")


def format_duration(seconds: float) -> str:
    total = int(round(seconds))
    hours = total // 3600
    minutes = (total % 3600) // 60
    secs = total % 60
    return f"{hours:02d}:{minutes:02d}:{secs:02d}"


def pick_mp3(audio_dir: Path, mode: str, name: str | None) -> Path | None:
    files = [p for p in audio_dir.glob("*.mp3") if p.is_file()]
    if not files:
        return None
    if mode == "latest":
        return max(files, key=lambda p: p.stat().st_mtime)
    if mode == "oldest":
        return min(files, key=lambda p: p.stat().st_mtime)
    if mode == "name":
        if not name:
            raise SystemExit("--audio-name is required when using --audio-pick name")
        candidate = audio_dir / name
        if candidate.suffix.lower() != ".mp3":
            mp3_candidate = candidate.with_suffix(".mp3")
            if mp3_candidate.exists():
                candidate = mp3_candidate
        if candidate.exists():
            return candidate
        matches = [p for p in files if p.name == name or p.stem == name]
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            names = ", ".join(p.name for p in matches)
            raise SystemExit(f"Multiple matches for --audio-name {name}: {names}")
        raise SystemExit(f"No MP3 found in {audio_dir} named {name}")
    raise SystemExit(f"Unknown audio pick mode: {mode}")


def combine_mp3s(audio_input_dir: Path, output_path: Path) -> None:
    files = sorted(audio_input_dir.glob("*.mp3"))
    if not files:
        raise SystemExit(f"No MP3 files found in {audio_input_dir}")

    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        list_path = Path(tmpdir) / "concat.txt"
        with list_path.open("w", encoding="utf-8") as f:
            for p in files:
                f.write(f"file '{p.as_posix()}'\n")

        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-c:a",
            "libmp3lame",
            "-q:a",
            "2",
            str(output_path),
        ]
        run(cmd)


def build_output_path(video_path: Path, suffix: str, in_place: bool) -> Path:
    if in_place:
        return video_path.with_name(video_path.stem + "_tmp" + video_path.suffix)
    return video_path.with_name(video_path.stem + suffix + video_path.suffix)


def choose_audio_codec_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".webm":
        return "opus"
    if ext in {".mp4", ".mov", ".m4v", ".mkv"}:
        return "aac"
    if ext == ".avi":
        return "mp3"
    return "aac"


def main():
    parser = argparse.ArgumentParser(
        description="Replace video audio track with an MP3 from the audio folder."
    )
    parser.add_argument(
        "--combine",
        action="store_true",
        help="Combine MP3 files from audio-input into audio/combined.mp3 before processing.",
    )
    parser.add_argument(
        "--audio-file",
        type=Path,
        help="Explicit MP3 file to use instead of auto-detecting from audio/.",
    )
    parser.add_argument(
        "--audio-dir",
        type=Path,
        default=Path("audio"),
        help="Directory that contains a single MP3 file (default: audio).",
    )
    parser.add_argument(
        "--audio-pick",
        choices=["latest", "oldest", "name"],
        default="latest",
        help="When multiple MP3 files exist in audio/, choose which to use.",
    )
    parser.add_argument(
        "--audio-name",
        help="MP3 filename to use when --audio-pick name (extension optional).",
    )
    parser.add_argument(
        "--audio-input-dir",
        type=Path,
        default=Path("audio-input"),
        help="Directory with MP3 files to combine when using --combine (default: audio-input).",
    )
    parser.add_argument(
        "--video-dir",
        type=Path,
        default=Path("video"),
        help="Directory with video files to process (default: video).",
    )
    parser.add_argument(
        "--audio-codec",
        default=None,
        help="Audio codec for output (default: auto by container).",
    )
    parser.add_argument(
        "--suffix",
        default="_newaudio",
        help="Suffix for output files when not using --in-place (default: _newaudio).",
    )
    parser.add_argument(
        "--in-place",
        action="store_true",
        help="Overwrite video files in place (uses a temporary file then replaces).",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Overwrite existing output files.",
    )
    parser.add_argument(
        "--list-audio-lengths",
        action="store_true",
        help="List durations of MP3 files in the audio directory and exit.",
    )

    args = parser.parse_args()

    which_or_die("ffmpeg")
    which_or_die("ffprobe")

    if args.list_audio_lengths:
        audio_files = sorted([p for p in args.audio_dir.glob("*.mp3") if p.is_file()])
        if not audio_files:
            print(f"No MP3 files found in {args.audio_dir}")
            return
        total = 0.0
        for p in audio_files:
            duration = ffprobe_duration(p)
            total += duration
            print(f"{p.name}: {format_duration(duration)} ({duration:.2f}s)")
        print(f"Total: {format_duration(total)} ({total:.2f}s)")
        return

    if args.audio_file:
        audio_path = args.audio_file
    else:
        audio_path = pick_mp3(args.audio_dir, args.audio_pick, args.audio_name)
        if args.combine or audio_path is None:
            ts = datetime.now().strftime("%Y.%m.%d-%H.%M.%S")
            combined = args.audio_dir / f"{ts}.mp3"
            combine_mp3s(args.audio_input_dir, combined)
            audio_path = combined

    if not audio_path.exists():
        raise SystemExit(f"Audio file not found: {audio_path}")

    video_dir = args.video_dir
    if not video_dir.exists():
        raise SystemExit(f"Video directory not found: {video_dir}")

    videos = [p for p in sorted(video_dir.iterdir()) if p.suffix.lower() in VIDEO_EXTS]
    if not videos:
        raise SystemExit(f"No video files found in {video_dir}")

    audio_duration = ffprobe_duration(audio_path)

    failures = []
    for video_path in videos:
        try:
            video_duration = ffprobe_duration(video_path)
            use_shortest = audio_duration > (video_duration + 0.01)

            output_path = build_output_path(video_path, args.suffix, args.in_place)
            if output_path.exists() and not args.overwrite:
                raise RuntimeError(f"Output exists: {output_path} (use --overwrite)")

            audio_codec = args.audio_codec or choose_audio_codec_for_path(output_path)

            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-stats",
                "-i",
                str(video_path),
                "-i",
                str(audio_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                audio_codec,
            ]
            if use_shortest:
                cmd.append("-shortest")
            if args.overwrite or args.in_place:
                cmd.insert(1, "-y")
            cmd.append(str(output_path))

            run(cmd)

            if args.in_place:
                os.replace(output_path, video_path)
        except Exception as exc:
            failures.append((video_path, str(exc)))
            print(f"Failed: {video_path} ({exc})")

    if failures:
        raise SystemExit(f"{len(failures)} video(s) failed")


if __name__ == "__main__":
    main()
