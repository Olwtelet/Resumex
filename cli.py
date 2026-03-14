#!/usr/bin/env python3
"""
CLI interface for Slop Media Machine.
Provides the same operations as the GUI but via command line.
"""

import argparse
import json
import os
import shutil
import sys
import threading
import subprocess

from src.scraper.scraper import scrape_all_threads
from video_maker import create_all_stacked_reddit_scroll_videos
from src.youtube.youtube_upload import (
    YoutubeUploader,
    YoutubePostHistoryManager,
    extract_metadata_from_folder,
)

with open("config/reddit_threads.json", "r") as f:
    SUBREDDITS = json.load(f)


def get_stats():
    """Get current stats about scraped posts, videos, and uploads."""
    scraped_posts_folder = "reddit_data"
    final_videos_folder = "final_vids"
    youtube_history_file = "data/youtube_post_history.txt"

    scraped_posts_count = (
        len(os.listdir(scraped_posts_folder))
        if os.path.exists(scraped_posts_folder)
        else 0
    )
    final_videos_count = (
        len(os.listdir(final_videos_folder))
        if os.path.exists(final_videos_folder)
        else 0
    )
    youtube_uploads_count = 0
    if os.path.exists(youtube_history_file):
        with open(youtube_history_file, "r") as f:
            content = f.read().strip()
            if content:
                youtube_uploads_count = len([line for line in content.split("\n") if line])

    return {
        "posts_scraped": scraped_posts_count,
        "videos_created": final_videos_count,
        "youtube_uploads": youtube_uploads_count,
    }


def cmd_stats(args):
    """Display current stats."""
    stats = get_stats()
    print("\n=== Slop Media Machine Stats ===")
    print(f"Posts Scraped:    {stats['posts_scraped']}")
    print(f"Videos Created:   {stats['videos_created']}")
    print(f"YouTube Uploads:  {stats['youtube_uploads']}")
    print()


def cmd_scrape(args):
    """Scrape Reddit for storytelling content."""
    print("\n" + "=" * 50)
    print("STARTING REDDIT SCRAPER")
    print("=" * 50)
    print(f"Total posts to scrape: {args.count}")

    stop_flag = threading.Event()
    try:
        scrape_all_threads(SUBREDDITS, args.count, stop_flag)
        print("=" * 50)
        print("SCRAPING COMPLETE")
        print("=" * 50 + "\n")
    except KeyboardInterrupt:
        stop_flag.set()
        print("\nScraping interrupted by user.")
    except Exception as e:
        print(f"ERROR: {e}")


def cmd_make(args):
    """Generate videos from scraped posts."""
    print("=" * 50)
    print("STARTING VIDEO GENERATION")
    print("=" * 50)
    if args.count:
        print(f"Creating {args.count} videos...")
    else:
        print("Creating videos continuously (Ctrl+C to stop)...")

    stop_flag = threading.Event()
    try:
        if args.count:
            from video_maker import create_stacked_reddit_scroll_video, create_metadata, compile_video_and_metadata, cleanup_temp_files
            for i in range(args.count):
                if stop_flag.is_set():
                    break
                print(f"\n--- Video {i+1} of {args.count} ---")
                result = create_stacked_reddit_scroll_video("final_vids")
                if result is False:
                    print("[!] No more usable posts available. Stopping.")
                    break
                narrated_video_path, post_data = result
                metadata_dict = create_metadata(post_data["title"], post_data["content"], post_data.get("url"))
                scores = post_data.get("scores")
                if scores:
                    metadata_dict.update(scores)
                compile_video_and_metadata(narrated_video_path, metadata_dict, "final_vids")
                cleanup_temp_files()
        else:
            create_all_stacked_reddit_scroll_videos(output_dir="final_vids", stop_flag=stop_flag)
        print("=" * 50)
        print("VIDEO GENERATION COMPLETE")
        print("=" * 50 + "\n")
    except KeyboardInterrupt:
        stop_flag.set()
        print("\nVideo generation interrupted by user.")
    except Exception as e:
        print(f"ERROR: {e}")


def cmd_upload(args):
    """Upload a video to YouTube."""
    post_history_module = YoutubePostHistoryManager()
    videos_folder = "final_vids"

    if not os.path.exists(videos_folder):
        print("ERROR: final_vids folder not found")
        return

    all_subfolders = os.listdir(videos_folder)

    # filter to unposted videos by checking reddit_url in metadata
    unposted_subfolders = []
    for subfolder in all_subfolders:
        subfolder_path = os.path.join(videos_folder, subfolder)
        metadata = extract_metadata_from_folder(subfolder_path)
        if metadata is False:
            continue
        reddit_url = metadata.get("reddit_url", "")
        if reddit_url and not post_history_module.post_exists(reddit_url):
            unposted_subfolders.append((subfolder, metadata))

    if not unposted_subfolders:
        print("No unposted videos found.")
        return

    print(f"\nFound {len(unposted_subfolders)} unposted videos out of {len(all_subfolders)} total")

    unposted_subfolders.sort(key=lambda x: x[1].get("repost_quality", 0), reverse=True)
    selected_subfolder, metadata = unposted_subfolders[0]
    selected_subfolder_path = os.path.join(videos_folder, selected_subfolder)
    video_path = os.path.join(selected_subfolder_path, "video.mp4")

    title = metadata["title"]
    description = metadata["description"]
    reddit_url = metadata.get("reddit_url", "")

    print("\n" + "=" * 50)
    print("VIDEO PREVIEW")
    print("=" * 50)
    print(f"Folder: {selected_subfolder}")
    print(f"Title: {title}")
    print(f"Description:\n{description}")
    print(f"Reddit URL: {reddit_url}")
    print("=" * 50)

    if not args.yes:
        confirm = input("\nUpload this video? [y/N]: ").strip().lower()
        if confirm != "y":
            print("Upload cancelled.")
            return

    print("\n" + "=" * 50)
    print("UPLOADING VIDEO TO YOUTUBE")
    print("=" * 50)

    try:
        uploader = YoutubeUploader()
        uploader.upload_video(title, description, video_path)

        if reddit_url:
            post_history_module.add_post(reddit_url)

        # Delete the video folder after successful upload
        shutil.rmtree(selected_subfolder_path)
        print(f"Deleted uploaded video folder: {selected_subfolder}")

        print("=" * 50)
        print("UPLOAD COMPLETE")
        print("=" * 50 + "\n")
    except Exception as e:
        print(f"ERROR: Upload failed - {e}")


def cmd_list(args):
    """List all videos and their upload status."""
    post_history_module = YoutubePostHistoryManager()
    videos_folder = "final_vids"

    if not os.path.exists(videos_folder):
        print("No videos folder found.")
        return

    all_subfolders = sorted(os.listdir(videos_folder))

    if not all_subfolders:
        print("No videos found.")
        return

    print("\n=== Video List ===")
    print(f"{'Folder':<15} {'Status':<10} {'Title':<50}")
    print("-" * 75)

    for subfolder in all_subfolders:
        subfolder_path = os.path.join(videos_folder, subfolder)
        metadata = extract_metadata_from_folder(subfolder_path)

        if metadata is False:
            print(f"{subfolder:<15} {'ERROR':<10} [Cannot read metadata]")
            continue

        reddit_url = metadata.get("reddit_url", "")
        if reddit_url and post_history_module.post_exists(reddit_url):
            status = "UPLOADED"
        elif not reddit_url:
            status = "NO URL"
        else:
            status = "PENDING"

        title = metadata.get("title", "[No title]")[:47]
        if len(metadata.get("title", "")) > 47:
            title += "..."

        print(f"{subfolder:<15} {status:<10} {title}")

    print()


def cmd_auth(args):
    """Reauthenticate YouTube credentials."""
    print("\n" + "=" * 50)
    print("STARTING YOUTUBE REAUTHENTICATION")
    print("=" * 50)
    print("A browser window will open for authentication...")

    auth_script_path = os.path.join("src", "youtube", "youtube_auth.py")

    try:
        result = subprocess.run(
            [sys.executable, auth_script_path],
            capture_output=False
        )

        if result.returncode == 0:
            print("=" * 50)
            print("AUTHENTICATION COMPLETE")
            print("=" * 50 + "\n")
        else:
            print("=" * 50)
            print("AUTHENTICATION FAILED")
            print("=" * 50 + "\n")
    except Exception as e:
        print(f"ERROR: Authentication failed - {e}")


def main():
    parser = argparse.ArgumentParser(
        description="Slop Media Machine CLI",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python cli.py stats              Show current stats
  python cli.py scrape             Scrape Reddit (default 100 posts total)
  python cli.py scrape -c 50       Scrape 50 posts total across all threads
  python cli.py make               Generate videos continuously
  python cli.py list               List all videos and upload status
  python cli.py upload             Select and upload the best-scored video
  python cli.py upload -y          Upload without confirmation
  python cli.py auth               Reauthenticate YouTube credentials
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # stats command
    stats_parser = subparsers.add_parser("stats", help="Display current stats")
    stats_parser.set_defaults(func=cmd_stats)

    # scrape command
    scrape_parser = subparsers.add_parser("scrape", help="Scrape Reddit for content")
    scrape_parser.add_argument(
        "-c", "--count", type=int, default=100,
        help="Total number of posts to scrape across all threads (default: 100)"
    )
    scrape_parser.set_defaults(func=cmd_scrape)

    # make command
    make_parser = subparsers.add_parser("make", help="Generate videos from scraped posts")
    make_parser.add_argument(
        "-c", "--count", type=int, default=None,
        help="Number of videos to create (default: unlimited)"
    )
    make_parser.set_defaults(func=cmd_make)

    # list command
    list_parser = subparsers.add_parser("list", help="List all videos and their status")
    list_parser.set_defaults(func=cmd_list)

    # upload command
    upload_parser = subparsers.add_parser("upload", help="Upload a video to YouTube")
    upload_parser.add_argument(
        "-y", "--yes", action="store_true",
        help="Skip confirmation prompt"
    )
    upload_parser.set_defaults(func=cmd_upload)

    # auth command
    auth_parser = subparsers.add_parser("auth", help="Reauthenticate YouTube credentials")
    auth_parser.set_defaults(func=cmd_auth)

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        return

    args.func(args)


if __name__ == "__main__":
    main()
