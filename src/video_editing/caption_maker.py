def extract_word_timestamps_from_line(line, start_time, end_time):
    line_len = len(line)
    time_diff = end_time - start_time
    time_per_char = time_diff / line_len
    word_timestamps = []
    char_index = 0
    for word in line.split():
        word_len = len(word)
        start_index = char_index
        end_index = char_index + word_len
        char_index = end_index + 1  # update char index for next loop
        this_word_start_time = round((start_time + (start_index * time_per_char)), 2)
        this_word_end_time = round((start_time + (end_index * time_per_char)), 2)
        word_timestamp_datum = {
            "word": word,
            "start_time": this_word_start_time,
            "end_time": this_word_end_time,
        }
        word_timestamp_datum
        word_timestamps.append(word_timestamp_datum)

    return word_timestamps


def extract_word_timestamps_from_transcript(transcript):
    def timestamp_string_to_s(timestamp: str):
        """
        00:00:04,240 -> 4.240
        Can return False if parsing fails
        """
        try:
            hours, minutes, seconds = timestamp.split(":")
        except ValueError:
            print(f"[!] Warning: Failed to parse timestamp: {timestamp}")
            return False
        seconds, milliseconds = seconds.split(",")
        return f"{int(hours) * 3600 + int(minutes) * 60 + int(seconds)}.{milliseconds}"

    transcript_sections = transcript.split("\n\n")

    word_timestamps = []

    for transcript_section in transcript_sections:
        section_lines = transcript_section.split("\n")
        index_line = section_lines[0]
        timestamp_line = section_lines[1]
        text_lines = section_lines[2:]
        index = int(index_line.strip())
        start_time_string, end_time_string = timestamp_line.split(" --> ")
        start_time_s = timestamp_string_to_s(start_time_string.strip())
        end_time_s = timestamp_string_to_s(end_time_string.strip())
        if start_time_s is False or end_time_s is False:
            print(
                f"[!] Warning: Failed to parse timestamp in section {transcript_section}\nJust skipping over it for now..."
            )
            continue
        text = " ".join(text_lines).strip()
        this_section_word_timestamps = extract_word_timestamps_from_line(
            text, float(start_time_s), float(end_time_s)
        )
        word_timestamps.extend(this_section_word_timestamps)

    return word_timestamps


def remove_sudden_frame_gaps(frames, max_gap=0.08):
    """
    Modifies frame timestamps to remove small gaps between consecutive frames.

    Ensures smooth transitions by making each frame start exactly when the previous one ends,
    if the gap is below `max_gap`.

    Args:
        frames (list): List of caption frames, each with 'start_time' and 'end_time'.
        max_gap (float): Maximum allowed gap before it's considered "sudden".

    Returns:
        list: Adjusted list of frames with smoothed timing.
    """
    if not frames:
        return []

    adjusted_frames = [frames[0]]

    for i in range(1, len(frames)):
        prev = adjusted_frames[-1]
        curr = frames[i].copy()  # Copy to avoid mutating original

        gap = curr["start_time"] - prev["end_time"]
        if gap > 0 and gap <= max_gap:
            curr["start_time"] = prev["end_time"]  # Remove the tiny gap

        adjusted_frames.append(curr)

    return adjusted_frames


def generate_caption_frames(word_timestamps, max_group_duration=2.5, max_words=5):
    """
    Groups word timestamps into segments and produces per-word caption frames.

    Each frame includes:
        - full group of words (same in each frame of group)
        - highlight index (which word is being spoken)
        - start and end times for that word
    """
    if not word_timestamps:
        return []

    frames = []
    group = []
    group_start_time = word_timestamps[0]["start_time"]

    for i, wt in enumerate(word_timestamps):
        group.append(wt)
        group_end_time = wt["end_time"]

        group_duration = group_end_time - group_start_time
        group_too_long = group_duration > max_group_duration
        group_too_big = len(group) >= max_words

        next_is_new_group = False
        if i + 1 < len(word_timestamps):
            next_start = word_timestamps[i + 1]["start_time"]
            next_is_new_group = (
                group_too_long or group_too_big or (next_start - group_end_time > 0.5)
            )

        if next_is_new_group or i + 1 == len(word_timestamps):
            words = [w["word"] for w in group]
            for j, w in enumerate(group):
                frame = {
                    "words": words,
                    "highlight_index": j,
                    "start_time": w["start_time"],
                    "end_time": w["end_time"],
                }
                frames.append(frame)

            # Reset group
            group = []
            if i + 1 < len(word_timestamps):
                group_start_time = word_timestamps[i + 1]["start_time"]

    frames = remove_sudden_frame_gaps(frames, max_gap=0.4)

    return frames


if __name__ == "__main__":
    pass
