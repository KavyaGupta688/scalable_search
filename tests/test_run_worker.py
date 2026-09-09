from __future__ import annotations

import signal

from scripts.run_worker import install_signal_handlers


class WindowsLikeLoop:
    def __init__(self):
        self.threadsafe_callbacks = []

    def add_signal_handler(self, *_args):
        raise NotImplementedError

    def call_soon_threadsafe(self, callback):
        self.threadsafe_callbacks.append(callback)


def test_windows_signal_handlers_use_signal_module(monkeypatch):
    registered = []
    monkeypatch.setattr(signal, "signal", lambda sig, callback: registered.append((sig, callback)))
    loop = WindowsLikeLoop()

    install_signal_handlers(loop, object())

    assert {item[0] for item in registered} == {signal.SIGINT, signal.SIGTERM}
