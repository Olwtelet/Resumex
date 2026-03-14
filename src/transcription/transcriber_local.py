from faster_whisper import WhisperModel
from pathlib import Path
import os
import requests


class Transcriber:
    def __init__(self, model_size: str = "base.en", compute_type: str = "int8"):
        """
        Initialize the Faster-Whisper model.
        :param model_size: tiny, base, small, medium, large-v2
        :param compute_type: "int8", "float16", or "float32"

        Model benchmarking info
            base.en | 98
            tiny.en | 96
            base    | 91
            tiny    | 83
        """
        self.model = WhisperModel(model_size, compute_type=compute_type, device="cpu")

    def get_supported_faster_whisper_models(self):
        def remove_prefix(model_name: str) -> str:
            # model size 'faster-whisper-base', expected one of: tiny.en, tiny, base.en
            return model_name.replace("faster-whisper-", "")

        url = "https://huggingface.co/api/models?author=guillaumekln"

        try:
            response = requests.get(url, timeout=10)
            response.raise_for_status()
            data = response.json()
            response_models = sorted(
                {m["modelId"].split("/")[-1] for m in data if "whisper" in m["modelId"]}
            )
            response_models = [remove_prefix(m) for m in response_models]
            return response_models

        except Exception as e:
            print(f"[!] Warning! Failed to fetch model list: {e}\nUsing fallback list.")
            fallback = [
                "faster-whisper-base",
                "faster-whisper-base.en",
                "faster-whisper-large-v1",
                "faster-whisper-large-v2",
                "faster-whisper-medium",
                "faster-whisper-medium.en",
                "faster-whisper-small",
                "faster-whisper-small.en",
                "faster-whisper-tiny",
                "faster-whisper-tiny.en",
            ]
            fallback = [remove_prefix(m) for m in fallback]
            return fallback

    def transcribe_to_srt(
        self, audio_path: str, save: bool = False, output_folder="transcriptions"
    ) -> str:
        """
        Transcribe audio and return SRT-format subtitle string.
        If save=True, writes .srt next to the audio file.
        """

        if save:
            if not os.path.exists(output_folder):
                os.makedirs(output_folder)

        segments, info = self.model.transcribe(
            audio_path,
            language="en",
            beam_size=10,  # Higher precision than default (5)
            best_of=10,  # Improves greedy selection if beam search is not used
            patience=2.0,  # Explore longer before finalizing beam results
            length_penalty=1.0,  # Neutral bias for length
            temperature=[0.0, 0.2],  # Retry strategy in case of decoding failures
            word_timestamps=True,  # Needed if you're syncing captions
            condition_on_previous_text=True,  # Ensures context continuity
            no_repeat_ngram_size=3,  # Avoids echo/repeats
            log_prob_threshold=-2.0,  # Slightly more permissive than -1.0
            suppress_blank=True,
            suppress_tokens=[-1],
            vad_filter=True,  # Optional: reduce hallucinated speech
            chunk_length=30,  # Reasonable tradeoff to reduce memory usage spikes
        )

        srt_output = []
        for i, segment in enumerate(segments, 1):
            start = self._format_timestamp(segment.start)
            end = self._format_timestamp(segment.end)
            text = segment.text.strip()
            srt_output.append(f"{i}\n{start} --> {end}\n{text}\n")

        srt_string = "\n".join(srt_output)

        if save:
            save_index = len(os.listdir(output_folder))
            srt_path = Path(output_folder) / f"transcription_{save_index}.srt"
            with open(srt_path, "w", encoding="utf-8") as f:
                f.write(srt_string)
            return str(srt_path)

        return srt_string

    def _format_timestamp(self, seconds: float) -> str:
        millis = int(seconds * 1000)
        hours = millis // 3600000
        mins = (millis % 3600000) // 60000
        secs = (millis % 60000) // 1000
        ms = millis % 1000
        return f"{hours:02}:{mins:02}:{secs:02},{ms:03}"


if __name__ == "__main__":
    transcriber = Transcriber()
    audio_file = (
        r"H:\my_files\my_programs\shortform-sludge-maker\narrations\12_jf_alpha.wav"
    )
    available_models = transcriber.get_supported_faster_whisper_models()
    print("Available Faster-Whisper models:")
    for model in available_models:
        print(f" - {model}")
    srt_content = transcriber.transcribe_to_srt(audio_file, save=False)
    print("Transcription (SRT format):")
    print(srt_content)
