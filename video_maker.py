print(f"Importing modules...")

from src.transcription.transcriber_local import Transcriber
from src.scraper.scraper import DataSaver
from src.narration.narrarate import narrate
from src.reddit_post_image.post_image_maker import make_reddit_post_image
from src.video_editing.caption_maker import extract_word_timestamps_from_transcript


import json
import random
import time
import uuid
from src.sludge.sludge_video_extractor import Extractor
from moviepy.editor import VideoFileClip, AudioFileClip, CompositeVideoClip
import os
import stat
import pathlib
import platform
import subprocess

from src.video_editing.video_editing_functions import (
    scroll_image,
    stack_videos_vertically,
    add_fade_background,
    add_audio_to_video,
)
from concurrent.futures import ThreadPoolExecutor, as_completed


print(f"Successfully loaded all necessary support modules!")

# Toggle for parallel execution of video rendering and metadata generation
# When True: metadata generation runs in parallel with video steps 3-8
# When False: metadata generation runs after video is complete (original behavior)
PARALLEL_METADATA_GENERATION = True

SUBREDDIT_ICON_URL = "https://www.redditinc.com/assets/images/site/reddit-logo.png"
VIDEO_DIMS = (1080, 1920)
SLOP_VIDEO_VERTICAL_PERCENT = 0.4


SCROLLING_REDDIT_POST_HEIGHT = int(VIDEO_DIMS[1] * SLOP_VIDEO_VERTICAL_PERCENT)
SUB_SLUDGE_VIDEO_DIMS = (
    VIDEO_DIMS[0],
    int(VIDEO_DIMS[1] * SLOP_VIDEO_VERTICAL_PERCENT),
)


class PostUsageHistory:
    def __init__(self):
        self.fp = "data/post_usage_history.txt"

        if not os.path.exists(self.fp):
            with open(self.fp, "w") as f:
                pass

    def add_post(self, post_url):
        with open(self.fp, "a") as f:
            f.write(f"{post_url}\n")

    def get_all_posts(self):
        with open(self.fp, "r") as f:
            return [line.strip() for line in f if line.strip()]

    def post_exists(self, post_url):
        existing_posts = self.get_all_posts()
        if post_url in existing_posts:
            return True
        return False


MIN_CONTENT_LENGTH = 300
MAX_CONTENT_LENGTH = 1500
MIN_ENGAGEMENT = 4
MIN_REPOST_QUALITY = 6
MIN_NARRATIVE_CURIOSITY = 4


def filter_posts(posts):
    """Filter posts by usage history, content length, and scores."""
    post_usage_history = PostUsageHistory()
    eligible = []

    for post in posts:
        post_data = post.to_dict()

        # skip empty content
        if not post_data["content"].strip():
            continue

        # skip already used
        if post_usage_history.post_exists(post_data["url"]):
            continue

        # skip posts without scores
        scores = post_data.get("scores")
        if not scores:
            continue

        # skip posts that are too short or too long for image creation
        content_len = len(post_data["content"])
        if content_len < MIN_CONTENT_LENGTH or content_len > MAX_CONTENT_LENGTH:
            continue

        # skip posts with bad scores
        if scores.get("engagement", 0) < MIN_ENGAGEMENT:
            continue
        if scores.get("repost_quality", 0) < MIN_REPOST_QUALITY:
            continue
        if scores.get("narrative_curiosity", 0) < MIN_NARRATIVE_CURIOSITY:
            continue

        eligible.append(post)

    return eligible


def get_post_image(posts, expected_width):
    eligible = filter_posts(posts)
    print(f"[2] {len(eligible)} posts passed filtering (from {len(posts)} total)")

    if not eligible:
        print("[2] No eligible posts available.")
        return None, None

    random.shuffle(eligible)

    for post in eligible:
        post_data = post.to_dict()

        image_path = make_reddit_post_image(
            thread=post_data["thread_name"],
            title_text=post_data["title"],
            body_text=post_data["content"],
            username=post_data["username"],
            expected_width=expected_width,
            subreddit_icon_url=SUBREDDIT_ICON_URL,
            save=True,
        )

        if image_path is None:
            continue

        # successfully made the image
        post_usage_history = PostUsageHistory()
        post_usage_history.add_post(post_data["url"])
        return image_path, post_data

    print("[2] Failed to create image from any eligible post.")
    return None, None


def cleanup_temp_files():
    import gc

    gc.collect()
    time.sleep(1)

    total_deleted = 0
    folders = [r"temp", r"narrations"]

    for folder_path in folders:
        folder = pathlib.Path(folder_path)
        if not folder.exists():
            continue

        for item in folder.rglob("*"):
            try:
                if item.is_file():
                    make_deletable(item)
                    delete_file(item)
                    total_deleted += 1
                elif item.is_dir():
                    try:
                        item.rmdir()
                    except OSError:
                        pass
            except Exception:
                pass

        for item in sorted(folder.rglob("*"), reverse=True):
            if item.is_dir():
                try:
                    item.rmdir()
                except Exception:
                    pass

    print(f"[CLEANUP] Removed {total_deleted} temp files")


def make_deletable(file):
    try:
        os.chmod(file, stat.S_IWUSR | stat.S_IRUSR)
    except Exception:
        pass


def delete_file(file):
    if platform.system() == "Windows":
        try:
            subprocess.run(
                ["takeown", "/f", str(file)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["icacls", str(file), "/grant", "Everyone:F"],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            subprocess.run(
                ["del", "/f", "/q", str(file)],
                shell=True,
                check=False,
            )
        except Exception:
            pass
    else:
        try:
            file.unlink()
        except PermissionError:
            subprocess.run(["sudo", "rm", "-f", str(file)], check=False)


def prepare_post_data(output_dir):
    """
    Steps 1-2: Load scraped data and create post image.
    Returns (post_image_save_path, post_data) or (None, None) on failure.
    """
    temp_folder_name = r"temp"
    os.makedirs(temp_folder_name, exist_ok=True)

    # get scraped post data
    print(f"[1] Loading scraped reddit data...")
    t = time.time()
    reddit_data_manager = DataSaver()
    posts = reddit_data_manager.get_all_posts()
    print(f"[1] Loaded {len(posts)} posts ({time.time()-t:.1f}s)")

    # create the static reddit post
    print(f"[2] Creating post image...")
    t = time.time()
    post_image_save_path, post_data = get_post_image(
        posts, expected_width=VIDEO_DIMS[0]
    )
    if post_image_save_path in [False, None]:
        print("[!] Fatal error: No eligible posts for image creation.")
        return None, None
    print(f"[2] Post: {post_data['title'][:60]}...")
    print(f"[2] Done ({time.time()-t:.1f}s)")

    return post_image_save_path, post_data


def create_video_from_post(post_image_save_path, post_data):
    """
    Steps 3-8: Create video from post image and data.
    Returns narrated_video_path or False on failure.
    """
    # make a narration of this post
    post_title = post_data["title"]
    post_text = post_data["content"]
    narration_content = f"{post_title}. {post_text}"

    print(f"[3] Generating narration...")
    t = time.time()
    narration_audio_file_path, narration_duration = narrate(
        "jf_alpha", narration_content
    )
    print(f"[3] Narration: {narration_duration}s audio ({time.time()-t:.1f}s)")

    # make that a scrolling video
    print(f"[4] Creating scrolling video...")
    t = time.time()
    scrolling_reddit_post_video_path = r"temp/reddit_post_scrolling_video.mp4"
    scroll_image(
        image_path=post_image_save_path,
        out_video_path=scrolling_reddit_post_video_path,
        scroll_duration=narration_duration,
        height=SCROLLING_REDDIT_POST_HEIGHT,
        width=VIDEO_DIMS[0],
    )
    print(f"[4] Done ({time.time()-t:.1f}s)")

    # craft the sub sludge video
    print(f"[5] Extracting sludge video...")
    t = time.time()
    sub_sludge_extractor = Extractor()
    sub_sludge_video_path = r"temp/sub_sludge_video.mp4"
    sub_sludge_extractor.get_random_sludge_video(
        narration_duration, sub_sludge_video_path, SUB_SLUDGE_VIDEO_DIMS
    )
    print(f"[5] Done ({time.time()-t:.1f}s)")

    # put the videos on top of each other
    print(f"[6] Stacking videos...")
    t = time.time()
    stacked_video_path = r"temp/stacked_video.mp4"
    stack_videos_vertically(
        scrolling_reddit_post_video_path, sub_sludge_video_path, stacked_video_path
    )
    print(f"[6] Done ({time.time()-t:.1f}s)")

    # add fade background with pad
    print(f"[7] Adding faded background...")
    t = time.time()
    stacked_video_with_background_path = r"temp/stacked_video_with_background.mp4"
    add_fade_background(
        stacked_video_path, sub_sludge_video_path, stacked_video_with_background_path,
        output_dims=VIDEO_DIMS,
    )
    print(f"[7] Done ({time.time()-t:.1f}s)")

    # add narration audio
    print(f"[8] Adding narration audio...")
    t = time.time()
    narrated_video_path = "temp/narrated_final_video.mp4"
    add_audio_to_video(
        video_path=stacked_video_with_background_path,
        audio_path=narration_audio_file_path,
        out_video_path=narrated_video_path,
    )
    print(f"[8] Done ({time.time()-t:.1f}s)")

    return narrated_video_path


def create_stacked_reddit_scroll_video(output_dir):
    """
    Full video creation pipeline (steps 1-8).
    Wrapper that calls prepare_post_data and create_video_from_post.
    """
    print("="*70)
    print("STARTING NEW VIDEO CREATION")
    print("="*70)

    video_start = time.time()

    # Steps 1-2: Get post data and image
    post_image_save_path, post_data = prepare_post_data(output_dir)
    if post_image_save_path is None:
        return False

    # Steps 3-8: Create video
    narrated_video_path = create_video_from_post(post_image_save_path, post_data)

    total_time = time.time() - video_start
    print(f"[SUCCESS] Video created in {total_time:.1f}s")
    return narrated_video_path, post_data


def create_metadata(post_title, post_content, post_url=None):
    from src.metadata.metadata_generator import generate_metadata
    metadata = generate_metadata(post_title, post_content)
    metadata["reddit_post_title"] = post_title
    metadata["reddit_post_content"] = post_content
    if post_url:
        metadata["reddit_url"] = post_url
    return metadata


def compile_video_and_metadata(video_path, metadata_dict, output_folder):
    if metadata_dict in [None, False]:
        print(f"Fatal error: This metadata is not valid: {metadata_dict}")
        return False

    os.makedirs(output_folder, exist_ok=True)
    subfolder_name = str(uuid.uuid4())[:8]
    subfolder_path = os.path.join(output_folder, subfolder_name)
    os.makedirs(subfolder_path, exist_ok=True)

    new_video_path = os.path.join(subfolder_path, "video.mp4")
    os.rename(video_path, new_video_path)

    metadata_file_path = os.path.join(subfolder_path, "metadata.json")
    with open(metadata_file_path, "w") as f:
        json.dump(metadata_dict, f, indent=4)

    print(f"[FINAL] Saved to {subfolder_name}/")
    print("="*70)


from src.video_editing.video_editing_functions import (
    caption_video,
)
from src.video_editing.caption_maker import (
    generate_caption_frames,
)


def create_slop_with_captions_video():
    all_posts = DataSaver().get_all_posts()
    if len(all_posts) == 0:
        print(f"[!] Fatal error: DataSaver().get_all_posts() yielded no post objects!")
        return False

    # define criteria for post selection
    max_text_len = 2000
    min_text_len = 600

    # select a post that hasnt been used, and fits criteria
    post_history_module = PostUsageHistory()
    while 1:
        random_post = random.choice(all_posts)
        post_data = random_post.to_dict()

        # make sure post has valid text size
        text_len = len(post_data["content"])
        if text_len < min_text_len or text_len > max_text_len:
            all_posts.remove(random_post)
            continue

        # make sure post is new
        post_url = post_data["url"]
        if post_history_module.post_exists(post_url):
            all_posts.remove(random_post)
            continue

        # if we got here, we have a valid post
        post_history_module.add_post(post_url)
        break

    

    #narrate the post
    content_to_narrate = f"{post_data['title']}. {post_data['content']}"
    narration_file_path, narration_duration = narrate(
        "jf_alpha", content_to_narrate)
    
    #extract a slop video as background
    print(f"Extracting a slop video for the post...")
    slop_extractor = Extractor()
    slop_video_file_path = r"temp/slop_video.mp4"
    slop_extractor.get_random_sludge_video(
        narration_duration,
        slop_video_file_path,
        VIDEO_DIMS,
    )

    #transcribe the narration
    transcriber = Transcriber()
    transcript = transcriber.transcribe_to_srt(audio_path=narration_file_path)

    #generate captions for this video
    word_timestamps = extract_word_timestamps_from_transcript(transcript)
    frames = generate_caption_frames(
        word_timestamps, max_group_duration=2.5, max_words=5
    )
    captioned_video_path = "captioned_output.mp4"
    caption_video(slop_video_file_path, frames, out_video_path=captioned_video_path)
    
    #add narration
    narrated_captioned_video_path = "narrated_captioned_output.mp4"
    add_audio_to_video(
        captioned_video_path, narration_file_path, narrated_captioned_video_path
    )
    print(f'Created a narrated captioned video at {narrated_captioned_video_path}')


# main entry point functions
def create_all_stacked_reddit_scroll_videos(output_dir="final_vids", stop_flag=None, register_thread_callback=None):
    """
    Main entry point for video generation.

    Args:
        output_dir: Directory to save final videos
        stop_flag: Threading event to signal stop
        register_thread_callback: Optional callback to register child threads for GUI output routing
    """
    while True:
        if stop_flag and stop_flag.is_set():
            print("[!] Stop flag detected, stopping video generation...")
            break
        try:
            print("="*70)
            print("STARTING NEW VIDEO CREATION")
            print("="*70)

            video_start = time.time()

            # Steps 1-2: Get post data and image (must complete before parallelization)
            post_image_save_path, post_data = prepare_post_data(output_dir)
            if post_image_save_path is None:
                print("[!] No more usable posts available. Stopping video generation.")
                break

            if stop_flag and stop_flag.is_set():
                break

            if PARALLEL_METADATA_GENERATION:
                # Run video creation (steps 3-8) and metadata generation in parallel
                narrated_video_path = None
                metadata_dict = None

                def video_task():
                    if register_thread_callback:
                        register_thread_callback()
                    return create_video_from_post(post_image_save_path, post_data)

                def metadata_task():
                    if register_thread_callback:
                        register_thread_callback()
                    print(f"[9] Generating metadata (parallel)...")
                    t = time.time()
                    result = create_metadata(post_data["title"], post_data["content"], post_data.get("url"))
                    print(f"[9] Metadata done ({time.time()-t:.1f}s)")
                    return result

                with ThreadPoolExecutor(max_workers=2) as executor:
                    video_future = executor.submit(video_task)
                    metadata_future = executor.submit(metadata_task)

                    # Wait for both to complete
                    narrated_video_path = video_future.result()
                    metadata_dict = metadata_future.result()

                total_time = time.time() - video_start
                print(f"[SUCCESS] Video created in {total_time:.1f}s (parallel mode)")

            else:
                # Sequential execution (original behavior)
                narrated_video_path = create_video_from_post(post_image_save_path, post_data)

                total_time = time.time() - video_start
                print(f"[SUCCESS] Video created in {total_time:.1f}s")

                if stop_flag and stop_flag.is_set():
                    break

                print(f"[9] Generating metadata...")
                t = time.time()
                metadata_dict = create_metadata(post_data["title"], post_data["content"], post_data.get("url"))
                print(f"[9] Done ({time.time()-t:.1f}s)")

            # Add scores to metadata
            scores = post_data.get("scores")
            if scores:
                metadata_dict.update(scores)

            compile_video_and_metadata(narrated_video_path, metadata_dict, output_dir)
            cleanup_temp_files()
        except Exception as e:
            print(f"[!] Error creating video: {e}")
            break


if __name__ == "__main__":
    create_slop_with_captions_video()
