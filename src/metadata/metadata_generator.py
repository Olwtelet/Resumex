"""
Metadata Generator - Generates YouTube titles and descriptions from Reddit posts.

Uses gemma2:9b via Ollama for generation.
"""

import json
import re
import urllib.request
import urllib.error


OLLAMA_MODEL = "gemma2:9b"
OLLAMA_URL = "http://localhost:11434/api/generate"

TITLE_PROMPT = """Generate a YouTube Shorts title for this Reddit story.
The story is told from the perspective of the Reddit poster (OP).
Rules:
- Maximum 10 words
- The title MUST start with "I" or "My" (from OP's perspective)
- Reference the specific conflict, event, or outcome
- No quotes around the title
- Be accurate - the title should reflect what OP did or experienced
- Just output the title, nothing else

Good: "I Caught My Boss Lying to HR", "My Neighbor Finally Got What He Deserved"
Bad: "Man Catches Boss", "Elderly Customer Throws Tantrum", "My Encounter Ended Badly"

Reddit post title: {title}
Reddit post content: {content}

Title:"""

DESCRIPTION_PROMPT = """Write a YouTube Shorts description for this Reddit story.
Rules:
- Write in first-person (use "I", "My", "Me")
- Write exactly 2 short sentences that tease the story
- End with 3-5 hashtags (no spaces in hashtags)
- Only state facts from the post - never invent details
- Never use question marks
- Just output the description, nothing else

Reddit post title: {title}
Reddit post content: {content}

Description:"""


def _query_ollama(prompt, timeout=300):
    """Query the Ollama model via REST API with CPU-only inference."""
    payload = json.dumps({
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
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
            return result["response"].strip()
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", errors="replace") if e.fp else ""
        raise RuntimeError(f"Ollama HTTP {e.code}: {body}")
    except urllib.error.URLError as e:
        raise RuntimeError(f"Ollama connection error: {e}")
    except Exception as e:
        raise RuntimeError(f"Ollama error: {e}")


def _normalize_typography(text: str) -> str:
    """Convert fancy typography to ASCII equivalents."""
    replacements = {
        '\u2019': "'",
        '\u2018': "'",
        '\u201c': '"',
        '\u201d': '"',
        '\u2014': '-',
        '\u2013': '-',
        '\u2026': '...',
    }
    for char, replacement in replacements.items():
        text = text.replace(char, replacement)
    return text


def _strip_emojis(text: str) -> str:
    """Remove emojis and surrogate pairs while preserving normal text."""
    text = _normalize_typography(text)
    emoji_pattern = re.compile(
        "["
        "\U0001F600-\U0001F64F"
        "\U0001F300-\U0001F5FF"
        "\U0001F680-\U0001F6FF"
        "\U0001F1E0-\U0001F1FF"
        "\U00002702-\U000027B0"
        "\U000024C2-\U0001F251"
        "\U0001F900-\U0001F9FF"
        "\U0001FA00-\U0001FA6F"
        "\U0001FA70-\U0001FAFF"
        "\U00002600-\U000026FF"
        "\U00002700-\U000027BF"
        "\U0001F000-\U0001F02F"
        "\U0001F0A0-\U0001F0FF"
        "\ud800-\udfff"
        "\uac00-\ud7af"
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub("", text)


def _clean_output(text: str, is_description: bool = False) -> str:
    """Clean up model output."""
    text = text.strip()
    # Remove quotes
    if text.startswith('"') and text.endswith('"'):
        text = text[1:-1]
    if text.startswith("'") and text.endswith("'"):
        text = text[1:-1]
    # Remove prefix labels
    text = re.sub(r'^(Title|Description):\s*', '', text, flags=re.IGNORECASE)
    # Strip emojis
    text = _strip_emojis(text)
    # Remove markdown bold formatting
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    # Remove "Hook:" and "Hashtags:" labels
    text = re.sub(r'^Hook:\s*', '', text, flags=re.IGNORECASE | re.MULTILINE)
    text = re.sub(r'\nHashtags?:\s*', '\n', text, flags=re.IGNORECASE)
    # Remove text within brackets [like this]
    text = re.sub(r'\[[^\]]*\]', '', text)
    # Remove escaped quotes
    text = text.replace('\\"', ' ')
    # Remove remaining standalone quotes
    text = text.replace('"', '')

    if is_description:
        lines = [re.sub(r'\s+', ' ', line).strip() for line in text.split('\n')]
        text = '\n'.join(line for line in lines if line)
    else:
        text = re.sub(r'\s+', ' ', text)

    return text.strip()


def generate_title(post_title: str, post_content: str) -> str:
    """Generate a YouTube title from Reddit post content."""
    prompt = TITLE_PROMPT.format(title=post_title, content=post_content[:1500])
    raw_output = _query_ollama(prompt)
    # Take only first line for title
    title = _clean_output(raw_output.split("\n")[0])
    return title


def generate_description(post_title: str, post_content: str) -> str:
    """Generate a YouTube description from Reddit post content."""
    prompt = DESCRIPTION_PROMPT.format(title=post_title, content=post_content[:1500])
    raw_output = _query_ollama(prompt)
    description = _clean_output(raw_output, is_description=True)
    return description


def generate_metadata(post_title: str, post_content: str) -> dict:
    """
    Generate complete YouTube metadata (title + description) from Reddit post.

    Args:
        post_title: The Reddit post title
        post_content: The Reddit post body content

    Returns:
        dict with 'title' and 'description' keys
    """
    title = generate_title(post_title, post_content)
    description = generate_description(post_title, post_content)

    return {
        "title": title,
        "description": description,
    }
