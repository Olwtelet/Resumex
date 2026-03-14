from PIL import Image, ImageDraw, ImageFont
import requests
from io import BytesIO
import random
import os
from src.scraper.scraper import DataSaver
import cv2

# --- Constants ---
IMG_WIDTH, IMG_HEIGHT = 360, 640
MARGIN = 16
LINE_SPACING = 6

# Fonts
FONT_TITLE = r"fonts/NotoSans-Bold.ttf"
FONT_BODY = r"fonts/NotoSans-Regular.ttf"
FONT_SEARCH = r"fonts/NotoSans-SemiBold.ttf"
font_title = ImageFont.truetype(FONT_TITLE, size=18)
font_body = ImageFont.truetype(FONT_BODY, size=14)
font_search = ImageFont.truetype(FONT_SEARCH, size=12)


def crop_image(image_path, left, top, right, bottom, save=False):
    image = cv2.imread(image_path)
    cropped_image = image[top:bottom, left:right]
    if save:
        cv2.imwrite(image_path, cropped_image)
    return cropped_image


def pixel_is_white(pixel):
    if len(pixel) != 3:
        return False
    if pixel[0] > 240 and pixel[1] > 240 and pixel[2] > 240:
        return True
    return False


def crop_whitespace_out_of_image(image_path, save=False):
    # read image, read size
    image = cv2.imread(image_path)
    dims = image.shape
    y_max, x_max = dims[0], dims[1]

    # loop row by row starting from bottom,
    # looking for first non-white row
    first_non_white_row_from_bottom = None
    for y in range(y_max - 1, -1, -1):
        this_row_pixels = []
        for x in range(0, x_max):
            pixel = image[y, x]
            this_row_pixels.append(pixel)
        if not all(pixel_is_white(pixel) for pixel in this_row_pixels):
            first_non_white_row_from_bottom = y
            break

    # if didnt find ANY non-white rows, return error
    if first_non_white_row_from_bottom is None:
        print("[!] Warning: This image is entirely white!")
        return False

    pad = 30

    cropped_image = crop_image(
        image_path, 0, 0, x_max, first_non_white_row_from_bottom + pad, save=save
    )

    return cropped_image


def resize_image_keep_aspect_ratio(image, target_width):
    width, height = image.size
    aspect_ratio = height / width
    target_height = int(target_width * aspect_ratio)
    resized_image = image.resize((target_width, target_height), Image.LANCZOS)
    return resized_image


def make_reddit_post_image(
    thread,
    title_text,
    body_text,
    username,
    expected_width,
    subreddit_icon_url=None,
    save=True,
    save_path="temp",
):
    if None in [thread, title_text, body_text, username]:
        return None

    BODY_TEXT_MAX_LENGTH = 1500
    BODY_TEXT_MIN_LENGTH = 300
    THREAD_NAME_MAX_LENGTH = 17
    USERNAME_MAX_LENGTH = 27

    if len(body_text) > BODY_TEXT_MAX_LENGTH:
        # print("[!] Error: your body text is too long itll be cut off")
        return None
    if len(body_text) < BODY_TEXT_MIN_LENGTH:
        # print("[!] Error: your body text is too short itll be cut off")
        return None
    if len(thread) > THREAD_NAME_MAX_LENGTH:
        # print("[!] Error: your thread name is too long itll be cut off")
        return None
    if len(username) > USERNAME_MAX_LENGTH:
        # print("[!] Error: your username is too long itll be cut off")
        return None

    post_age = f"{random.randint(1,19)}h"
    base_image_path = "reddit_assets/images/base_post_image.png"
    img = Image.open(base_image_path).convert("RGB")
    draw = ImageDraw.Draw(img)

    # Draw subreddit name in search bar
    draw.text((170, 18), thread, font=font_search, fill="#333333")

    # Draw subreddit icon
    try:
        response = requests.get(subreddit_icon_url)
        subreddit_icon = (
            Image.open(BytesIO(response.content)).convert("RGBA").resize((20, 20))
        )
        mask_icon = Image.new("L", (20, 20), 0)
        ImageDraw.Draw(mask_icon).ellipse((0, 0, 20, 20), fill=255)
        img.paste(subreddit_icon, (85, 25), mask_icon)
    except Exception as e:
        # print("[!] Non fetal error: Failed to load subreddit icon:", e)
        # return None
        pass

    # Draw profile avatar
    fallback_path = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "reddit_assets", "images", "pfp_bw.png")
    avatar = Image.open(fallback_path).convert("RGBA").resize((32, 32), Image.LANCZOS)
    # Composite avatar onto white background to eliminate black from transparency
    avatar_bg = Image.new("RGBA", (32, 32), (255, 255, 255, 255))
    avatar_bg.paste(avatar, (0, 0), avatar)
    mask = Image.new("L", (32, 32), 0)
    ImageDraw.Draw(mask).ellipse((0, 0, 32, 32), fill=255)
    img.paste(avatar_bg, (MARGIN, 60), mask)

    # Draw username and timestamp
    draw.text(
        (MARGIN + 40, 60), f"{username} · {post_age} ago", font=font_body, fill="gray"
    )

    # Text wrapping function
    def draw_wrapped_text(draw, text, font, x, y, max_width):
        paragraphs = text.split("\n")  # handles \n and \n\n naturally
        for para in paragraphs:
            if para.strip() == "":
                # Add paragraph spacing
                y += font.getbbox("A")[3] - font.getbbox("A")[1] + LINE_SPACING
                continue

            words = para.split()
            line = ""
            for word in words:
                test_line = f"{line} {word}".strip()
                bbox = font.getbbox(test_line)
                line_width = bbox[2] - bbox[0]
                if line_width <= max_width:
                    line = test_line
                else:
                    draw.text((x, y), line, font=font, fill="black")
                    y += font.getbbox(line)[3] - font.getbbox(line)[1] + LINE_SPACING
                    line = word
            if line:
                draw.text((x, y), line, font=font, fill="black")
                y += font.getbbox(line)[3] - font.getbbox(line)[1] + LINE_SPACING
        return y

    # Draw title and body
    content_y_start = 60 + 32 + 10
    y = draw_wrapped_text(
        draw, title_text, font_title, MARGIN, content_y_start, IMG_WIDTH - 2 * MARGIN
    )
    y += 8
    y = draw_wrapped_text(draw, body_text, font_body, MARGIN, y, IMG_WIDTH - 2 * MARGIN)

    # resize to match expected width
    img = resize_image_keep_aspect_ratio(img, expected_width)

    if save:
        image_saver = ImageSaver(save_path=save_path)
        image_path = image_saver.save_image(
            img,
            thread,
        )
        crop_whitespace_out_of_image(image_path, save=True)
        return image_path

    return img


class ImageSaver:
    def __init__(self, save_path="reddit_post_images"):
        self.save_path = save_path
        if not os.path.exists(save_path):
            os.makedirs(save_path)

    def save_image(
        self,
        img,
        thread_name,
    ):
        uuid = str(random.randint(10000, 99999))[
            :8
        ]  # Generate a short unique identifier
        file_name = f"{uuid}.png"
        subfolder = thread_name.replace(" ", "_").replace("/", "_")
        subfolder_path = os.path.join(self.save_path, subfolder)
        if not os.path.exists(subfolder_path):
            os.makedirs(subfolder_path)
        image_path = os.path.join(self.save_path, subfolder, file_name)

        img.save(image_path)
        return image_path

    def get_all_images(self):
        import os

        return [f for f in os.listdir(self.save_path) if f.endswith(".png")]


def create_all_reddit_posts():
    ds = DataSaver()
    image_saver = ImageSaver()
    posts = ds.get_all_posts()
    for post in posts:
        post = post.to_dict()
        thread = post["thread_name"]
        title_text = post["title"]
        body_text = post["content"]
        username = post["username"]
        image = make_reddit_post_image(
            thread, title_text, body_text, username, expected_width=360
        )
        if image is not None:
            image_path = image_saver.save_image(image, thread)
            crop_whitespace_out_of_image(image_path, save=True)


if __name__ == "__main__":
    create_all_reddit_posts()
