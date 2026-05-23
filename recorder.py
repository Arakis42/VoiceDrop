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

        try:
            with sd.InputStream(
                samplerate=self.SAMPLE_RATE,
                channels=self.CHANNELS,
                dtype="int16",
                callback=_callback,
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
