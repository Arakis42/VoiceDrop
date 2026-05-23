"""
single_instance.py – Windows named-mutex guard with takeover.

Usage in main.py:
    import single_instance
    if not single_instance.acquire():
        # acquire() already signalled the old instance to quit and waited
        # for it to release the mutex. Reaching here means takeover failed.
        single_instance.notify_existing()
        sys.exit(0)
    single_instance.install_quit_listener(on_quit_request)
    # ... app startup ...
"""
import ctypes
import logging
import threading
import time

# Unique GUID-based names so they cannot collide with other apps.
_MUTEX_NAME = "VoiceDrop_SingleInstance_{4F8A2B1C-9E3D-4A7F-B2C6-1D5E8F0A3B7E}"
_QUIT_EVENT_NAME = "VoiceDrop_QuitRequest_{4F8A2B1C-9E3D-4A7F-B2C6-1D5E8F0A3B7E}"

_mutex_handle = None
_listener_thread: threading.Thread | None = None

# Win32 constants
_ERROR_ALREADY_EXISTS = 183
_SYNCHRONIZE = 0x00100000
_EVENT_MODIFY_STATE = 0x0002
_WAIT_OBJECT_0 = 0x00000000
_INFINITE = 0xFFFFFFFF


def _kernel32():
    return ctypes.windll.kernel32


def acquire(takeover_timeout_s: float = 5.0) -> bool:
    """Try to claim the single-instance mutex.

    If another instance holds the mutex, signal it to quit via a named event
    and wait up to ``takeover_timeout_s`` for it to release the mutex.

    Returns True if this process now owns the mutex, False if takeover failed.
    """
    global _mutex_handle
    k = _kernel32()
    _mutex_handle = k.CreateMutexW(None, True, _MUTEX_NAME)
    if k.GetLastError() != _ERROR_ALREADY_EXISTS:
        logging.debug("single_instance: mutex acquired on first try.")
        return True

    # Another instance is running — close our handle, signal it to quit, retry.
    if _mutex_handle:
        k.CloseHandle(_mutex_handle)
        _mutex_handle = None
    logging.info("single_instance: existing instance detected, requesting quit.")
    _signal_quit()

    # Poll for the mutex to become free.
    deadline = time.monotonic() + takeover_timeout_s
    while time.monotonic() < deadline:
        time.sleep(0.1)
        _mutex_handle = k.CreateMutexW(None, True, _MUTEX_NAME)
        if k.GetLastError() != _ERROR_ALREADY_EXISTS:
            logging.info("single_instance: takeover successful.")
            return True
        k.CloseHandle(_mutex_handle)
        _mutex_handle = None

    logging.warning("single_instance: takeover timed out.")
    return False


def _signal_quit() -> None:
    """Open the named quit event and set it so the existing instance exits."""
    k = _kernel32()
    # OpenEventW(dwDesiredAccess, bInheritHandle, lpName)
    handle = k.OpenEventW(_EVENT_MODIFY_STATE, False, _QUIT_EVENT_NAME)
    if not handle:
        logging.warning("single_instance: quit event not found (old instance "
                        "may be pre-takeover build).")
        return
    try:
        k.SetEvent(handle)
    finally:
        k.CloseHandle(handle)


def install_quit_listener(on_quit_request) -> None:
    """Spawn a daemon thread that calls on_quit_request() when a newer
    instance asks us to exit.
    """
    global _listener_thread
    if _listener_thread is not None:
        return

    def _wait_loop():
        k = _kernel32()
        # CreateEventW(lpEventAttributes, bManualReset, bInitialState, lpName)
        # Manual-reset so we can re-arm if multiple takeover attempts happen.
        handle = k.CreateEventW(None, True, False, _QUIT_EVENT_NAME)
        if not handle:
            logging.warning("single_instance: failed to create quit event.")
            return
        try:
            result = k.WaitForSingleObject(handle, _INFINITE)
            if result == _WAIT_OBJECT_0:
                logging.info("single_instance: quit requested by new instance.")
                try:
                    on_quit_request()
                except Exception:
                    logging.exception("on_quit_request failed")
        finally:
            k.CloseHandle(handle)

    _listener_thread = threading.Thread(target=_wait_loop, daemon=True)
    _listener_thread.start()


def notify_existing() -> None:
    """Fallback dialog when takeover fails."""
    ctypes.windll.user32.MessageBoxW(
        0,
        "VoiceDrop läuft bereits und konnte nicht ersetzt werden.\n\n"
        "Bitte über das Tray-Symbol beenden und erneut starten.",
        "VoiceDrop",
        0x40 | 0x1000,  # MB_ICONINFORMATION | MB_SETFOREGROUND
    )


def release() -> None:
    """Explicitly release the mutex (called on clean shutdown)."""
    global _mutex_handle
    if _mutex_handle:
        _kernel32().CloseHandle(_mutex_handle)
        _mutex_handle = None
