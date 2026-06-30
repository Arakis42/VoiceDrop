import io
import threading
import wave

try:
    import numpy as np
    import sounddevice as sd
    SOUNDDEVICE_AVAILABLE = True
except ImportError:
    SOUNDDEVICE_AVAILABLE = False


class RecorderError(Exception):
    pass


def get_input_devices() -> list[tuple[str, int]]:
    """Return [(name, index), ...] for selectable input devices, de-duplicated.

    Windows exposes every physical mic once per host API (MME, DirectSound,
    WASAPI, WDM-KS), which floods the picker with near-identical entries and
    truncated MME names. We therefore prefer the modern WASAPI host API, which
    lists each active device exactly once with its full name. If WASAPI is
    unavailable (e.g. non-Windows), we fall back to de-duplicating by name
    across all host APIs.
    """
    if not SOUNDDEVICE_AVAILABLE:
        return []
    try:
        devices = sd.query_devices()
    except Exception:
        return []

    wasapi_idx = None
    try:
        for i, h in enumerate(sd.query_hostapis()):
            if "wasapi" in h["name"].lower():
                wasapi_idx = i
                break
    except Exception:
        wasapi_idx = None

    result: list[tuple[str, int]] = []
    seen: set[str] = set()
    for i, d in enumerate(devices):
        if d["max_input_channels"] <= 0:
            continue
        if wasapi_idx is not None and d["hostapi"] != wasapi_idx:
            continue
        name = d["name"]
        if name in seen:
            continue
        seen.add(name)
        result.append((name, i))
    return result


def _find_device_index(name: str) -> int | None:
    """Return device index for the given name, or None if not found (falls back to default)."""
    try:
        for dev_name, idx in get_input_devices():
            if dev_name == name:
                return idx
    except Exception:
        pass
    return None


class AudioRecorder:
    SAMPLE_RATE = 16000
    CHANNELS = 1

    def __init__(self):
        self._stop_event: threading.Event | None = None
        self._thread: threading.Thread | None = None
        self._frames: list = []
        self._lock = threading.Lock()

    def _find_input_device(self) -> bool:
        try:
            devices = sd.query_devices()
            for d in devices:
                if d["max_input_channels"] > 0:
                    return True
        except Exception:
            pass
        return False

    def start_recording(self) -> None:
        if not SOUNDDEVICE_AVAILABLE:
            raise RecorderError(
                "sounddevice is not installed. Run: pip install sounddevice"
            )

        with self._lock:
            if self._thread and self._thread.is_alive():
                return

            if not self._find_input_device():
                raise RecorderError(
                    "No microphone found. Please connect a microphone and try again."
                )

            self._stop_event = threading.Event()
            self._frames = []
            self._thread = threading.Thread(
                target=self._record_loop,
                daemon=True,
            )
            self._thread.start()

    def _record_loop(self) -> None:
        def _callback(indata, frames, time_info, status):
            if not self._stop_event.is_set():
                self._frames.append(indata.copy())

        from config import get_config
        device_name = get_config().get("audio_device")
        device_idx = _find_device_index(device_name) if device_name else None

        try:
            with sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype="int16",
                callback=_callback,
                device=device_idx,
            ):
                self._stop_event.wait()
        except Exception:
            pass

    def stop_recording(self) -> io.BytesIO:
        if self._stop_event:
            self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5.0)

        frames = self._frames[:]
        self._frames = []

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as wf:
            wf.setnchannels(self.CHANNELS)
            wf.setsampwidth(2)  # int16 = 2 bytes
            wf.setframerate(self.SAMPLE_RATE)
            if frames:
                import numpy as np
                wf.writeframes(np.concatenate(frames, axis=0).tobytes())
        buffer.seek(0)
        return buffer
