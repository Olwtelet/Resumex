"""
Benchmark and optimize the 'add faded background' step (step 7).

Current implementation does 4 moviepy encode passes:
  1. Resize sludge video to full dims
  2. Blur every frame with cv2.GaussianBlur(71x71)
  3. Resize foreground with padding
  4. Composite foreground onto blurred background

This test creates synthetic input videos and compares the current
approach against a single-pass ffmpeg filter chain.
"""
import sys
import os
import time
import subprocess

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

TEMP_DIR = os.path.join(PROJECT_ROOT, "temp")
os.makedirs(TEMP_DIR, exist_ok=True)

# Dimensions matching video_maker.py
FULL_WIDTH = 1080
FULL_HEIGHT = 1920
SLUDGE_HEIGHT = int(FULL_HEIGHT * 0.4)  # 768
TEST_DURATION = 10  # seconds - short for quick testing


def generate_test_videos():
    """Generate synthetic test videos using ffmpeg testsrc."""
    main_video = os.path.join(TEMP_DIR, "test_stacked_video.mp4")
    sludge_video = os.path.join(TEMP_DIR, "test_sludge_video.mp4")

    if not os.path.exists(main_video):
        print(f"  Generating test main video ({FULL_WIDTH}x{FULL_HEIGHT}, {TEST_DURATION}s)...")
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"testsrc=duration={TEST_DURATION}:size={FULL_WIDTH}x{FULL_HEIGHT}:rate=30",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            main_video
        ], capture_output=True)

    if not os.path.exists(sludge_video):
        print(f"  Generating test sludge video ({FULL_WIDTH}x{SLUDGE_HEIGHT}, {TEST_DURATION}s)...")
        subprocess.run([
            "ffmpeg", "-y", "-f", "lavfi",
            "-i", f"testsrc=duration={TEST_DURATION}:size={FULL_WIDTH}x{SLUDGE_HEIGHT}:rate=30",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            sludge_video
        ], capture_output=True)

    return main_video, sludge_video


def benchmark_current(main_video, sludge_video):
    """Run the current moviepy-based implementation."""
    from src.video_editing.video_editing_functions import add_fade_background

    output = os.path.join(TEMP_DIR, "result_current.mp4")
    t = time.time()
    add_fade_background(main_video, sludge_video, output)
    elapsed = time.time() - t
    size = os.path.getsize(output) / (1024 * 1024) if os.path.exists(output) else 0
    return elapsed, size, output


def benchmark_ffmpeg_single_pass(main_video, sludge_video):
    """
    Single-pass ffmpeg approach:
    - Scale sludge to full dims
    - Apply gblur (equivalent to 71x71 Gaussian)
    - Overlay the main video (with padding) on top
    """
    output = os.path.join(TEMP_DIR, "result_ffmpeg.mp4")
    pad = 50  # foreground_video_pad from paste_video_onto_video

    # Foreground is resized to (width - 2*pad) keeping aspect ratio
    fg_width = FULL_WIDTH - (pad * 2)  # 980
    fg_height = int(fg_width * (FULL_HEIGHT / FULL_WIDTH))  # maintain aspect ratio

    # gblur sigma ~35 approximates a 71x71 Gaussian kernel (sigma ~ ksize/2)
    blur_sigma = 35

    # Center position for overlay
    overlay_x = (FULL_WIDTH - fg_width) // 2
    overlay_y = (FULL_HEIGHT - fg_height) // 2

    filter_complex = (
        f"[1:v]scale={FULL_WIDTH}:{FULL_HEIGHT},gblur=sigma={blur_sigma}[bg];"
        f"[0:v]scale={fg_width}:{fg_height}[fg];"
        f"[bg][fg]overlay={overlay_x}:{overlay_y}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", main_video,
        "-i", sludge_video,
        "-filter_complex", filter_complex,
        "-c:v", "libx264", "-preset", "medium", "-pix_fmt", "yuv420p",
        "-an", output
    ]

    t = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - t

    if result.returncode != 0:
        print(f"  ffmpeg error: {result.stderr[-500:]}")
        return elapsed, 0, output

    size = os.path.getsize(output) / (1024 * 1024) if os.path.exists(output) else 0
    return elapsed, size, output


def benchmark_ffmpeg_gpu(main_video, sludge_video):
    """
    Single-pass ffmpeg with NVENC hardware encoding (if available).
    Falls back gracefully if no GPU.
    """
    output = os.path.join(TEMP_DIR, "result_ffmpeg_gpu.mp4")
    pad = 50
    fg_width = FULL_WIDTH - (pad * 2)
    fg_height = int(fg_width * (FULL_HEIGHT / FULL_WIDTH))
    blur_sigma = 35
    overlay_x = (FULL_WIDTH - fg_width) // 2
    overlay_y = (FULL_HEIGHT - fg_height) // 2

    filter_complex = (
        f"[1:v]scale={FULL_WIDTH}:{FULL_HEIGHT},gblur=sigma={blur_sigma}[bg];"
        f"[0:v]scale={fg_width}:{fg_height}[fg];"
        f"[bg][fg]overlay={overlay_x}:{overlay_y}"
    )

    cmd = [
        "ffmpeg", "-y",
        "-i", main_video,
        "-i", sludge_video,
        "-filter_complex", filter_complex,
        "-c:v", "h264_nvenc", "-preset", "p4", "-pix_fmt", "yuv420p",
        "-an", output
    ]

    t = time.time()
    result = subprocess.run(cmd, capture_output=True, text=True)
    elapsed = time.time() - t

    if result.returncode != 0:
        if "nvenc" in result.stderr.lower() or "encoder" in result.stderr.lower():
            return None, 0, output  # GPU not available
        print(f"  ffmpeg GPU error: {result.stderr[-500:]}")
        return elapsed, 0, output

    size = os.path.getsize(output) / (1024 * 1024) if os.path.exists(output) else 0
    return elapsed, size, output


def main():
    print("\n  STEP 7 BENCHMARK: add_fade_background")
    print("  " + "=" * 50)
    print(f"  Video: {FULL_WIDTH}x{FULL_HEIGHT}, {TEST_DURATION}s @ 30fps")
    print()

    # Generate test inputs
    print("  [1] Generating test videos...")
    main_video, sludge_video = generate_test_videos()
    print("  Done.\n")

    results = []

    # Benchmark current implementation
    print("  [2] Running CURRENT implementation (moviepy, 4 passes)...")
    elapsed, size, _ = benchmark_current(main_video, sludge_video)
    results.append(("Current (moviepy)", elapsed, size))
    print(f"      {elapsed:.1f}s, {size:.1f}MB\n")

    # Benchmark ffmpeg single-pass
    print("  [3] Running FFMPEG single-pass...")
    elapsed, size, _ = benchmark_ffmpeg_single_pass(main_video, sludge_video)
    results.append(("FFmpeg single-pass", elapsed, size))
    print(f"      {elapsed:.1f}s, {size:.1f}MB\n")

    # Benchmark ffmpeg GPU
    print("  [4] Running FFMPEG with GPU (NVENC)...")
    elapsed, size, _ = benchmark_ffmpeg_gpu(main_video, sludge_video)
    if elapsed is None:
        print("      Skipped (no NVENC GPU available)\n")
    else:
        results.append(("FFmpeg GPU (NVENC)", elapsed, size))
        print(f"      {elapsed:.1f}s, {size:.1f}MB\n")

    # Summary
    print("  " + "-" * 50)
    print(f"  {'Method':<25}{'Time':>8}{'Size':>10}{'Speedup':>10}")
    print("  " + "-" * 50)
    baseline = results[0][1] if results else 1
    for name, elapsed, size in results:
        speedup = baseline / elapsed if elapsed > 0 else 0
        print(f"  {name:<25}{elapsed:>7.1f}s{size:>8.1f}MB{speedup:>9.1f}x")
    print("  " + "-" * 50)


if __name__ == "__main__":
    main()
