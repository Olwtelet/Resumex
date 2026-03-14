#!/usr/bin/env python3
"""
Always-on automation script for the shortform sludge maker.

This script runs continuously and:
1. Scrapes more Reddit posts when running low on unused data
2. Creates videos when final_vids folder is low
3. Uploads videos to YouTube on a schedule (every ~5 hours)

Run with: poetry run python cron.py
"""

import os
import sys
import time
import signal
import threading
import random
import json
from datetime import datetime
from pathlib import Path

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.scraper.scraper import scrape_all_threads, DataSaver
from video_maker import (
    create_stacked_reddit_scroll_video,
    create_metadata,
    compile_video_and_metadata,
    PostUsageHistory,
)
from src.youtube.youtube_upload import (
    YoutubeUploader,
    YoutubePostHistoryManager,
    extract_metadata_from_folder,
)


# Configuration
LOGS_DIR = "logs"
MAX_LOGS = 10
FINAL_VIDS_DIR = "final_vids"
MIN_FINAL_VIDS = 3
MIN_UNUSED_POSTS = 10
POSTS_TO_SCRAPE_PER_RUN = 15
UPLOAD_INTERVAL_HOURS = 5
LOOP_SLEEP_SECONDS = 60

with open("config/reddit_threads.json", "r") as f:
    ALL_SUBREDDITS = json.load(f)

# Global stop flag
stop_flag = threading.Event()


def signal_handler(sig, frame):
    print("\n[CRON] Received shutdown signal, stopping gracefully...")
    stop_flag.set()


signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


class Logger:
    def __init__(self):
        os.makedirs(LOGS_DIR, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        self.log_path = os.path.join(LOGS_DIR, f"cron_{timestamp}.log")
        self._cleanup_old_logs()

    def _cleanup_old_logs(self):
        """Keep only the most recent MAX_LOGS log files."""
        log_files = sorted(Path(LOGS_DIR).glob("cron_*.log"), key=os.path.getmtime)
        while len(log_files) > MAX_LOGS - 1:  # -1 because we're about to create a new one
            oldest = log_files.pop(0)
            try:
                oldest.unlink()
                print(f"[CRON] Deleted old log: {oldest.name}")
            except Exception as e:
                print(f"[CRON] Failed to delete old log {oldest}: {e}")

    def log(self, message):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        formatted = f"[{timestamp}] {message}"
        print(formatted)
        try:
            with open(self.log_path, "a", encoding="utf-8") as f:
                f.write(formatted + "\n")
        except Exception as e:
            print(f"[CRON] Failed to write to log: {e}")


class StateManager:
    """Tracks state like last upload time."""

    def __init__(self):
        self.state_path = "data/cron_state.json"
        os.makedirs("data", exist_ok=True)
        self.state = self._load()

    def _load(self):
        if os.path.exists(self.state_path):
            try:
                with open(self.state_path, "r") as f:
                    return json.load(f)
            except:
                pass
        return {"last_upload_time": 0}

    def save(self):
        with open(self.state_path, "w") as f:
            json.dump(self.state, f, indent=2)

    def get_last_upload_time(self):
        return self.state.get("last_upload_time", 0)

    def set_last_upload_time(self, timestamp=None):
        if timestamp is None:
            timestamp = time.time()
        self.state["last_upload_time"] = timestamp
        self.save()


def count_unused_posts():
    """Count how many scraped posts haven't been used yet."""
    data_saver = DataSaver()
    all_posts = data_saver.get_all_posts()
    post_history = PostUsageHistory()
    used_urls = set(post_history.get_all_posts())

    unused_count = 0
    for post in all_posts:
        if post.url not in used_urls:
            unused_count += 1

    return unused_count, len(all_posts)


def count_unposted_videos():
    """Count videos in final_vids that haven't been uploaded yet."""
    if not os.path.exists(FINAL_VIDS_DIR):
        os.makedirs(FINAL_VIDS_DIR, exist_ok=True)
        return 0, 0

    post_history = YoutubePostHistoryManager()
    subfolders = [f for f in os.listdir(FINAL_VIDS_DIR)
                  if os.path.isdir(os.path.join(FINAL_VIDS_DIR, f))]

    unposted = 0
    for subfolder in subfolders:
        subfolder_path = os.path.join(FINAL_VIDS_DIR, subfolder)
        metadata = extract_metadata_from_folder(subfolder_path)
        if metadata is False:
            continue
        reddit_url = metadata.get("reddit_url", "")
        if reddit_url and not post_history.post_exists(reddit_url):
            unposted += 1

    return unposted, len(subfolders)


def run_scraper(logger):
    """Scrape posts distributed across all subreddits."""
    logger.log(f"[SCRAPER] Starting scrape of {POSTS_TO_SCRAPE_PER_RUN} posts across all subreddits")

    try:
        scrape_all_threads(ALL_SUBREDDITS, POSTS_TO_SCRAPE_PER_RUN, stop_flag)
        logger.log(f"[SCRAPER] Completed scrape run")
        return True
    except Exception as e:
        logger.log(f"[SCRAPER] Error: {e}")
        return False


def create_video(logger):
    """Create a single video."""
    logger.log("[VIDEO] Starting video creation...")

    try:
        result = create_stacked_reddit_scroll_video(FINAL_VIDS_DIR)
        if result is False:
            logger.log("[VIDEO] Failed to create video (no valid posts?)")
            return False

        video_path, post_data = result
        metadata = create_metadata(
            post_data["title"],
            post_data["content"],
            post_data.get("url")
        )
        compile_video_and_metadata(video_path, metadata, FINAL_VIDS_DIR)
        logger.log(f"[VIDEO] Created video for: {post_data['title'][:50]}...")
        return True
    except Exception as e:
        logger.log(f"[VIDEO] Error: {e}")
        return False


def upload_video(logger, state):
    """Upload a video to YouTube."""
    logger.log("[UPLOAD] Starting upload...")

    try:
        post_history = YoutubePostHistoryManager()
        subfolders = [f for f in os.listdir(FINAL_VIDS_DIR)
                      if os.path.isdir(os.path.join(FINAL_VIDS_DIR, f))]

        # Find unposted videos
        unposted = []
        for subfolder in subfolders:
            subfolder_path = os.path.join(FINAL_VIDS_DIR, subfolder)
            metadata = extract_metadata_from_folder(subfolder_path)
            if metadata is False:
                continue
            reddit_url = metadata.get("reddit_url", "")
            if reddit_url and not post_history.post_exists(reddit_url):
                unposted.append((subfolder_path, metadata))

        if not unposted:
            logger.log("[UPLOAD] No unposted videos available")
            return False

        # Select highest repost_quality video
        unposted.sort(key=lambda x: x[1].get("repost_quality", 0), reverse=True)
        selected_path, metadata = unposted[0]
        video_path = os.path.join(selected_path, "video.mp4")
        title = metadata["title"]
        description = metadata["description"]
        reddit_url = metadata.get("reddit_url", "")

        logger.log(f"[UPLOAD] Uploading: {title[:50]}...")

        uploader = YoutubeUploader()
        uploader.upload_video(title, description, video_path)

        if reddit_url:
            post_history.add_post(reddit_url)

        # Delete the folder after successful upload
        import shutil
        shutil.rmtree(selected_path)
        logger.log(f"[UPLOAD] Success! Deleted {os.path.basename(selected_path)}")

        state.set_last_upload_time()
        return True

    except Exception as e:
        logger.log(f"[UPLOAD] Error: {e}")
        return False


def main_loop():
    logger = Logger()
    state = StateManager()

    logger.log("=" * 60)
    logger.log("CRON JOB STARTED")
    logger.log("=" * 60)

    while not stop_flag.is_set():
        try:
            # Check status
            unused_posts, total_posts = count_unused_posts()
            unposted_vids, total_vids = count_unposted_videos()
            hours_since_upload = (time.time() - state.get_last_upload_time()) / 3600

            logger.log("-" * 40)
            logger.log(f"Status: {unused_posts}/{total_posts} unused posts, "
                      f"{unposted_vids}/{total_vids} unposted videos, "
                      f"{hours_since_upload:.1f}h since last upload")

            # 1. Need more reddit data?
            if unused_posts < MIN_UNUSED_POSTS:
                logger.log(f"[DECISION] Need more posts ({unused_posts} < {MIN_UNUSED_POSTS})")
                run_scraper(logger)
                if stop_flag.is_set():
                    break
                continue

            # 2. Need more videos?
            if unposted_vids < MIN_FINAL_VIDS:
                logger.log(f"[DECISION] Need more videos ({unposted_vids} < {MIN_FINAL_VIDS})")
                create_video(logger)
                if stop_flag.is_set():
                    break
                continue

            # 3. Time to upload?
            if hours_since_upload >= UPLOAD_INTERVAL_HOURS:
                logger.log(f"[DECISION] Time to upload ({hours_since_upload:.1f}h >= {UPLOAD_INTERVAL_HOURS}h)")
                upload_video(logger, state)
                if stop_flag.is_set():
                    break
                continue

            # Nothing to do, sleep
            next_upload_in = UPLOAD_INTERVAL_HOURS - hours_since_upload
            logger.log(f"[IDLE] All good. Next upload in ~{next_upload_in:.1f}h. Sleeping {LOOP_SLEEP_SECONDS}s...")
            time.sleep(LOOP_SLEEP_SECONDS)

        except Exception as e:
            logger.log(f"[ERROR] Main loop error: {e}")
            time.sleep(LOOP_SLEEP_SECONDS)

    logger.log("=" * 60)
    logger.log("CRON JOB STOPPED")
    logger.log("=" * 60)


if __name__ == "__main__":
    main_loop()
