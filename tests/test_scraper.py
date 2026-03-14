#!/usr/bin/env python3
"""
Test script for the Reddit scraper.
Run from project root: poetry run python tests/test_scraper.py [thread_count]
"""

import sys
import os
import signal
import threading
import random
import argparse
import time

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.scraper.scraper import RedditScraper

# Track spawned scraper instances for cleanup
_active_stop_flag = threading.Event()

def signal_handler(sig, frame):
    print("\n[!] Interrupted, signaling scrapers to stop...")
    _active_stop_flag.set()
    sys.exit(0)

signal.signal(signal.SIGINT, signal_handler)
signal.signal(signal.SIGTERM, signal_handler)


ALL_SUBREDDITS = [
    "https://www.reddit.com/r/tifu/",
    "https://www.reddit.com/r/AmItheAsshole/",
    "https://www.reddit.com/r/pettyrevenge/",
    "https://www.reddit.com/r/ProRevenge/",
    "https://www.reddit.com/r/raisedbynarcissists/",
    "https://www.reddit.com/r/confession/",
    "https://www.reddit.com/r/offmychest/",
    "https://www.reddit.com/r/MaliciousCompliance/",
    "https://www.reddit.com/r/karen/",
    "https://www.reddit.com/r/TalesFromRetail/",
]


def test_scraper(thread_count: int, posts_per_thread: int):
    # Randomly select subreddits
    selected = random.sample(ALL_SUBREDDITS, min(thread_count, len(ALL_SUBREDDITS)))

    print(f"Testing scraper with {len(selected)} subreddit(s), {posts_per_thread} posts each")
    print(f"Selected subreddits: {', '.join(s.split('/r/')[1].rstrip('/') for s in selected)}")
    print("=" * 60)

    total_success = 0
    total_failed = 0

    for thread_url in selected:
        if _active_stop_flag.is_set():
            print("[!] Stop flag detected, exiting...")
            break

        subreddit_name = thread_url.split('/r/')[1].rstrip('/')
        print(f"\n--- Scraping r/{subreddit_name} ---")

        scraper = None
        try:
            scraper = RedditScraper(stop_flag=_active_stop_flag)

            # Get post links
            post_links = scraper.get_posts(thread_url, max_posts=posts_per_thread)[:posts_per_thread]
            print(f"Found {len(post_links)} post links")

            random.shuffle(post_links)

            for i, post_link in enumerate(post_links):
                if _active_stop_flag.is_set():
                    break

                post = scraper.get_post_content(post_link)

                if post is not None and post.content:
                    total_success += 1
                    print(f"  [SUCCESS] Post {i+1}/{len(post_links)}")
                    print(f"    Title: {post.title[:60] if post.title else 'N/A'}...")
                    print(f"    Author: u/{post.username}")
                    print(f"    Content length: {len(post.content)} chars")
                    print(f"    URL: {post.url}")
                else:
                    total_failed += 1
                    print(f"  [FAILED] Post {i+1}/{len(post_links)} - Could not extract content")

                # Small delay between posts
                time.sleep(random.uniform(2, 5))

        except Exception as e:
            print(f"[ERROR] Failed to scrape r/{subreddit_name}: {e}")
            total_failed += 1
        finally:
            if scraper:
                scraper.close()

    print("\n" + "=" * 60)
    print("TEST RESULTS")
    print("=" * 60)
    print(f"  Successful: {total_success}")
    print(f"  Failed: {total_failed}")
    print(f"  Total: {total_success + total_failed}")
    if total_success + total_failed > 0:
        print(f"  Success rate: {total_success / (total_success + total_failed) * 100:.1f}%")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test Reddit scraper")
    parser.add_argument("--threads", "-t", type=int, default=1,
                        help="Number of subreddits to scrape (default: 1)")
    parser.add_argument("--posts", "-p", type=int, default=3,
                        help="Posts per subreddit (default: 3)")
    args = parser.parse_args()

    test_scraper(args.threads, args.posts)
