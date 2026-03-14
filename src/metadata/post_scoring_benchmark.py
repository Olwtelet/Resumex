"""
Post Scoring Benchmark - Scores Reddit posts on engagement, sentiment, and repost quality.

Uses gemma2:9b via Ollama with JSON mode to produce structured scores.

Usage:
    poetry run python src/metadata/post_scoring_benchmark.py
    poetry run python src/metadata/post_scoring_benchmark.py -c 20
    poetry run python src/metadata/post_scoring_benchmark.py -c 10 -s 123
"""

import argparse
import io
import json
import os
import random
import sys
import urllib.request
import urllib.error


OLLAMA_MODEL = "gemma2:9b"
OLLAMA_URL = "http://localhost:11434/api/generate"

SCORING_PROMPT = """Score this Reddit post for YouTube Shorts reposting potential.
Output a JSON object with exactly these three integer fields (1-10 each):

- "engagement": How controversial, dramatic, or attention-grabbing is this post? (1=boring/mundane, 10=extremely dramatic/spicy/hot-take)
- "sentiment": How emotionally charged is the writing? (1=calm/neutral/measured, 10=outraged/furious/explosive)
- "repost_quality": How much substantive first-person content is there to narrate in a video?
  1-3: no real content (link-only, podcast promo, one-liner, health tip, TV recommendation, or pure spam)
  4-5: very brief or vague personal content, or entirely second-hand/abstract
  6-7: decent first-person content with personal details and some situation described
  8-9: rich first-person narrative with detailed personal situation, conflict or drama, and emotional weight
  10: exceptional story - detailed, dramatic, emotionally compelling, with clear stakes

Output ONLY valid JSON, nothing else.

Reddit post title: {title}
Reddit post content: {content}"""


def query_ollama_json(prompt, timeout=300):
    """Query Ollama with JSON format enforcement."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
        "format": "json",
        "options": {
            "num_gpu": 0,
        },
    }).encode("utf-8")

    req = urllib.request.Request(
        OLLAMA_URL,
        data=payload,
        headers={"Content-Type": "application/json"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            response_text = result["response"].strip()
            return json.loads(response_text)
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(f"Ollama HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama connection error: {e}")
    except json.JSONDecodeError as e:
        raise RuntimeError(f"Failed to parse JSON from model: {e}")
    except Exception as e:
        raise RuntimeError(f"Ollama error: {e}")


def get_test_posts(count=10, seed=42):
    """Load a random sample of reddit posts, skipping empty content."""
    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    reddit_data_dir = os.path.join(project_root, "reddit_data")
    files = [f for f in os.listdir(reddit_data_dir) if f.endswith(".json")]

    all_posts = []
    for filename in files:
        filepath = os.path.join(reddit_data_dir, filename)
        with open(filepath, "r", encoding="utf-8") as f:
            post = json.load(f)
            if post.get("content", "").strip():
                all_posts.append(post)

    random.seed(seed)
    return random.sample(all_posts, min(count, len(all_posts)))


def validate_scores(scores):
    """Validate and clamp score values to 1-10 integers."""
    validated = {}
    for key in ("engagement", "sentiment", "repost_quality"):
        val = scores.get(key)
        if val is None:
            validated[key] = 5
        else:
            validated[key] = max(1, min(10, int(val)))
    return validated


def main():
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

    parser = argparse.ArgumentParser(description="Score Reddit posts for repost quality")
    parser.add_argument("-c", "--count", type=int, default=10, help="Number of posts to score (default: 10)")
    parser.add_argument("-s", "--seed", type=int, default=42, help="Random seed (default: 42)")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output file path")
    args = parser.parse_args()

    posts = get_test_posts(count=args.count, seed=args.seed)

    print(f"Model: {OLLAMA_MODEL} (JSON mode)")
    print(f"Posts: {len(posts)} (seed={args.seed})")
    print("=" * 70)

    results = []
    for i, post in enumerate(posts):
        print(f"\n{'=' * 70}")
        print(f"POST {i+1}/{len(posts)}")
        print(f"{'=' * 70}")
        print(f"Subreddit: r/{post['thread_name']}")
        print(f"Title: {post['title']}")
        print(f"Content ({len(post['content'])} chars): {post['content'][:200]}...")

        prompt = SCORING_PROMPT.format(
            title=post["title"],
            content=post["content"][:1500],
        )

        try:
            raw_scores = query_ollama_json(prompt)
            scores = validate_scores(raw_scores)
            print(f"  Engagement:     {scores['engagement']}/10")
            print(f"  Sentiment:      {scores['sentiment']}/10")
            print(f"  Repost Quality: {scores['repost_quality']}/10")
        except RuntimeError as e:
            print(f"  ERROR: {e}")
            scores = {"engagement": -1, "sentiment": -1, "repost_quality": -1}

        results.append({
            "subreddit": post["thread_name"],
            "title": post["title"],
            "content_preview": post["content"][:300],
            "content_length": len(post["content"]),
            "scores": scores,
        })

    print(f"\n{'=' * 70}")
    print("DONE")
    print(f"{'=' * 70}")

    # Summary stats
    scored = [r for r in results if r["scores"]["engagement"] != -1]
    if scored:
        avg_eng = sum(r["scores"]["engagement"] for r in scored) / len(scored)
        avg_sent = sum(r["scores"]["sentiment"] for r in scored) / len(scored)
        avg_qual = sum(r["scores"]["repost_quality"] for r in scored) / len(scored)
        print(f"\nAverages ({len(scored)} posts):")
        print(f"  Engagement:     {avg_eng:.1f}")
        print(f"  Sentiment:      {avg_sent:.1f}")
        print(f"  Repost Quality: {avg_qual:.1f}")

    output_path = args.output
    if not output_path:
        output_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "post_scoring_results.json")
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"\nResults saved to: {output_path}")


if __name__ == "__main__":
    main()
