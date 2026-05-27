"""System output mute helper — persistenter COM-Worker-Thread.

Mutes the default Windows render endpoint (speakers/headphones) during
recording so background audio (streams, calls) does not bleed into the mic.

Verwendet einen einzigen langlebigen Daemon-Thread der COM einmalig
initialisiert und den AudioEndpoint cached. Dadurch dauert jeder
SetMute()-Aufruf < 5 ms statt 100–300 ms (die bei COM-Neuinitialisierung
auf einem Fresh-Thread anfallen).

Aufruf-Sequenz:
    audio_mute.initialize()       # einmalig beim App-Start
    audio_mute.mute_and_remember()  # fire-and-forget vor Aufnahme
    audio_mute.restore()            # blockierend nach Aufnahme

All operations are best-effort: any failure is logged and swallowed so that
recording itself is never broken by audio API issues.
"""

import logging
import queue
import threading
from typing import Optional

_task_queue: queue.Queue = queue.Queue()
_worker_thread: Optional[threading.Thread] = None


def initialize() -> None:
    """Worker-Thread starten und COM/Endpoint vorab laden (beim App-Start aufrufen)."""
    global _worker_thread
    if _worker_thread and _worker_thread.is_alive():
        return
    _worker_thread = threading.Thread(
        target=_com_worker, daemon=True, name="AudioMuteWorker"
    )
    _worker_thread.start()


def _com_worker() -> None:
    """Langlebiger COM-Thread: initialisiert einmalig, cached den Endpoint."""
    ep = None
    try:
        import comtypes
        comtypes.CoInitialize()
        from pycaw.pycaw import AudioUtilities
        ep = AudioUtilities.GetSpeakers().EndpointVolume
        logging.debug("audio_mute: endpoint cached")
    except Exception:
        logging.exception("audio_mute: COM init failed, muting unavailable")

    # Mutable state lebt ausschließlich in diesem Thread → kein Lock nötig
    _prev: list[Optional[int]] = [None]

    while True:
        fn = _task_queue.get()
        if fn is None:  # poison pill → beenden
            return
        try:
            fn(ep, _prev)
        except Exception:
            logging.exception("audio_mute task failed")


def mute_and_remember() -> None:
    """Stummschalten – nicht-blockierend (fire-and-forget).

    Stellt sicher dass der Worker-Thread läuft falls er noch nicht gestartet wurde.
    """
    _ensure_initialized()

    def _task(ep, prev):
        if ep is None:
            return
        try:
            state = int(ep.GetMute())
            prev[0] = state
            if state == 0:
                ep.SetMute(1, None)
        except Exception:
            logging.exception("mute_and_remember failed")
            prev[0] = None

    _task_queue.put(_task)


def restore() -> None:
    """Vorherigen Zustand wiederherstellen – blockierend (aber schnell, Endpoint gecacht)."""
    _ensure_initialized()
    done = threading.Event()

    def _task(ep, prev):
        try:
            if ep is not None and prev[0] is not None:
                ep.SetMute(prev[0], None)
            prev[0] = None
        except Exception:
            logging.exception("restore failed")
        finally:
            done.set()

    _task_queue.put(_task)
    done.wait(timeout=0.5)


def _ensure_initialized() -> None:
    """Lazy-Fallback: Worker starten falls initialize() nicht explizit aufgerufen wurde."""
    global _worker_thread
    if not (_worker_thread and _worker_thread.is_alive()):
        initialize()
