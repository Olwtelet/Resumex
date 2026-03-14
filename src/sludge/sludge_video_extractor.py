import os
import random
import subprocess
import cv2


def get_video_duration(video_path):
    cap = cv2.VideoCapture(video_path)
    if not cap.isOpened():
        raise ValueError(f"Cannot open video file: {video_path}")
    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.release()
    if fps <= 0:
        raise ValueError(f"Invalid fps for video: {video_path}")
    return frame_count / fps


def extract_and_resize(input_path, output_path, start_time, end_time, width, height):
    cmd = [
        "ffmpeg", "-y",
        "-ss", str(start_time),
        "-to", str(end_time),
        "-i", input_path,
        "-vf", f"scale={width}:{height}",
        "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
        "-an", output_path,
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"[!] ffmpeg error in extract_and_resize: {result.stderr[-300:]}")
        return False
    return output_path


class Extractor:
    def __init__(self):
        self.videos_dir = r"sludge_videos"

    def get_random_sludge_video(self, target_duration, output_path, expected_dims):
        video_extensions = (".mp4", ".avi", ".mkv", ".mov", ".webm")
        all_videos = [f for f in os.listdir(self.videos_dir) if f.lower().endswith(video_extensions)]
        random_video = random.choice(all_videos)
        base_sludge_video_path = os.path.join(self.videos_dir, random_video)

        duration = int(get_video_duration(base_sludge_video_path))
        if duration < target_duration:
            print(f"Video {random_video} is too short ({duration}s), skipping.")
            return False
        possible_start_times = range(10, duration - target_duration - 10)
        start_time = random.choice(possible_start_times)
        end_time = start_time + target_duration

        extract_and_resize(
            base_sludge_video_path, output_path,
            start_time, end_time,
            expected_dims[0], expected_dims[1],
        )


if __name__ == "__main__":
    pass
