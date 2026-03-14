#!/usr/bin/env python3
"""
Download random video-only clips from a YouTube URL using yt-dlp + ffmpeg.
Outputs to sludge_videos/ folder for use as background sludge content.
Automatically crops to 1080x1920 (iPhone vertical resolution).
"""
import argparse
import glob
import json
import os
import random
import subprocess
from dataclasses import dataclass

# Target resolution for sludge videos (iPhone vertical)
TARGET_WIDTH = 1080
TARGET_HEIGHT = 1920

# Minimum video duration (10 minutes)
MIN_DURATION_SECONDS = 600

# Avoid first/last 20% of video (use middle 60%)
TRIM_PERCENT = 0.20

# Default output directory relative to project root
DEFAULT_OUTPUT_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "sludge_videos"
)


@dataclass(frozen=True)
class Segment:
    start: int  # seconds
    end: int    # seconds


def hms(seconds: int) -> str:
    """Convert seconds to HH:MM:SS format."""
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    return f"{h:02d}:{m:02d}:{s:02d}"


def get_video_dimensions(video_path: str) -> tuple[int, int]:
    """Get video width and height using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-select_streams", "v:0",
        "-show_entries", "stream=width,height",
        "-of", "json",
        video_path
    ]
    result = subprocess.check_output(cmd, text=True)
    info = json.loads(result)
    stream = info["streams"][0]
    return stream["width"], stream["height"]


def crop_to_vertical(input_path: str, output_path: str) -> None:
    """
    Crop video to 1080x1920 (9:16 vertical) from center.
    Takes a vertical slice from the center of the video.
    """
    src_w, src_h = get_video_dimensions(input_path)

    # Calculate crop dimensions to get 9:16 aspect ratio
    target_aspect = TARGET_WIDTH / TARGET_HEIGHT  # 0.5625

    # Determine crop size based on source dimensions
    if src_w / src_h > target_aspect:
        # Source is wider than target - crop width, keep height
        crop_h = src_h
        crop_w = int(src_h * target_aspect)
    else:
        # Source is taller than target - crop height, keep width
        crop_w = src_w
        crop_h = int(src_w / target_aspect)

    # Center crop offsets
    x_offset = (src_w - crop_w) // 2
    y_offset = (src_h - crop_h) // 2

    # FFmpeg crop filter and scale to exact target size
    crop_filter = f"crop={crop_w}:{crop_h}:{x_offset}:{y_offset},scale={TARGET_WIDTH}:{TARGET_HEIGHT}"

    cmd = [
        "ffmpeg", "-y",
        "-i", input_path,
        "-vf", crop_filter,
        "-c:v", "libx264",
        "-preset", "fast",
        "-crf", "23",
        "-an",  # no audio
        output_path
    ]
    subprocess.run(cmd, check=True, capture_output=True)


def get_duration_seconds(url: str) -> int:
    """Get video duration using yt-dlp metadata (no download)."""
    out = subprocess.check_output(["yt-dlp", "-J", url], text=True)
    info = json.loads(out)
    dur = info.get("duration")
    if dur is None:
        raise RuntimeError("yt-dlp did not return duration for this URL.")
    return int(dur)


def pick_random_segments(
    duration: int,
    clip_len: int,
    n: int,
    min_gap: int,
    seed: int | None
) -> list[Segment]:
    """
    Pick up to n non-overlapping segments of length clip_len.
    Only picks from middle 60% of video (avoids first/last 20%).
    min_gap adds padding (seconds) around each segment to reduce near-overlaps.
    """
    rng = random.Random(seed)

    # Calculate safe zone (middle 60% of video)
    trim_start = int(duration * TRIM_PERCENT)
    trim_end = int(duration * (1 - TRIM_PERCENT))

    # Earliest and latest possible start times within safe zone
    earliest_start = trim_start
    latest_start = trim_end - clip_len

    if latest_start < earliest_start:
        raise ValueError(f"Video middle section too short for {clip_len}s clips.")

    segments: list[Segment] = []
    attempts = 0
    max_attempts = 5000

    def conflicts(start: int, end: int) -> bool:
        for seg in segments:
            a1 = seg.start - min_gap
            a2 = seg.end + min_gap
            if not (end <= a1 or start >= a2):
                return True
        return False

    while len(segments) < n and attempts < max_attempts:
        attempts += 1
        start = rng.randint(earliest_start, latest_start)
        end = start + clip_len
        if not conflicts(start, end):
            segments.append(Segment(start, end))

    if len(segments) < n:
        print(f"Warning: only found {len(segments)}/{n} non-overlapping segments.")

    return sorted(segments, key=lambda s: s.start)


def download_segment_video_only(
    url: str,
    seg: Segment,
    out_dir: str,
    height: int,
    prefix: str,
) -> str:
    """
    Download a time slice using yt-dlp --download-sections.
    Then crop to 1080x1920 vertical format.
    Returns the final output file path.
    """
    section = f"*{hms(seg.start)}-{hms(seg.end)}"
    fmt = f"bv*[height<={height}]/b[height<={height}]/bv*/b"

    # Temporary file pattern for raw download
    temp_pattern = f"{prefix}_%(id)s_{seg.start:06d}_{seg.end:06d}"
    temp_tmpl = os.path.join(out_dir, f"{temp_pattern}_temp.%(ext)s")

    cmd = [
        "yt-dlp",
        url,
        "--download-sections", section,
        "-f", fmt,
        "--merge-output-format", "mp4",
        "--postprocessor-args", "ffmpeg:-an",  # remove audio
        "-o", temp_tmpl,
    ]
    print("  Downloading...")
    subprocess.run(cmd, check=True)

    # Find the actual downloaded file
    search_pattern = os.path.join(out_dir, f"{prefix}_*_{seg.start:06d}_{seg.end:06d}_temp.mp4")
    matches = glob.glob(search_pattern)
    if not matches:
        raise FileNotFoundError(f"Could not find downloaded file matching {search_pattern}")
    temp_file = matches[0]

    # Crop to vertical format
    final_file = temp_file.replace("_temp.mp4", ".mp4")
    print(f"  Cropping to {TARGET_WIDTH}x{TARGET_HEIGHT}...")
    crop_to_vertical(temp_file, final_file)

    # Remove temp file
    os.remove(temp_file)

    return final_file


def download_sludge(
    url: str,
    num_clips: int = 3,
    clip_length: int = 180,
    height: int = 480,
    min_gap: int = 30,
    seed: int | None = None,
    out_dir: str | None = None,
    prefix: str = "sludge"
) -> list[str]:
    """
    Main function to download random sludge clips from a YouTube video.

    Args:
        url: YouTube video URL
        num_clips: Number of random clips to download
        clip_length: Length of each clip in seconds (default 180 = 3 min)
        height: Max video height (default 480)
        min_gap: Minimum gap between clips in seconds
        seed: Random seed for reproducibility
        out_dir: Output directory (defaults to sludge_videos/)
        prefix: Filename prefix

    Returns:
        List of downloaded file paths
    """
    if out_dir is None:
        out_dir = DEFAULT_OUTPUT_DIR

    os.makedirs(out_dir, exist_ok=True)

    print(f"Fetching video metadata...")
    duration = get_duration_seconds(url)
    print(f"Duration: {duration} seconds ({hms(duration)})")

    if duration < MIN_DURATION_SECONDS:
        print(f"Skipping: video is shorter than {MIN_DURATION_SECONDS}s minimum")
        return []

    segments = pick_random_segments(duration, clip_length, num_clips, min_gap, seed)

    downloaded = []
    for i, seg in enumerate(segments, 1):
        print(f"\nClip {i}/{len(segments)}: {hms(seg.start)} -> {hms(seg.end)}")
        out_path = download_segment_video_only(url, seg, out_dir, height, f"{prefix}{i}")
        downloaded.append(out_path)

    print(f"\nDone! Downloaded {len(downloaded)} clips to {out_dir}")
    return downloaded


def main():
    p = argparse.ArgumentParser(
        description="Download random video-only clips from YouTube for sludge content."
    )
    p.add_argument("urls", nargs="+", help="YouTube video URL(s)")
    p.add_argument("-n", "--num", type=int, default=3,
                   help="Number of random clips per video (default: 3)")
    p.add_argument("-l", "--length", type=int, default=180,
                   help="Clip length in seconds (default: 180 = 3 minutes)")
    p.add_argument("--height", type=int, default=480,
                   help="Max video height (default: 480)")
    p.add_argument("--min-gap", type=int, default=30,
                   help="Min gap between clips in seconds (default: 30)")
    p.add_argument("--seed", type=int, default=None,
                   help="Random seed for reproducible picks")
    p.add_argument("-o", "--out", default=None,
                   help=f"Output directory (default: {DEFAULT_OUTPUT_DIR})")
    p.add_argument("--prefix", default="sludge",
                   help="Filename prefix (default: sludge)")
    args = p.parse_args()

    for i, url in enumerate(args.urls, 1):
        print(f"\n{'='*60}")
        print(f"Processing video {i}/{len(args.urls)}: {url}")
        print('='*60)
        try:
            download_sludge(
                url=url,
                num_clips=args.num,
                clip_length=args.length,
                height=args.height,
                min_gap=args.min_gap,
                seed=args.seed,
                out_dir=args.out,
                prefix=f"{args.prefix}{i}",
            )
        except Exception as e:
            print(f"Error processing {url}: {e}")


if __name__ == "__main__":
    main()
