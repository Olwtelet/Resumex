"""
End-to-end test for the final_vid production pipeline.
Generates one video with granular per-step timing, then cleans up.
Does NOT write to post_usage_history or youtube_post_history.
"""
import sys
import os
import shutil
import time
import random

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

TEMP_DIR = os.path.join(PROJECT_ROOT, "temp")
REDDIT_DATA_DIR = os.path.join(PROJECT_ROOT, "reddit_data")

VIDEO_DIMS = (1080, 1920)
SLOP_VIDEO_VERTICAL_PERCENT = 0.4
SCROLLING_REDDIT_POST_HEIGHT = int(VIDEO_DIMS[1] * SLOP_VIDEO_VERTICAL_PERCENT)
SUB_SLUDGE_VIDEO_DIMS = (VIDEO_DIMS[0], int(VIDEO_DIMS[1] * SLOP_VIDEO_VERTICAL_PERCENT))


def main():
    results = []

    def run_step(name, fn):
        t = time.time()
        result = fn()
        results.append((name, time.time() - t))
        return result

    print("\n  FINAL VID PIPELINE - GRANULAR TIMING TEST")
    print("  Running...\n")

    os.makedirs(TEMP_DIR, exist_ok=True)

    # --- Step: Load posts ---
    from src.scraper.scraper import DataSaver

    def load_posts():
        return DataSaver().get_all_posts()
    posts = run_step("Load posts from reddit_data/", load_posts)

    # --- Step: Filter posts ---
    import video_maker

    class FakePostUsageHistory:
        def __init__(self): pass
        def add_post(self, url): pass
        def post_exists(self, url): return False
        def get_all_posts(self): return []

    video_maker.PostUsageHistory = FakePostUsageHistory

    def filter_posts_step():
        return video_maker.filter_posts(posts)
    eligible = run_step("Filter posts (scores, length, history)", filter_posts_step)

    if not eligible:
        print("  [!] No eligible posts. Aborting.")
        return

    # --- Step: Create post image ---
    from src.reddit_post_image.post_image_maker import make_reddit_post_image

    random.shuffle(eligible)
    post_image_path = None
    post_data = None

    def create_post_image():
        nonlocal post_image_path, post_data
        for post in eligible:
            post_data = post.to_dict()
            result = make_reddit_post_image(
                thread=post_data["thread_name"],
                title_text=post_data["title"],
                body_text=post_data["content"],
                username=post_data["username"],
                expected_width=VIDEO_DIMS[0],
                subreddit_icon_url="https://www.redditinc.com/assets/images/site/reddit-logo.png",
                save=True,
            )
            if result:
                post_image_path = result
                return result
        return None
    run_step("Render post image (PIL)", create_post_image)

    if not post_image_path:
        print("  [!] Failed to create post image. Aborting.")
        return

    # --- Step: Narration (TTS model load + inference) ---
    from src.narration.narrarate import narrate

    narration_content = f"{post_data['title']}. {post_data['content']}"

    def generate_narration():
        return narrate("jf_alpha", narration_content)
    narration_audio_path, narration_duration = run_step("Narration (Kokoro TTS load + inference)", generate_narration)

    # --- Step: Scroll image into video ---
    from src.video_editing.video_editing_functions import scroll_image

    scrolling_video_path = os.path.join(TEMP_DIR, "reddit_post_scrolling_video.mp4")

    def create_scroll_video():
        scroll_image(
            image_path=post_image_path,
            out_video_path=scrolling_video_path,
            scroll_duration=narration_duration,
            height=SCROLLING_REDDIT_POST_HEIGHT,
            width=VIDEO_DIMS[0],
        )
    run_step("Scroll image to video (ffmpeg crop)", create_scroll_video)

    # --- Step: Get sludge video duration ---
    from src.sludge.sludge_video_extractor import get_video_duration, extract_and_resize

    video_extensions = (".mp4", ".avi", ".mkv", ".mov", ".webm")
    sludge_dir = "sludge_videos"
    all_videos = [f for f in os.listdir(sludge_dir) if f.lower().endswith(video_extensions)]
    random_video = random.choice(all_videos)
    base_sludge_path = os.path.join(sludge_dir, random_video)

    def get_sludge_duration():
        return get_video_duration(base_sludge_path)
    sludge_duration = run_step("Get sludge video duration", get_sludge_duration)

    # --- Step: Extract + resize subclip (single ffmpeg pass) ---
    sub_sludge_path = os.path.join(TEMP_DIR, "sub_sludge_video.mp4")
    start_time = random.randint(10, int(sludge_duration) - int(narration_duration) - 10)
    end_time = start_time + narration_duration

    def extract_and_resize_sludge():
        return extract_and_resize(
            base_sludge_path, sub_sludge_path,
            start_time, end_time,
            SUB_SLUDGE_VIDEO_DIMS[0], SUB_SLUDGE_VIDEO_DIMS[1],
        )
    run_step("Extract + resize sludge (ffmpeg single pass)", extract_and_resize_sludge)

    # --- Step: Stack videos ---
    from src.video_editing.video_editing_functions import stack_videos_vertically

    stacked_video_path = os.path.join(TEMP_DIR, "stacked_video.mp4")

    def stack_videos():
        stack_videos_vertically(scrolling_video_path, sub_sludge_path, stacked_video_path)
    run_step("Stack videos vertically (ffmpeg vstack)", stack_videos)

    # --- Step: Add fade background ---
    from src.video_editing.video_editing_functions import add_fade_background

    background_video_path = os.path.join(TEMP_DIR, "stacked_video_with_background.mp4")

    def add_background():
        add_fade_background(stacked_video_path, sub_sludge_path, background_video_path, output_dims=VIDEO_DIMS)
    run_step("Add fade background (ffmpeg blur+overlay+encode)", add_background)

    # --- Step: Add narration audio ---
    from src.video_editing.video_editing_functions import add_audio_to_video

    narrated_video_path = os.path.join(TEMP_DIR, "narrated_final_video.mp4")

    def add_audio():
        add_audio_to_video(background_video_path, narration_audio_path, narrated_video_path)
    run_step("Add narration audio (ffmpeg copy + aac mux)", add_audio)

    # --- Step: Generate metadata ---
    def gen_metadata():
        return video_maker.create_metadata(
            post_data["title"], post_data["content"], post_data.get("url")
        )
    metadata = run_step("Generate metadata (Ollama gemma2:9b)", gen_metadata)

    # --- Save outputs for quality review ---
    import json

    test_vid_path = os.path.join(PROJECT_ROOT, "tests", "test_final_vid.mp4")
    test_metadata_path = os.path.join(PROJECT_ROOT, "tests", "test_final_vid_metadata.json")

    shutil.copy2(narrated_video_path, test_vid_path)
    with open(test_metadata_path, "w") as f:
        json.dump(metadata, f, indent=4)
    print(f"  Saved: {test_vid_path}")
    print(f"  Saved: {test_metadata_path}")

    # --- Cleanup temp ---
    def cleanup():
        video_maker.cleanup_temp_files()
    run_step("Cleanup temp files", cleanup)

    # --- Print results sorted by time ---
    results_sorted = sorted(results, key=lambda x: x[1], reverse=True)

    print("\n  " + "-" * 68)
    print(f"  {'#':<4}{'Step':<48}{'Time (s)':>10}")
    print("  " + "-" * 68)
    for i, (name, elapsed) in enumerate(results_sorted, 1):
        print(f"  {i:<4}{name:<48}{elapsed:>9.1f}s")
    print("  " + "-" * 68)
    total = sum(r[1] for r in results)
    print(f"  {'':4}{'TOTAL':<48}{total:>9.1f}s")
    print("  " + "-" * 68 + "\n")


if __name__ == "__main__":
    main()
