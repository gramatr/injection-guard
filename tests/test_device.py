"""
Device selection (config.py DEVICE / model._resolve_device) — opt-in GPU,
CPU default, loud failure on misconfiguration. See config.py's comment
for the measured CPU-vs-GPU numbers behind "opt-in, never required."
"""

import pytest

from injection_guard import config, model


def test_auto_prefers_cuda_when_available(monkeypatch):
    monkeypatch.setattr(config, "DEVICE", "auto")
    monkeypatch.setattr(model.torch.cuda, "is_available", lambda: True)
    assert model._resolve_device() == "cuda"


def test_auto_falls_back_to_cpu_when_unavailable(monkeypatch):
    monkeypatch.setattr(config, "DEVICE", "auto")
    monkeypatch.setattr(model.torch.cuda, "is_available", lambda: False)
    assert model._resolve_device() == "cpu"


def test_forced_cpu_always_honored(monkeypatch):
    monkeypatch.setattr(config, "DEVICE", "cpu")
    assert model._resolve_device() == "cpu"


def test_forced_cuda_with_no_gpu_fails_loudly(monkeypatch):
    monkeypatch.setattr(config, "DEVICE", "cuda")
    monkeypatch.setattr(model.torch.cuda, "is_available", lambda: False)
    with pytest.raises(RuntimeError, match="no GPU visible"):
        model._resolve_device()


def test_forced_cuda_with_gpu_present_is_honored(monkeypatch):
    monkeypatch.setattr(config, "DEVICE", "cuda")
    monkeypatch.setattr(model.torch.cuda, "is_available", lambda: True)
    assert model._resolve_device() == "cuda"
