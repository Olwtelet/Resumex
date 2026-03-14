"""Test narration generation. Picks a random sentence, generates audio, saves to tests/test_narration.wav."""

import sys
import os
import random
import shutil
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
os.chdir(PROJECT_ROOT)

from src.narration.narrarate import narrate

SENTENCES = [
    "I never thought my neighbor would go that far over a parking spot.",
    "The look on her face when I told her the truth was something I will never forget.",
    "After three years of silence, he finally called me back.",
    "I quit my job yesterday and I have never felt more alive in my entire life.",
    "She told me she loved me, but her actions said something completely different.",
    "The moment I walked through that door, I knew everything had changed forever.",
    "He spent six years planning the perfect revenge and it worked flawlessly.",
    "I found out my best friend had been lying to me for over a decade.",
    "Sometimes the smallest decisions lead to the biggest consequences in life.",
    "When the doctor gave me the results, I broke down crying in the waiting room.",
]

OUTPUT_PATH = os.path.join(PROJECT_ROOT, "tests", "test_narration.wav")


def main():
    sentence = random.choice(SENTENCES)
    print(f"Selected sentence: {sentence}")
    print(f"Generating narration...")

    t = time.time()
    audio_path, duration = narrate("jf_alpha", sentence)
    elapsed = time.time() - t

    shutil.move(audio_path, OUTPUT_PATH)

    print(f"Duration: {duration}s")
    print(f"Generation time: {elapsed:.1f}s")
    print(f"Saved to: {OUTPUT_PATH}")

    if os.path.exists(OUTPUT_PATH) and os.path.getsize(OUTPUT_PATH) > 0:
        print("PASSED")
    else:
        print("FAILED - output file missing or empty")


if __name__ == "__main__":
    main()
