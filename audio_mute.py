"""System output mute helper.

Mutes the default Windows render endpoint (speakers/headphones) during
recording so background audio (streams, calls) does not bleed into the mic.
Remembers the prior mute state and restores it.

All operations are best-effort: any failure is logged and swallowed so that
recording itself is never broken by audio API issues.
"""

import logging
import threading

_lock = threading.Lock()
_prev_mute_state: int | None = None  # 0 / 1 as returned by GetMute()
_available: bool | None = None


def _ensure_available() -> bool:
    global _available
    if _available is not None:
        return _available
    try:
        import comtypes  # noqa: F401
        from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume  # noqa: F401
        _available = True
    except Exception as e:
        logging.warning("Audio mute unavailable (pycaw/comtypes missing?): %s", e)
        _available = False
    return _available


def _get_endpoint():
    import comtypes
    try:
        comtypes.CoInitialize()
    except OSError:
        # Already initialized on this thread — fine.
        pass
    from pycaw.pycaw import AudioUtilities

    return AudioUtilities.GetSpeakers().EndpointVolume


def mute_and_remember() -> None:
    """Remember the current mute state and mute the default output."""
    global _prev_mute_state
    if not _ensure_available():
        return
    with _lock:
        try:
            ep = _get_endpoint()
            _prev_mute_state = int(ep.GetMute())
            if _prev_mute_state == 0:
                ep.SetMute(1, None)
        except Exception:
            logging.exception("mute_and_remember failed")
            _prev_mute_state = None


def restore() -> None:
    """Restore the previously remembered mute state. No-op if nothing stored."""
    global _prev_mute_state
    if not _ensure_available():
        return
    with _lock:
        if _prev_mute_state is None:
            return
        try:
            ep = _get_endpoint()
            ep.SetMute(int(_prev_mute_state), None)
        except Exception:
            logging.exception("restore failed")
        finally:
            _prev_mute_state = None
