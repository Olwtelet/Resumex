from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
import os
import json
import shutil


class YoutubeUploader:
    def __init__(self):
        # Load saved credentials
        if not os.path.exists("src/youtube/token.json"):
            raise FileNotFoundError("Google API Token file not found.")
        self.creds = Credentials.from_authorized_user_file(
            "src/youtube/token.json", ["https://www.googleapis.com/auth/youtube.upload"]
        )

    def upload_video(
        self,
        title,
        description,
        video_file_path,
    ):
        if not os.path.exists(video_file_path):
            raise FileNotFoundError(
                f"Cant upload video. Local file not found: {video_file_path}"
            )

        youtube = build("youtube", "v3", credentials=self.creds)

        request_body = {
            "snippet": {
                "title": title,
                "description": description,
                "tags": ["shorts"],
                "categoryId": "22",  # People & Blogs
            },
            "status": {
                "privacyStatus": "public",
                "selfDeclaredMadeForKids": False,
            },
        }

        media = MediaFileUpload(
            video_file_path,
            chunksize=-1,
            resumable=True,
        )

        request = youtube.videos().insert(
            part="snippet,status", body=request_body, media_body=media
        )

        response = request.execute()
        print("Video uploaded:", response["id"])


class YoutubePostHistoryManager:
    def __init__(self):
        self.fp = r"data/youtube_post_history.txt"
        if not os.path.exists(self.fp):
            with open(self.fp, "w") as f:
                f.write("")

    def add_post(self, reddit_url):
        with open(self.fp, "a") as f:
            f.write(f"{reddit_url}\n")

    def post_exists(self, reddit_url):
        with open(self.fp, "r") as f:
            content = f.read()
            return reddit_url in content.split("\n")


def extract_metadata_from_folder(video_subfolder_path):
    metadata_json_path = os.path.join(video_subfolder_path, "metadata.json")
    with open(metadata_json_path, "r") as f:
        metadata = json.load(f)
        if "title" not in metadata or "description" not in metadata:
            print(
                f"[!] Warning: this metadata.json file is missing title or description keys:\n{metadata_json_path}"
            )
            return False

    sanitized = sanitize_metadata(metadata)
    sanitized["reddit_url"] = metadata.get("reddit_url", "")
    sanitized["repost_quality"] = metadata.get("repost_quality", 0)
    return sanitized


def sanitize_metadata(metadata):
    def remove_chars(chars, string):
        for char in chars:
            string = string.replace(char, "")

        return string.strip()

    blacklist_chars = [
        "---",  # em dash sequence (YouTube titles usually use single dash)
        "{",
        "}",  # rarely seen in titles
        "<",
        ">",  # HTML-like symbols, never in titles
        "\\",  # backslash
        "|",  # pipe
        "@",  # used for mentions, but not title-safe
        "%",
        "^",
        "*",
        "+",
        "=",
        "`",
        "~",  # code/math/technical chars
        "—",
        "–",  # fancy em/en dashes
        "‘",
        "’",
        "“",
        "”",  # smart quotes
        "…",
        "«",
        '"',
        "»",
        "‹",
        "›",  # ellipsis, chevrons
        "•",
        "·",
        "°",  # bullets, degrees
        "  ",  # double space
        "\t",
        "\n",  # tabs and newlines
    ]

    new_data = {}
    title = metadata.get("title", "")
    description = metadata.get("description", "")
    title = remove_chars(blacklist_chars, title)
    description = remove_chars(blacklist_chars, description)
    new_data["title"] = title
    new_data["description"] = description
    return new_data


def upload_from_final_vids():
    # parse by unposted videos
    post_history_module = YoutubePostHistoryManager()
    videos_folder = r"final_vids"
    all_subfolders = os.listdir(videos_folder)

    # filter to unposted videos by checking reddit_url in metadata
    unposted_subfolders = []
    for subfolder in all_subfolders:
        subfolder_path = os.path.join(videos_folder, subfolder)
        metadata = extract_metadata_from_folder(subfolder_path)
        if metadata is False:
            continue
        reddit_url = metadata.get("reddit_url", "")
        reddit_content = metadata.get("reddit_post_content", "")
        if not reddit_content.strip():
            continue
        if reddit_url and not post_history_module.post_exists(reddit_url):
            unposted_subfolders.append((subfolder, metadata))

    print(
        f"{len(unposted_subfolders)} of {len(all_subfolders)} videos have not been posted yet."
    )

    if not unposted_subfolders:
        print("[!] No unposted videos available.")
        return False

    # select the highest repost_quality video
    unposted_subfolders.sort(key=lambda x: x[1].get("repost_quality", 0), reverse=True)
    selected_subfolder, metadata = unposted_subfolders[0]
    selected_subfolder_path = os.path.join(videos_folder, selected_subfolder)
    video_path = os.path.join(selected_subfolder_path, "video.mp4")

    title = metadata["title"]
    description = metadata["description"]
    reddit_url = metadata.get("reddit_url", "")

    print(f"\nPOST METADATA HUMAN CHECK")
    print(f"Title: {title}")
    print(f"Description: {description}")
    print(f"Reddit URL: {reddit_url}")
    input(f"Good to go? Press Enter to continue or Ctrl+C to cancel.")

    try:
        # upload it using the uploader
        uploader = YoutubeUploader()
        uploader.upload_video(title, description, video_path)

        # add to post history by reddit url
        if reddit_url:
            post_history_module.add_post(reddit_url)

        # Delete the video folder after successful upload
        shutil.rmtree(selected_subfolder_path)
        print(f"Deleted uploaded video folder: {selected_subfolder}")
    except Exception as e:
        print(f"ERROR: Upload failed - {e}")
        return False


if __name__ == "__main__":
    upload_from_final_vids()
