#!/usr/bin/env python3
import argparse
import glob
import os
import shutil
import subprocess
import sys
import tempfile
import random
import re
import shlex
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


def sum_durations(files: list[Path]) -> float:
    return sum(ffprobe_duration(p) for p in files)


def list_mp3_files(audio_input_dir: Path) -> list[Path]:
    return [p for p in sorted(audio_input_dir.glob("*.mp3")) if p.is_file()]


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


def order_audio_input_files(audio_input_dir: Path, shuffle: bool) -> list[Path]:
    files = list_mp3_files(audio_input_dir)
    if not files:
        raise SystemExit(f"No MP3 files found in {audio_input_dir}")
    if shuffle:
        prefixed = []
        others = []
        for p in files:
            match = re.match(r"^(\d{2})[\s._-]+", p.stem)
            if match:
                prefixed.append((int(match.group(1)), p.name.lower(), p))
            else:
                others.append(p)
        prefixed = [p for _, _, p in sorted(prefixed)]
        random.shuffle(others)
        files = prefixed + others
    return files


def select_audio_files_for_duration(files: list[Path], target_duration: float | None) -> list[Path]:
    if target_duration is None:
        return files

    selected = []
    total = 0.0
    for p in files:
        selected.append(p)
        total += ffprobe_duration(p)
        if total >= target_duration:
            break
    if total < target_duration:
        print(
            "Warning: audio-input shorter than video target, output audio will loop "
            f"(audio-input {format_duration(total)}, "
            f"video {format_duration(target_duration)})"
        )
    return selected


def combine_mp3_files(files: list[Path], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory() as tmpdir:
        list_path = Path(tmpdir) / "concat.txt"
        with list_path.open("w", encoding="utf-8") as f:
            for p in files:
                f.write(f"file '{p.resolve().as_posix()}'\n")

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


def combine_mp3s(
    audio_input_dir: Path,
    output_path: Path,
    shuffle: bool,
    target_duration: float | None = None,
) -> list[Path]:
    files = order_audio_input_files(audio_input_dir, shuffle)
    files = select_audio_files_for_duration(files, target_duration)
    combine_mp3_files(files, output_path)
    return files


def write_tracklist(
    files: list[Path],
    output_path: Path,
    *,
    video_path: Path | None = None,
    video_duration: float | None = None,
) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    current = 0.0
    audio_duration = sum_durations(files)
    with output_path.open("w", encoding="utf-8") as f:
        if video_path is not None:
            f.write(f"Video: {video_path.name}\n")
        if video_duration is not None:
            f.write(f"Video length: {format_duration(video_duration)}\n")
        f.write(f"Audio length: {format_duration(audio_duration)}\n")
        f.write("\n")
        for p in files:
            display_name = p.stem
            match = re.match(r"^\d{2}[\s._-]+(.+)$", p.stem)
            if match:
                display_name = match.group(1)
            f.write(f"{format_duration(current)} - {display_name}\n")
            current += ffprobe_duration(p)


def create_combined_audio(
    audio_input_dir: Path,
    audio_dir: Path,
    shuffle: bool,
    *,
    output_path: Path | None = None,
    tracklist_path: Path | None = None,
    target_duration: float | None = None,
    video_path: Path | None = None,
) -> Path:
    if not list_mp3_files(audio_input_dir):
        raise SystemExit(f"No MP3 files found in {audio_input_dir}")
    if output_path is None:
        ts = datetime.now().strftime("%Y.%m.%d-%H.%M.%S")
        output_path = audio_dir / f"{ts}.mp3"
    if tracklist_path is None:
        tracklist_path = output_path.with_suffix(".txt")
    combined_files = combine_mp3s(audio_input_dir, output_path, shuffle, target_duration)
    write_tracklist(
        combined_files,
        tracklist_path,
        video_path=video_path,
        video_duration=target_duration,
    )
    return output_path


def has_glob_chars(path: Path) -> bool:
    return any(char in str(path) for char in "*?[")


def resolve_video_inputs(video_inputs: list[Path]) -> list[Path]:
    videos = []
    seen = set()
    for video_input in video_inputs:
        matches = []
        if has_glob_chars(video_input):
            matches = [Path(p) for p in sorted(glob.glob(str(video_input)))]
        elif video_input.is_dir():
            matches = [p for p in sorted(video_input.iterdir()) if p.suffix.lower() in VIDEO_EXTS]
        else:
            matches = [video_input]

        if not matches:
            raise SystemExit(f"No video files matched: {video_input}")

        for video_path in matches:
            resolved = video_path.resolve()
            if resolved in seen:
                continue
            if not video_path.exists():
                raise SystemExit(f"Video file not found: {video_path}")
            if video_path.suffix.lower() not in VIDEO_EXTS:
                raise SystemExit(f"Unsupported video extension: {video_path.suffix}")
            videos.append(video_path)
            seen.add(resolved)

    if not videos:
        raise SystemExit("No video files found")
    return videos


def build_output_path(
    video_path: Path,
    suffix: str,
    in_place: bool,
    output_dir: Path | None = None,
) -> Path:
    if in_place:
        return video_path.with_name(video_path.stem + "_tmp" + video_path.suffix)
    if output_dir is not None:
        output_dir.mkdir(parents=True, exist_ok=True)
        return output_dir / video_path.name
    return video_path.with_name(video_path.stem + suffix + video_path.suffix)


def build_tracklist_path(video_path: Path, output_path: Path, in_place: bool) -> Path:
    if in_place:
        return video_path.with_suffix(".txt")
    return output_path.with_suffix(".txt")


def collect_video_durations(videos: list[Path]) -> dict[Path, float]:
    return {video_path: ffprobe_duration(video_path) for video_path in videos}


def print_preflight_summary(
    args: argparse.Namespace,
    videos: list[Path],
    video_durations: dict[Path, float],
) -> None:
    print("Preflight")
    print("---------")
    print(f"Videos: {len(videos)}")
    for video_path in videos:
        print(f"  {video_path}: {format_duration(video_durations[video_path])}")
    total_video_duration = sum(video_durations.values())
    print(f"Video total: {format_duration(total_video_duration)}")

    audio_input_files = list_mp3_files(args.audio_input_dir)
    if audio_input_files:
        audio_input_duration = sum_durations(audio_input_files)
        print(
            f"MP3 input: {len(audio_input_files)} file(s), "
            f"total {format_duration(audio_input_duration)}"
        )
        longest_video = max(video_durations.values()) if video_durations else 0.0
        if audio_input_duration < longest_video:
            print(
                "Warning: MP3 input is shorter than the longest video "
                f"({format_duration(audio_input_duration)} < "
                f"{format_duration(longest_video)}). Audio may loop."
            )
    else:
        print(f"MP3 input: no MP3 files found in {args.audio_input_dir}")

    if args.force_shuffle_audio_input:
        mode = "pro Video neu mischen"
    elif args.combine:
        mode = "audio-input einmal kombinieren"
    else:
        mode = "vorhandenes Audio verwenden"
    print(f"Mode: {mode}")

    if args.in_place:
        print("Output: in-place")
    elif args.output_dir:
        print(f"Output: {args.output_dir}")
    else:
        print(f"Output: next to source video with suffix {args.suffix}")
    print(f"Overwrite: {'yes' if args.overwrite else 'no'}")
    print()


def choose_audio_codec_for_path(path: Path) -> str:
    ext = path.suffix.lower()
    if ext == ".webm":
        return "opus"
    if ext in {".mp4", ".mov", ".m4v", ".mkv"}:
        return "aac"
    if ext == ".avi":
        return "mp3"
    return "aac"


def read_input(prompt: str) -> str:
    try:
        return input(prompt).strip()
    except EOFError:
        return ""


def prompt_bool(question: str, default: bool = False) -> bool:
    suffix = " [Y/n]: " if default else " [y/N]: "
    while True:
        answer = read_input(question + suffix).lower()
        if not answer:
            return default
        if answer in {"y", "yes", "j", "ja"}:
            return True
        if answer in {"n", "no", "nein"}:
            return False
        print("Bitte mit ja oder nein antworten.")


def parse_single_path(answer: str, *, label: str) -> Path | None:
    if not answer:
        return None
    try:
        parts = shlex.split(answer)
    except ValueError as exc:
        print(f"{label} konnte nicht gelesen werden: {exc}")
        return None
    if len(parts) != 1:
        print(f"Bitte genau einen {label} angeben.")
        return None
    return Path(parts[0]).expanduser()


def prompt_optional_path(question: str, *, must_exist_dir: bool = False) -> Path | None:
    while True:
        answer = read_input(question)
        if not answer:
            return None
        path = parse_single_path(answer, label="Pfad")
        if path is None:
            continue
        if must_exist_dir and not path.is_dir():
            print(f"Ordner nicht gefunden: {path}")
            continue
        return path


def parse_path_list(answer: str) -> list[Path] | None:
    if not answer:
        return None
    try:
        parts = shlex.split(answer)
    except ValueError as exc:
        print(f"Input konnte nicht gelesen werden: {exc}")
        return None
    if not parts:
        return None
    return [Path(part).expanduser() for part in parts]


def prompt_video_inputs() -> list[Path] | None:
    print("Video-Input Beispiele:")
    print("  video/")
    print("  /pfad/zum/video.mp4")
    print('  "/pfad/zu/*.mp4"')
    print('  "/pfad/Video 1.mp4" "/pfad/Video 2.mp4"')
    while True:
        video_inputs = parse_path_list(
            read_input("Input-Datei, Ordner oder Dateien (leer = video/): ")
        )
        if video_inputs is None:
            return None
        try:
            resolve_video_inputs(video_inputs)
        except SystemExit as exc:
            print(exc)
            continue
        return video_inputs


def prompt_mode() -> str:
    print()
    print("Audio-Modus:")
    print("  1) vorhandenes Audio aus audio/ verwenden")
    print("  2) audio-input/ einmal kombinieren und optional mischen")
    print("  3) pro Video neu aus audio-input/ mischen")
    while True:
        answer = read_input("Modus waehlen [1-3, leer = 1]: ")
        if not answer:
            return "existing"
        if answer == "1":
            return "existing"
        if answer == "2":
            return "combine"
        if answer == "3":
            return "force"
        print("Bitte 1, 2 oder 3 eingeben.")


def run_cli_assistant(args: argparse.Namespace) -> argparse.Namespace:
    args.interactive_assistant = True
    print("AudioSwitcher Assistent")
    print("----------------------")
    args.video_input = prompt_video_inputs()

    mode = prompt_mode()
    audio_input_dir = prompt_optional_path(
        "Audio-Input-Ordner mit MP3s (leer = audio-input/): ",
        must_exist_dir=True,
    )
    if audio_input_dir is not None:
        args.audio_input_dir = audio_input_dir

    if mode == "combine":
        args.combine = True
        args.shuffle_audio_input = prompt_bool("Beim Kombinieren mischen?", default=True)
    elif mode == "force":
        args.force_shuffle_audio_input = True

    output_dir = prompt_optional_path(
        "Output-Ordner (leer = neben dem Video mit Suffix schreiben): "
    )

    args.in_place = prompt_bool("In-place verwenden und Originalvideo ersetzen?", default=False)
    if args.in_place:
        args.output_dir = None
    else:
        args.output_dir = output_dir

    args.overwrite = prompt_bool("Vorhandene Output-Dateien ueberschreiben?", default=False)

    print()
    return args


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
        "--video-input",
        nargs="+",
        type=Path,
        help=(
            "Optional video file(s), directory, or glob pattern to process "
            "(overrides --video-dir)."
        ),
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
        "--output-dir",
        type=Path,
        help=(
            "Directory for processed videos. When set, output files keep the "
            "original video filename unless --in-place is used."
        ),
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
    parser.add_argument(
        "--list-audio-input-lengths",
        action="store_true",
        help="List durations of MP3 files in the audio-input directory and exit.",
    )
    parser.add_argument(
        "--list-audio-sort",
        choices=["name", "date"],
        default="name",
        help="Sort order for --list-audio-lengths (default: name).",
    )
    parser.add_argument(
        "--shuffle-audio-input",
        action="store_true",
        help="Randomize order of MP3s from audio-input when combining.",
    )
    parser.add_argument(
        "--force-shuffle-audio-input",
        action="store_true",
        help=(
            "Always create a new shuffled MP3 from audio-input, even if audio/ "
            "already contains an MP3."
        ),
    )
    parser.add_argument(
        "--combine-only",
        action="store_true",
        help="Only combine audio-input MP3s into audio/ and exit.",
    )

    args = parser.parse_args()
    if len(sys.argv) == 1:
        args = run_cli_assistant(args)

    which_or_die("ffmpeg")
    which_or_die("ffprobe")

    if args.combine_only:
        combined = create_combined_audio(
            args.audio_input_dir,
            args.audio_dir,
            args.shuffle_audio_input or args.force_shuffle_audio_input,
        )
        tracklist_path = combined.with_suffix(".txt")
        duration = ffprobe_duration(combined)
        print(f"Combined audio: {combined}")
        print(f"Tracklist: {tracklist_path}")
        print(f"Length: {format_duration(duration)} ({duration:.2f}s)")
        return

    if args.list_audio_lengths or args.list_audio_input_lengths:
        target_dir = args.audio_input_dir if args.list_audio_input_lengths else args.audio_dir
        audio_files = [p for p in target_dir.glob("*.mp3") if p.is_file()]
        if not audio_files:
            print(f"No MP3 files found in {target_dir}")
            return
        if args.list_audio_sort == "date":
            audio_files = sorted(audio_files, key=lambda p: p.stat().st_mtime, reverse=True)
        else:
            audio_files = sorted(audio_files, key=lambda p: p.name.lower())
        total = 0.0
        for p in audio_files:
            duration = ffprobe_duration(p)
            total += duration
            print(f"{p.name}: {format_duration(duration)} ({duration:.2f}s)")
        print(f"Total: {format_duration(total)} ({total:.2f}s)")
        return

    if args.video_input:
        videos = resolve_video_inputs(args.video_input)
    else:
        video_dir = args.video_dir
        if not video_dir.exists():
            raise SystemExit(f"Video directory not found: {video_dir}")

        videos = [p for p in sorted(video_dir.iterdir()) if p.suffix.lower() in VIDEO_EXTS]
        if not videos:
            raise SystemExit(f"No video files found in {video_dir}")

    video_durations = collect_video_durations(videos)
    print_preflight_summary(args, videos, video_durations)
    if getattr(args, "interactive_assistant", False):
        if not prompt_bool("Verarbeitung starten?", default=True):
            print("Abgebrochen.")
            return

    if args.audio_file:
        audio_path = args.audio_file
    elif args.force_shuffle_audio_input:
        audio_path = None
    else:
        audio_path = pick_mp3(args.audio_dir, args.audio_pick, args.audio_name)
        if args.combine or audio_path is None:
            audio_path = create_combined_audio(
                args.audio_input_dir,
                args.audio_dir,
                args.shuffle_audio_input,
            )

    if audio_path is not None and not audio_path.exists():
        raise SystemExit(f"Audio file not found: {audio_path}")

    failures = []
    for video_path in videos:
        try:
            video_duration = video_durations[video_path]
            output_path = build_output_path(
                video_path,
                args.suffix,
                args.in_place,
                args.output_dir,
            )
            if output_path.exists() and not args.overwrite:
                raise RuntimeError(f"Output exists: {output_path} (use --overwrite)")

            current_audio_path = audio_path
            if args.force_shuffle_audio_input:
                current_audio_path = create_combined_audio(
                    args.audio_input_dir,
                    args.audio_dir,
                    True,
                    output_path=args.audio_dir / f"{video_path.stem}.mp3",
                    tracklist_path=build_tracklist_path(
                        video_path,
                        output_path,
                        args.in_place,
                    ),
                    target_duration=video_duration,
                    video_path=video_path,
                )

            audio_duration = ffprobe_duration(current_audio_path)
            audio_longer = audio_duration > (video_duration + 0.01)
            audio_shorter = audio_duration + 0.01 < video_duration
            if audio_shorter:
                print(
                    "Warning: audio shorter than video, looping from start "
                    f"(audio {format_duration(audio_duration)}, "
                    f"video {format_duration(video_duration)})"
                )

            audio_codec = args.audio_codec or choose_audio_codec_for_path(output_path)

            cmd = [
                "ffmpeg",
                "-hide_banner",
                "-stats",
                "-i",
                str(video_path),
            ]
            if audio_shorter:
                cmd.extend(["-stream_loop", "-1"])
            cmd.extend([
                "-i",
                str(current_audio_path),
                "-map",
                "0:v:0",
                "-map",
                "1:a:0",
                "-c:v",
                "copy",
                "-c:a",
                audio_codec,
            ])
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
