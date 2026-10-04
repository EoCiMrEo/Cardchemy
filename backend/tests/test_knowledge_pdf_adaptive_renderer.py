"""Definitive raster oversize may reduce resolution without multiplying time or escaping cleanup."""
from pathlib import Path
import signal
import threading

import pytest

from app.services import knowledge_pdf_renderer as renderer
from tests.test_knowledge_pdf_renderer import fake_runtime, png, source


def test_adaptive_oversize_preserves_full_page_binding_and_one_cumulative_deadline(source, fake_runtime, monkeypatch):
    clock, calls, directories = [0.0], [], []
    monkeypatch.setattr(renderer.time, "monotonic", lambda: clock[0])
    def render(executable, pdf, page, target, timeout, *, cancel_event, long_side):
        calls.append((long_side, timeout, target))
        directories.append(target.parent)
        assert not target.exists() and cancel_event is None
        if long_side == 1600:
            target.write_bytes(b"x" * (renderer.MAX_PNG_BYTES + 1))
            clock[0] = 20.0
            raise renderer.KnowledgePdfRenderError("render_png_byte_limit")
        assert long_side == 1400 and timeout == 10
        clock[0] = 28.0
        return png(1400, 700)
    monkeypatch.setattr(renderer, "_render_one", render)
    result = renderer.render_pdf_pages(source[0], source_sha256=source[1], page_numbers=[1], adaptive=True)
    assert [call[0] for call in calls] == [1600, 1400]
    assert len(set(call[2] for call in calls)) == 2
    binding = result[0].image_binding("source")
    assert binding["render"]["scale_to"] == binding["width"] == 1400
    assert binding["render"]["full_page"] and not binding["render"]["crop"]
    assert binding["pdf_sha256"] == source[1] and binding["physical_page"] == 1
    assert all(not directory.exists() for directory in directories)


@pytest.mark.parametrize("failure", ["render_failed", "render_timeout", "render_cleanup_failed", "render_cancelled"])
def test_non_size_failures_never_trigger_resolution_fallback(source, fake_runtime, monkeypatch, failure):
    calls, directories = [], []
    def render(executable, pdf, page, target, timeout, **kwargs):
        calls.append(kwargs["long_side"])
        directories.append(target.parent)
        raise renderer.KnowledgePdfRenderError(failure)
    monkeypatch.setattr(renderer, "_render_one", render)
    with pytest.raises(renderer.KnowledgePdfRenderError, match=failure):
        renderer.render_pdf_pages(source[0], source_sha256=source[1], page_numbers=[1], adaptive=True)
    assert calls == [1600] and all(not directory.exists() for directory in directories)


@pytest.mark.parametrize("stop", ["deadline", "cancel"])
def test_deadline_or_cancellation_between_size_attempts_stops_without_second_child(source, fake_runtime, monkeypatch, stop):
    clock, calls, cancel = [0.0], [], threading.Event()
    monkeypatch.setattr(renderer.time, "monotonic", lambda: clock[0])
    def render(*args, **kwargs):
        calls.append(kwargs["long_side"])
        if stop == "deadline":
            clock[0] = 30.01
        else:
            cancel.set()
        raise renderer.KnowledgePdfRenderError("render_png_byte_limit")
    monkeypatch.setattr(renderer, "_render_one", render)
    with pytest.raises(renderer.KnowledgePdfRenderError, match="render_timeout" if stop == "deadline" else "render_cancelled"):
        renderer.render_pdf_pages(source[0], source_sha256=source[1], page_numbers=[1], adaptive=True,
                                  cancel_event=cancel)
    assert calls == [1600]


def test_four_size_attempts_are_the_absolute_maximum(source, fake_runtime, monkeypatch):
    calls = []
    def render(*args, **kwargs):
        calls.append(kwargs["long_side"])
        raise renderer.KnowledgePdfRenderError("render_png_byte_limit")
    monkeypatch.setattr(renderer, "_render_one", render)
    with pytest.raises(renderer.KnowledgePdfRenderError, match="render_png_byte_limit"):
        renderer.render_pdf_pages(source[0], source_sha256=source[1], page_numbers=[1], adaptive=True)
    assert calls == [1600, 1400, 1200, 1000]


def test_false_resolution_metadata_fails_instead_of_reducing_again(source, fake_runtime, monkeypatch):
    calls = []
    def render(*args, **kwargs):
        calls.append(kwargs["long_side"])
        return png(1400, 700)
    monkeypatch.setattr(renderer, "_render_one", render)
    with pytest.raises(renderer.KnowledgePdfRenderError, match="render_scale_mismatch"):
        renderer.render_pdf_pages(source[0], source_sha256=source[1], page_numbers=[1], adaptive=True)
    assert calls == [1600]


def test_native_nonzero_exit_and_owned_oversize_is_detected_then_group_reaped(tmp_path, monkeypatch):
    target, events = tmp_path / "owned.png", []
    monkeypatch.setattr(renderer, "_enforcement_available", lambda: True)
    monkeypatch.setattr(renderer.signal, "SIGKILL", 9, raising=False)
    class Process:
        pid = 321
        def wait(self, *, timeout):
            events.append(("wait", timeout))
            return 0 if timeout == 2 else -25
    def launch(command, **options):
        target.write_bytes(b"x" * (renderer.MAX_PNG_BYTES + 1))
        events.append(("scale", command[-1]))
        return Process()
    monkeypatch.setattr(renderer.subprocess, "Popen", launch)
    monkeypatch.setattr(renderer.os, "killpg", lambda pid, sig: events.append(("kill", pid, sig)), raising=False)
    with pytest.raises(renderer.KnowledgePdfRenderError, match="render_png_byte_limit"):
        renderer._render_one(Path("/pdftoppm"), tmp_path / "source.pdf", 1, target, 30, long_side=1400)
    assert ("scale", "1400") in events
    assert ("kill", 321, signal.SIGKILL) in events and events[-1] == ("wait", 2)
