<div align="center">

# ⚡ Resumex

### Intelligent Reddit Content → Viral Video Automation Engine

Transform Reddit discussions into **viral short-form videos automatically**.

<br>

<img src="https://readme-typing-svg.herokuapp.com?size=32&duration=3000&color=6A5ACD&center=true&vCenter=true&width=900&lines=Reddit+Scraper;Short+Video+Automation;YouTube+Shorts+Generator;AI+Content+Pipeline" />

<br>

![Stars](https://img.shields.io/github/stars/username/resumex)
![Forks](https://img.shields.io/github/forks/username/resumex)
![Issues](https://img.shields.io/github/issues/username/resumex)
![Python](https://img.shields.io/badge/Python-3.10+-blue)
![Automation](https://img.shields.io/badge/Automation-Selenium-green)
![Video](https://img.shields.io/badge/Video-MoviePy-orange)

⭐ **If you like this project consider giving it a star!**

</div>

---

# 🚀 Overview

**Resumex** is a Python automation pipeline that converts Reddit posts into short-form social media videos.

The system automatically:

• Scrapes Reddit posts
• Detects viral potential
• Converts posts into scripts
• Generates voice narration
• Builds vertical videos
• Uploads content to YouTube

Perfect for building **Reddit storytelling channels and automated content pipelines.**

---

# 🔥 Why Resumex

Producing viral short-form content manually takes hours.

Resumex automates the entire pipeline:

```text
Reddit Scraping
      ↓
Content Analysis
      ↓
Viral Ranking
      ↓
Script Generation
      ↓
Text-To-Speech
      ↓
Video Rendering
      ↓
YouTube Upload
```

Result:

• scalable content production
• automated video creation
• faster social media growth

---

# 📸 Preview

<img width="988" height="772" src="https://github.com/user-attachments/assets/ba10748b-ad26-413f-99ed-0b58262a484d"/>

<br>

<img width="1637" height="588" src="https://github.com/user-attachments/assets/0cba412b-022c-4a39-9542-f9122d55a692"/>

<br>

<img width="249" height="377" src="https://github.com/user-attachments/assets/4b3f372b-6d7f-4dfb-b44d-175e226d5554"/>

<img width="254" height="380" src="https://github.com/user-attachments/assets/98d48c65-a984-499c-bdb5-daee0e7f4e95"/>

<img width="250" height="379" src="https://github.com/user-attachments/assets/d2020f8a-174e-4c44-a13e-b4f3999ccd09"/>

---

# ⚡ Quick Start

Clone the repository

```bash
git clone https://github.com/username/resumex.git
cd resumex
```

Create virtual environment

```bash
python -m venv venv
```

Activate

Windows

```bash
venv\Scripts\activate
```

Linux / Mac

```bash
source venv/bin/activate
```

Install dependencies

```bash
pip install -r requirements.txt
```

Run automation pipeline

```bash
python main.py
```

---

# 📦 Requirements

```
selenium
moviepy
gtts
pydub
praw
opencv-python
numpy
google-api-python-client
```

---

# 🧩 Project Structure

```
resumex
│
├── scraper
│   ├── reddit_scraper.py
│   └── post_parser.py
│
├── analyzer
│   ├── viral_score.py
│   └── engagement_engine.py
│
├── generator
│   ├── script_builder.py
│   └── tts_engine.py
│
├── video
│   ├── video_builder.py
│   └── subtitle_renderer.py
│
├── upload
│   └── youtube_uploader.py
│
├── assets
│   ├── gameplay
│   └── fonts
│
└── main.py
```

---

# 🔎 Example Reddit Scraper

```python
from selenium import webdriver
from selenium.webdriver.common.by import By
import time

driver = webdriver.Chrome()

driver.get("https://www.reddit.com/r/AskReddit")

time.sleep(5)

posts = driver.find_elements(By.CSS_SELECTOR,"h3")

for post in posts[:10]:
    print(post.text)

driver.quit()
```

---

# 📊 Viral Scoring Algorithm

```python
def calculate_viral_score(upvotes, comments, awards):

    score = (
        upvotes * 0.6 +
        comments * 0.3 +
        awards * 0.1
    )

    if score > 5000:
        return "HIGH"

    elif score > 1000:
        return "MEDIUM"

    return "LOW"
```

---

# 📝 Script Generator

```python
def generate_script(title, body):

    script = f"""
    Reddit story time.

    {title}

    {body}

    What would you do in this situation?
    """

    return script
```

---

# 🔊 Text-To-Speech

```python
from gtts import gTTS

def generate_voice(script):

    tts = gTTS(script)
    tts.save("audio/output.mp3")
```

---

# 🎬 Video Generation

```python
from moviepy.editor import *

background = VideoFileClip("assets/gameplay.mp4").subclip(0,60)

audio = AudioFileClip("audio/output.mp3")

video = background.set_audio(audio)

video.write_videofile(
    "output/video.mp4",
    fps=30,
    codec="libx264"
)
```

---

# 📡 YouTube Upload

```python
from googleapiclient.discovery import build

youtube = build("youtube","v3",developerKey="API_KEY")

request = youtube.videos().insert(
    part="snippet,status",
    body={
        "snippet":{
            "title":"Reddit Story",
            "description":"Generated with Resumex"
        },
        "status":{
            "privacyStatus":"public"
        }
    }
)
```

---

# ⚙️ Configuration

Example `config.json`

```json
{
 "subreddits":[
   "AskReddit",
   "AmItheAsshole",
   "TrueOffMyChest"
 ],
 "posts_per_run":5,
 "voice":"female",
 "background":"minecraft",
 "upload":true
}
```

---

# 💡 Use Cases

Resumex can be used for:

• YouTube Shorts automation
• TikTok storytelling channels
• Reddit content creators
• automated media pipelines
• viral content research

---

# 📈 Roadmap

Planned features:

• GPT-powered script summarization
• TikTok auto uploader
• automatic subtitles
• AI thumbnail generator
• trend prediction engine

---

# ⭐ Support

If you find **Resumex** useful:

⭐ Star the repository
🍴 Fork the project
🚀 Share it with other developers

```
Automation + AI + Content = Resumex
```
