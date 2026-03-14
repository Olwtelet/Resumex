"""
Metadata Generator Benchmarking Script.

Tests multiple Ollama models against the same Reddit posts to compare
title and description generation quality.

Usage:
    poetry run python src/metadata/benchmarking.py
"""

import json
import os
import random
import time
import subprocess

# Models to benchmark (will be pulled if not available)
MODELS = [
    "qwen2.5:7b",
    "qwen2.5:14b",
    "llama3.1:8b",
    "mistral:7b",
    "gemma2:9b",
    "phi3:medium",
]

# Number of reddit posts to test each model on
NUM_TEST_POSTS = 5

# Prompts to test
TITLE_PROMPT = """Generate a YouTube Shorts title for this Reddit story.
Rules:
- Maximum 10 words
- MUST be first-person (use "I" or "My")
- Make it catchy and engaging
- No quotes around the title
- Just output the title, nothing else

Good examples: "I Caught My Boss Lying to HR", "My Neighbor Finally Got What He Deserved"
Bad examples: "Man Catches Boss", "This Person's Neighbor Story"

Reddit post title: {title}
Reddit post content: {content}

Title:"""

DESCRIPTION_PROMPT = """Write a YouTube Shorts description for this Reddit story.
Rules:
- Write in first-person (use "I", "My", "Me")
- Start with a 1-2 sentence hook that makes people want to watch
- Add 5 relevant hashtags at the end
- Keep the total under 150 words
- Do NOT fabricate details not in the original story
- Just output the description, nothing else

Reddit post title: {title}
Reddit post content: {content}

Description:"""


def get_test_posts(reddit_data_dir="reddit_data", count=NUM_TEST_POSTS):
    """Load a random sample of reddit posts for benchmarking, skipping empty content."""
    files = [f for f in os.listdir(reddit_data_dir) if f.endswith(".json")]

    all_posts = []
    for filename in files:
        filepath = os.path.join(reddit_data_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            post = json.load(f)
            if post.get("content", "").strip():
                all_posts.append(post)

    random.seed(42)  # Fixed seed for reproducibility
    return random.sample(all_posts, min(count, len(all_posts)))


def ensure_model_available(model_name):
    """Pull model if not already available."""
    result = subprocess.run(
        ["ollama", "list"],
        capture_output=True, text=True
    )
    if model_name.split(":")[0] in result.stdout:
        # Check exact tag
        for line in result.stdout.strip().split("\n"):
            if line.startswith(model_name):
                print(f"  [OK] {model_name} already available")
                return True

    print(f"  [PULL] Downloading {model_name}...")
    pull_result = subprocess.run(
        ["ollama", "pull", model_name],
        capture_output=False
    )
    return pull_result.returncode == 0


def query_ollama(model_name, prompt, timeout=120):
    """Query an Ollama model and return the response + timing."""
    start_time = time.time()
    try:
        result = subprocess.run(
            ["ollama", "run", model_name, prompt],
            capture_output=True, text=True, timeout=timeout,
            encoding="utf-8", errors="replace"
        )
        elapsed = time.time() - start_time
        if result.returncode != 0:
            return None, elapsed, result.stderr
        return result.stdout.strip(), elapsed, None
    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        return None, elapsed, "TIMEOUT"


def run_benchmark():
    """Run the full benchmark suite."""
    print("=" * 60)
    print("METADATA GENERATOR BENCHMARK")
    print("=" * 60)

    # Load test posts
    print("\n[1] Loading test posts...")
    posts = get_test_posts()
    print(f"    Loaded {len(posts)} posts for testing")
    for i, post in enumerate(posts):
        print(f"    Post {i+1}: r/{post['thread_name']} - {post['title'][:50]}...")

    results = {
        "test_posts": [
            {"title": p["title"], "content": p["content"][:200] + "...", "thread": p["thread_name"]}
            for p in posts
        ],
        "models": {}
    }

    # Test each model
    for model_idx, model_name in enumerate(MODELS):
        print(f"\n{'=' * 60}")
        print(f"[{model_idx+1}/{len(MODELS)}] Testing model: {model_name}")
        print("=" * 60)

        # Ensure model is available
        if not ensure_model_available(model_name):
            print(f"  [SKIP] Could not pull {model_name}")
            results["models"][model_name] = {"error": "could not pull model"}
            continue

        model_results = {
            "titles": [],
            "descriptions": [],
            "avg_title_time": 0,
            "avg_desc_time": 0,
        }

        title_times = []
        desc_times = []

        for post_idx, post in enumerate(posts):
            print(f"\n  --- Post {post_idx+1}/{len(posts)}: {post['title'][:40]}... ---")

            # Truncate content for prompt (avoid overwhelming small models)
            content = post["content"][:1500]

            # Generate title
            title_prompt = TITLE_PROMPT.format(title=post["title"], content=content)
            print(f"  Generating title...")
            title_output, title_time, title_err = query_ollama(model_name, title_prompt)
            title_times.append(title_time)

            if title_err:
                print(f"  [ERR] Title generation failed: {title_err}")
                title_output = f"ERROR: {title_err}"
            else:
                print(f"  Title ({title_time:.1f}s): {title_output[:80]}")

            # Generate description
            desc_prompt = DESCRIPTION_PROMPT.format(title=post["title"], content=content)
            print(f"  Generating description...")
            desc_output, desc_time, desc_err = query_ollama(model_name, desc_prompt)
            desc_times.append(desc_time)

            if desc_err:
                print(f"  [ERR] Description generation failed: {desc_err}")
                desc_output = f"ERROR: {desc_err}"
            else:
                print(f"  Description ({desc_time:.1f}s): {desc_output[:80]}...")

            model_results["titles"].append({
                "post_title": post["title"],
                "generated_title": title_output,
                "time_seconds": round(title_time, 2),
            })
            model_results["descriptions"].append({
                "post_title": post["title"],
                "generated_description": desc_output,
                "time_seconds": round(desc_time, 2),
            })

        model_results["avg_title_time"] = round(sum(title_times) / len(title_times), 2) if title_times else 0
        model_results["avg_desc_time"] = round(sum(desc_times) / len(desc_times), 2) if desc_times else 0
        results["models"][model_name] = model_results

        print(f"\n  Summary for {model_name}:")
        print(f"    Avg title gen time: {model_results['avg_title_time']}s")
        print(f"    Avg desc gen time:  {model_results['avg_desc_time']}s")

    # Write results
    output_path = "src/metadata/benchmark_results.json"
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)

    print(f"\n{'=' * 60}")
    print(f"BENCHMARK COMPLETE")
    print(f"Results written to: {os.path.abspath(output_path)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    run_benchmark()
