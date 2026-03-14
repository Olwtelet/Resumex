import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.reddit_post_image.post_image_maker import make_reddit_post_image

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
OUTPUT_PATH = os.path.join(TEST_DIR, "test_static_reddit_post.png")

result = make_reddit_post_image(
    thread="r/confession",
    title_text="I abruptly quit my job because I realized no one would notice",
    body_text="I worked at this company for 3 years. Every single day I showed up on time, did my work, helped others when they needed it. Not once did I get a thank you. Not once did anyone ask how I was doing. Last Tuesday I just didn't show up. I turned off my phone and waited. It took them 4 days to even send me an email. Four days. That's when I knew I made the right choice. I'm not going back. I deserve to be somewhere where people actually see me. It hurts but it also feels like the biggest relief I've ever felt in my life. I'm done being invisible.",
    username="throwaway82849",
    expected_width=360,
    save=False,
)

if result:
    result.save(OUTPUT_PATH)
    print(f"Image saved: {OUTPUT_PATH}")
else:
    print("Failed to create image")
