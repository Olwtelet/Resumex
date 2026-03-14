"""
Prompt Fine Tuner - Quickly test metadata generation prompts against real posts.

Loads reddit posts, generates titles + descriptions using the current prompts
in metadata_generator.py, and prints everything side-by-side for easy comparison.

Usage:
    poetry run python src/metadata/prompt_fine_tuner.py
    poetry run python src/metadata/prompt_fine_tuner.py --count 5
    poetry run python src/metadata/prompt_fine_tuner.py --seed 123
"""

import argparse
import io
import json
import os
import random
import sys


def get_test_posts(count=10, seed=42):
    """Load a random sample of reddit posts, skipping empty content."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    reddit_data_dir = os.path.join(project_root, "reddit_data")
    files = [f for f in os.listdir(reddit_data_dir) if f.endswith(".json")]

    # Load all posts, filter out empty content
    all_posts = []
    for filename in files:
        filepath = os.path.join(reddit_data_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            post = json.load(f)
            if post.get("content", "").strip():
                all_posts.append(post)

    random.seed(seed)
    return random.sample(all_posts, min(count, len(all_posts)))


def main():
    # Fix Windows console encoding
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Test metadata generation prompts")
    parser.add_argument("-c", "--count", type=int, default=10, help="Number of posts to test (default: 10)")
    parser.add_argument("-s", "--seed", type=int, default=42, help="Random seed for post selection (default: 42)")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output file path for results")
    args = parser.parse_args()

    # Import after argparse so --help is fast
    from metadata_generator import generate_title, generate_description, OLLAMA_MODEL

    posts = get_test_posts(count=args.count, seed=args.seed)

    results = []
    print(f"Model: {OLLAMA_MODEL}")
    print(f"Posts: {len(posts)} (seed={args.seed})")
    print("=" * 70)

    for i, post in enumerate(posts):
        print(f"\n{'=' * 70}")
        print(f"POST {i+1}/{len(posts)}")
        print(f"{'=' * 70}")
        print(f"Subreddit: r/{post['thread_name']}")
        print(f"Original Title: {post['title']}")
        print(f"Content ({len(post['content'])} chars):")
        print(f"  {post['content'][:300]}{'...' if len(post['content']) > 300 else ''}")

        print(f"\n--- Generated ---")
        title = generate_title(post["title"], post["content"])
        print(f"Title: {title}")

        description = generate_description(post["title"], post["content"])
        print(f"Description:\n  {description}")

        results.append({
            "subreddit": post["thread_name"],
            "original_title": post["title"],
            "content_preview": post["content"][:300],
            "generated_title": title,
            "generated_description": description,
        })

    print(f"\n{'=' * 70}")
    print("DONE")
    print(f"{'=' * 70}")

    output_path = args.output
    if not output_path:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fine_tuner_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"Results saved to: {output_path}")


if __name__ == "__main__":
    main()
