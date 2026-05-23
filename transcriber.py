import io
import threading
from typing import Optional

try:
    import numpy as np
    import soundfile as sf
    import whisper
    WHISPER_AVAILABLE = True
except ImportError:
    WHISPER_AVAILABLE = False


class TranscriberError(Exception):
    pass


class Transcriber:
    def __init__(self, model_name: str = "medium"):
        self._model_name = model_name
        self._model = None
        self._lock = threading.Lock()
        self._load_lock = threading.Lock()

    def set_model_name(self, model_name: str) -> None:
        with self._load_lock:
            if model_name != self._model_name:
                self._model_name = model_name
                if self._model is not None:
                    del self._model
                    self._model = None
                    try:
                        import gc
                        import torch
                        gc.collect()
                        torch.cuda.empty_cache()
                    except Exception:
                        pass

    def load_model(self) -> None:
        if not WHISPER_AVAILABLE:
            raise TranscriberError(
                "openai-whisper is not installed. Run: pip install openai-whisper"
            )
        try:
            import torch
            device = "cuda" if torch.cuda.is_available() else "cpu"
        except ImportError:
            device = "cpu"
        with self._load_lock:
            self._model = whisper.load_model(self._model_name, device=device)

    def is_model_loaded(self) -> bool:
        return self._model is not None

    def transcribe(self, audio_buffer: io.BytesIO) -> str:
        if not WHISPER_AVAILABLE:
            raise TranscriberError(
                "openai-whisper is not installed. Run: pip install openai-whisper"
            )
        if self._model is None:
            raise TranscriberError(
                "Please download the Whisper model in Settings first."
            )

        audio_buffer.seek(0)
        audio_data, sample_rate = sf.read(audio_buffer, dtype="float32")

        # Whisper expects mono float32 at 16kHz
        if len(audio_data.shape) > 1:
            audio_data = audio_data.mean(axis=1)

        if sample_rate != 16000:
            # Resample if needed (shouldn't happen since recorder uses 16kHz)
            import resampy
            audio_data = resampy.resample(audio_data, sample_rate, 16000)

        from config import get_config
        cfg = get_config()
        language = cfg.get("whisper_language") or None
        initial_prompt = cfg.get("whisper_initial_prompt") or None

        # Wenn Deutsch ausgewählt ist und ein Prompt gesetzt wurde:
        # language auf None lassen (Auto-Detect pro Segment) damit englische
        # Fachbegriffe korrekt durchkommen, aber der Prompt biased Whisper
        # in Richtung Deutsch.
        if language == "de" and initial_prompt:
            language = None

        with self._lock:
            result = self._model.transcribe(
                audio_data,
                language=language,
                task="transcribe",
                initial_prompt=initial_prompt,
            )

        return result["text"].strip()

    def get_model_name(self) -> str:
        return self._model_name


_transcriber: Optional[Transcriber] = None


def get_transcriber() -> Transcriber:
    global _transcriber
    if _transcriber is None:
        from config import get_config
        cfg = get_config()
        _transcriber = Transcriber(model_name=cfg.get("whisper_model"))
    return _transcriber
