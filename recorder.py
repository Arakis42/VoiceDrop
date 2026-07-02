import io
import logging
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


def _wasapi_settings_for(device_idx: int | None):
    """Return WasapiSettings(auto_convert=True) for WASAPI devices, else None.

    WASAPI in shared mode rejects sample rates that differ from the device's
    native mix format (e.g. our fixed 16 kHz vs a 48 kHz webcam mic) with
    "Invalid sample rate [-9997]". auto_convert enables PortAudio's built-in
    sample-rate conversion so 16 kHz capture works when we do open via WASAPI.
    """
    if device_idx is None:
        return None
    try:
        dev = sd.query_devices(device_idx)
        host = sd.query_hostapis(dev["hostapi"])
        if "wasapi" in host["name"].lower():
            return sd.WasapiSettings(auto_convert=True)
    except Exception:
        logging.debug("Could not determine host API for device %r",
                      device_idx, exc_info=True)
    return None


# Host APIs ordered by how reliably they open an input stream at our fixed
# 16 kHz on Windows. DirectSound/MME resample natively and open reliably;
# WASAPI needs auto_convert and has proven flaky for capture on some machines
# (raises "Unanticipated host error -9999"); WDM-KS is exclusive/low-level and
# kept last as a desperation attempt.
_HOSTAPI_CAPTURE_PREFERENCE = ("directsound", "mme", "wasapi", "wdm-ks")


def _name_matches(dev_name: str, wanted: str) -> bool:
    """True if a device name matches the stored selection.

    The picker stores the WASAPI/DirectSound full name, but the same physical
    mic appears under MME with the name truncated to 31 chars — so we also
    accept a prefix match (guarded by a min length to avoid false positives).
    """
    if dev_name == wanted:
        return True
    if min(len(dev_name), len(wanted)) >= 12 and (
        wanted.startswith(dev_name) or dev_name.startswith(wanted)
    ):
        return True
    return False


def _candidate_devices(name: str) -> list[tuple[int, str]]:
    """All input-device indices matching `name`, ordered by capture reliability.

    Returns [(index, host_api_name), ...] across every host API so recording
    can fall through from a flaky host API (WASAPI) to one that actually works
    at 16 kHz (DirectSound/MME) without the user having to change anything.
    """
    if not name:
        return []
    try:
        devices = sd.query_devices()
        hostapis = sd.query_hostapis()
    except Exception:
        return []

    def pref(host_name: str) -> int:
        h = host_name.lower()
        for i, key in enumerate(_HOSTAPI_CAPTURE_PREFERENCE):
            if key in h:
                return i
        return len(_HOSTAPI_CAPTURE_PREFERENCE)

    matches = []
    for i, d in enumerate(devices):
        if d["max_input_channels"] <= 0:
            continue
        if _name_matches(d["name"], name):
            host_name = hostapis[d["hostapi"]]["name"]
            matches.append((pref(host_name), i, host_name))
    matches.sort(key=lambda t: t[0])
    return [(i, h) for _, i, h in matches]


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
            if status:
                logging.debug("Recording stream status: %s", status)
            if not self._stop_event.is_set():
                self._frames.append(indata.copy())

        from config import get_config
        device_name = get_config().get("audio_device")

        # Try the selected mic across all its host APIs (reliable ones first),
        # then the system default. The first stream that opens is used for the
        # whole recording; the log records which host API actually worked.
        attempts = _candidate_devices(device_name) + [(None, "system default")]

        for idx, host in attempts:
            try:
                with sd.InputStream(
                    samplerate=self.SAMPLE_RATE,
                    channels=self.CHANNELS,
                    dtype="int16",
                    callback=_callback,
                    device=idx,
                    extra_settings=_wasapi_settings_for(idx),
                ):
                    logging.info("Recording via %s (index %s)", host, idx)
                    self._stop_event.wait()
                return
            except Exception as e:
                logging.warning("Recording open failed via %s (index %s): %s",
                                host, idx, e)
                if self._stop_event.is_set():
                    break  # user already released; don't keep probing
        logging.error("Recording failed on all candidate devices for %r",
                      device_name)

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
