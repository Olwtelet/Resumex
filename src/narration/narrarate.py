from narration.kokoro.pipeline import KPipeline
import soundfile as sf
import time
import os
import wave
import re


from loguru import logger

logger.remove()
logger.add(lambda msg: None, level="ERROR")


def test_voices():
    voices_folder = r"kokoro.js/voices"
    out_folder = r"voice_tests"
    os.makedirs(out_folder, exist_ok=True)
    voices = [name.split(".")[0] for name in os.listdir(voices_folder)]
    print(voices)

    for voice in voices:
        pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
        text = "Kokoro is running from source on Windows 123!"
        generator = pipeline(text, voice=voice)

        for i, (gs, ps, audio) in enumerate(generator):
            print(f"{i}: {gs} -> {ps}")
            sf.write(f"{out_folder}/output_{voice}_{i}.wav", audio, 24000)


def list_voices():
    voices_folder = r"kokoro.js/voices"
    voices = [name.split(".")[0] for name in os.listdir(voices_folder)]
    print("Available voices:")
    for voice in voices:
        print("  -", voice)


def concatenate_wav_files(input_files, output_file):
    with wave.open(output_file, "wb") as output_wav:
        params_set = False  # Track if we've set the output parameters

        for input_file in input_files:
            with wave.open(input_file, "rb") as input_wav:
                if not params_set:
                    output_wav.setparams(input_wav.getparams())
                    params_set = True  # Ensure this only happens once

                output_wav.writeframes(input_wav.readframes(input_wav.getnframes()))


def clear_narrations(file_paths):
    for f in file_paths:
        try:
            os.remove(f)
        except Exception as e:
            pass


def get_wav_duration(file_path):
    with wave.open(file_path, "rb") as wav_file:
        frames = wav_file.getnframes()
        rate = wav_file.getframerate()
        duration = frames / float(rate)
    return int(duration) + 1


def remove_emojis_from_text(text):
    emoji_pattern = re.compile(
        "["
        "\U0001f600-\U0001f64f"  # emoticons
        "\U0001f300-\U0001f5ff"  # symbols & pictographs
        "\U0001f680-\U0001f6ff"  # transport & map symbols
        "\U0001f700-\U0001f77f"  # alchemical symbols
        "\U0001f1e0-\U0001f1ff"  # flags (iOS)
        "]+",
        flags=re.UNICODE,
    )
    return emoji_pattern.sub(r"", text)


def narrate(voice, text):
    text = remove_emojis_from_text(text)

    output_folder = r"temp"
    os.makedirs(output_folder, exist_ok=True)
    this_audio_save_index = len(os.listdir(output_folder))
    files_in_dir = os.listdir(output_folder)
    pipeline = KPipeline(lang_code="a", repo_id="hexgrad/Kokoro-82M")
    generator = pipeline(text, voice=voice)

    part_file_paths = []
    for i, (gs, ps, audio) in enumerate(generator):
        file_name = f"{voice}_{len(files_in_dir) + 1}_{i+1}.wav"
        file_path = os.path.join(output_folder, file_name)
        sf.write(file_path, audio, 24000)
        part_file_paths.append(file_path)

    combined_audio_file_path = f"{output_folder}/{this_audio_save_index}_{voice}.wav"
    concatenate_wav_files(part_file_paths, combined_audio_file_path)
    clear_narrations(part_file_paths)
    duration = get_wav_duration(combined_audio_file_path)
    return combined_audio_file_path, duration


if __name__ == "__main__":
    pass
