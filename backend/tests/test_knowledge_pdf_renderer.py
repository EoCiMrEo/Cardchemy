"""Synthetic, provider-free admission, raster and process-fence contracts."""
from __future__ import annotations

import hashlib
from pathlib import Path
import signal
import struct
import subprocess
import sys
import threading
from types import SimpleNamespace
import zlib

import pytest

from app.services import knowledge_pdf_renderer as renderer
from tests.test_pdf_processor import pdf_bytes


def png(width=1200, height=1600) -> bytes:
    def chunk(kind, data):
        return struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data) & 0xffffffff)
    header = struct.pack(">IIBBBBB", width, height, 8, 0, 0, 0, 0)
    pixels = b"\0" + b"\xff" * width
    return b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", header) + chunk(b"IDAT", zlib.compress(pixels * height)) + chunk(b"IEND", b"")


@pytest.fixture
def source():
    raw = pdf_bytes(pages=4, text="Synthetic original lecture page")
    return raw, hashlib.sha256(raw).hexdigest()


@pytest.fixture
def fake_runtime(tmp_path, monkeypatch):
    executable = tmp_path / "pdftoppm"
    executable.write_bytes(b"synthetic-renderer")
    monkeypatch.setattr(renderer, "_enforcement_available", lambda: True)
    monkeypatch.setattr(renderer, "_renderer_path", lambda _: executable)
    return executable


@pytest.mark.parametrize("mutation", ["signature", "empty", "oversize", "sha", "mutable", "zero", "negative", "boolean", "duplicate", "five", "above_archive", "tuple"])
def test_invalid_inputs_are_rejected_before_process_or_temp_access(source, monkeypatch, mutation):
    raw, sha = source
    pages = [1]
    if mutation == "signature": raw = b"not-a-pdf"
    elif mutation == "empty": raw = b""
    elif mutation == "oversize": monkeypatch.setattr(renderer, "MAX_PDF_BYTES", len(raw) - 1)
    elif mutation == "sha": sha = "0" * 64
    elif mutation == "mutable": raw = bytearray(raw)
    elif mutation == "zero": pages = [0]
    elif mutation == "negative": pages = [-1]
    elif mutation == "boolean": pages = [True]
    elif mutation == "duplicate": pages = [1, 1]
    elif mutation == "five": pages = [1, 2, 3, 4, 5]
    elif mutation == "above_archive": pages = [101]
    else: pages = (1,)
    monkeypatch.setattr(renderer.tempfile, "TemporaryDirectory", lambda **_: pytest.fail("admission must precede source writes"))
    monkeypatch.setattr(renderer.subprocess, "Popen", lambda *a, **k: pytest.fail("invalid source reached parser"))
    with pytest.raises(renderer.KnowledgePdfRenderError):
        renderer.render_pdf_pages(raw, source_sha256=sha, page_numbers=pages)


def test_unsupported_host_fails_closed_before_renderer_or_temp_access(source, monkeypatch):
    monkeypatch.setattr(renderer, "_enforcement_available", lambda: False)
    monkeypatch.setattr(renderer, "_renderer_path", lambda _: pytest.fail("unsupported limits cannot run renderer"))
    with pytest.raises(renderer.KnowledgePdfRenderError, match="render_resource_mode_unavailable"):
        renderer.render_pdf_pages(source[0], source_sha256=source[1], page_numbers=[1])


def test_four_full_pages_preserve_order_hash_bindings_and_cleanup(source, fake_runtime, monkeypatch):
    paths, calls = [], []
    raw_png = png()
    def render(executable, pdf, page, target, timeout):
        assert executable == fake_runtime and pdf.read_bytes() == source[0]
        assert timeout <= 30 and target.parent == pdf.parent
        paths.append(pdf.parent)
        calls.append(page)
        target.write_bytes(raw_png)
        return raw_png
    monkeypatch.setattr(renderer, "_render_one", render)
    result = renderer.render_pdf_pages(source[0], source_sha256=source[1], page_numbers=[4, 1, 3, 2])
    assert calls == [4, 1, 3, 2]
    assert len(result) == 4 and all(not p.exists() for p in paths)
    for page in result:
        binding = page.image_binding("issued-document")
        assert binding["pdf_sha256"] == source[1]
        assert binding["sha256"] == hashlib.sha256(raw_png).hexdigest()
        assert binding["png_bytes"] == raw_png and binding["render"] == renderer.RENDER_PARAMETERS
        assert binding["width"] == 1200 and binding["height"] == 1600
        assert binding["renderer_sha256"] == hashlib.sha256(fake_runtime.read_bytes()).hexdigest()


@pytest.mark.parametrize("bad_png", [b"not-png", png() + b"trailing", png(1601, 20), png(1600, 1600)])
def test_bad_or_oversize_raster_returns_no_partial_images_and_cleans_source(source, fake_runtime, monkeypatch, bad_png):
    paths, calls = [], []
    def render(executable, pdf, page, target, timeout):
        paths.append(pdf.parent)
        calls.append(page)
        return png() if page == 1 else bad_png
    monkeypatch.setattr(renderer, "_render_one", render)
    with pytest.raises(renderer.KnowledgePdfRenderError, match="render_png_invalid"):
        renderer.render_pdf_pages(source[0], source_sha256=source[1], page_numbers=[1, 2, 3])
    assert calls == [1, 2] and all(not path.exists() for path in paths)


def test_total_deadline_stops_before_next_page_and_cleans_owned_source(source, fake_runtime, monkeypatch):
    times = iter([0, 0, 120, 121])
    monkeypatch.setattr(renderer.time, "monotonic", lambda: next(times))
    paths, calls = [], []
    def render(executable, pdf, page, target, timeout):
        paths.append(pdf.parent)
        calls.append(page)
        return png()
    monkeypatch.setattr(renderer, "_render_one", render)
    with pytest.raises(renderer.KnowledgePdfRenderError, match="render_total_timeout"):
        renderer.render_pdf_pages(source[0], source_sha256=source[1], page_numbers=[1, 2])
    assert calls == [1] and all(not path.exists() for path in paths)


def test_cancellation_before_start_creates_no_source_or_child(source, monkeypatch):
    cancel = threading.Event()
    cancel.set()
    monkeypatch.setattr(renderer.tempfile, "TemporaryDirectory", lambda **_: pytest.fail("cancelled source cannot be staged"))
    with pytest.raises(renderer.KnowledgePdfRenderError, match="render_cancelled"):
        renderer.render_pdf_pages(source[0], source_sha256=source[1], page_numbers=[1], cancel_event=cancel)


def test_live_cancel_event_interrupts_poll_wait_and_kills_group_without_next_page(tmp_path, monkeypatch):
    monkeypatch.setattr(renderer, "_enforcement_available", lambda: True)
    monkeypatch.setattr(renderer.signal, "SIGKILL", 9, raising=False)
    cancel, calls = threading.Event(), []
    class Process:
        pid = 456
        def wait(self, *, timeout):
            calls.append(("wait", timeout))
            if timeout != 2:
                cancel.set()
                raise subprocess.TimeoutExpired("hidden", timeout)
            return 0
    monkeypatch.setattr(renderer.subprocess, "Popen", lambda *a, **k: Process())
    monkeypatch.setattr(renderer.os, "killpg", lambda pid, sig: calls.append(("kill", pid, sig)), raising=False)
    with pytest.raises(renderer.KnowledgePdfRenderError, match="render_cancelled"):
        renderer._render_one(Path("/pdftoppm"), tmp_path / "source.pdf", 1, tmp_path / "page.png", 30, cancel_event=cancel)
    assert calls == [("wait", 0.1), ("kill", 456, 9), ("wait", 2)]


def test_cancel_during_render_cleans_source_and_discards_completed_page(source, fake_runtime, monkeypatch):
    cancel, paths, pages = threading.Event(), [], []
    def render(executable, pdf, page, target, timeout, *, cancel_event):
        assert cancel_event is cancel
        paths.append(pdf.parent)
        pages.append(page)
        cancel.set()
        return png()
    monkeypatch.setattr(renderer, "_render_one", render)
    with pytest.raises(renderer.KnowledgePdfRenderError, match="render_cancelled"):
        renderer.render_pdf_pages(source[0], source_sha256=source[1], page_numbers=[1, 2], cancel_event=cancel)
    assert pages == [1] and all(not path.exists() for path in paths)


def test_child_limit_installation_is_complete_and_failure_never_executes(monkeypatch):
    calls = []
    limits = SimpleNamespace(RLIMIT_AS=1, RLIMIT_CPU=2, RLIMIT_FSIZE=3, RLIMIT_CORE=4,
                             RLIMIT_NOFILE=5, setrlimit=lambda key, value: calls.append((key, value)))
    monkeypatch.setitem(sys.modules, "resource", limits)
    monkeypatch.setattr(renderer, "_enforcement_available", lambda: True)
    monkeypatch.setattr(renderer.os, "sched_getaffinity", lambda _: {9, 8, 6, 5, 2}, raising=False)
    monkeypatch.setattr(renderer.os, "sched_setaffinity", lambda _, cores: calls.append(("affinity", cores)), raising=False)
    renderer._child_limits(29.1)
    assert calls == [("affinity", [2, 5, 6, 8]), (1, (536870912, 536870912)), (2, (30, 30)),
                     (3, (1048577, 1048577)), (4, (0, 0)), (5, (64, 64))]
    monkeypatch.setattr(limits, "setrlimit", lambda *_: (_ for _ in ()).throw(OSError("synthetic private diagnostic")))
    monkeypatch.setattr(renderer, "_child_parent_guard", lambda _: None)
    monkeypatch.setattr(renderer.os, "execve", lambda *a: pytest.fail("uninstalled limits reached parser"))
    assert renderer._child_main(["--render-child", "/pdftoppm", "/source.pdf", "1", "/page", "30", "123"]) == 2


def test_child_exec_uses_full_media_page_no_crop_ocr_or_annotations_and_scrubbed_environment(monkeypatch):
    installed = []
    monkeypatch.setattr(renderer, "_child_parent_guard", lambda parent: installed.append(("parent", parent)))
    monkeypatch.setattr(renderer, "_child_limits", lambda timeout: installed.append(timeout))
    def execute(executable, command, environment):
        assert installed == [("parent", 123), 30]
        assert executable == "/pdftoppm"
        assert command == ["/pdftoppm", "-f", "3", "-l", "3", "-singlefile", "-png",
                           "-hide-annotations", "-scale-to", "1600", "/source.pdf", "/page"]
        assert set(environment) == {"LANG", "LC_ALL", "HOME", "TMPDIR", "PYTHONNOUSERSITE", "PYTHONUTF8"}
        raise SystemExit(0)  # Simulate successful exec, intercepted by the closed child boundary.
    monkeypatch.setattr(renderer.os, "execve", execute)
    assert renderer._child_main(["--render-child", "/pdftoppm", "/source.pdf", "3", "/page", "30", "123"]) == 2


@pytest.mark.parametrize("failure", ["none", "initial_parent", "registration", "race"])
def test_parent_death_guard_is_installed_and_registration_race_is_closed(monkeypatch, failure):
    import ctypes
    calls = []
    class Prctl:
        def __call__(self, *args):
            calls.append(args)
            return -1 if failure == "registration" else 0
    monkeypatch.setattr(ctypes, "CDLL", lambda *a, **k: SimpleNamespace(prctl=Prctl()))
    monkeypatch.setattr(renderer.signal, "SIGKILL", 9, raising=False)
    parents = iter([999 if failure == "initial_parent" else 123, 999 if failure == "race" else 123])
    monkeypatch.setattr(renderer.os, "getppid", lambda: next(parents))
    if failure == "none": renderer._child_parent_guard(123)
    else:
        with pytest.raises(renderer.KnowledgePdfRenderError): renderer._child_parent_guard(123)
    assert calls == ([] if failure == "initial_parent" else [(1, 9, 0, 0, 0)])


def test_container_pid_one_is_a_valid_supervising_parent(monkeypatch):
    import ctypes
    class Prctl:
        def __call__(self, *args): return 0
    monkeypatch.setattr(ctypes, "CDLL", lambda *a, **k: SimpleNamespace(prctl=Prctl()))
    monkeypatch.setattr(renderer.signal, "SIGKILL", 9, raising=False)
    monkeypatch.setattr(renderer.os, "getppid", lambda: 1)
    renderer._child_parent_guard(1)


@pytest.mark.parametrize("failure", ["timeout", "failed", "interrupted", "success"])
def test_every_started_process_group_is_killed_and_reaped_without_retry(tmp_path, monkeypatch, failure):
    monkeypatch.setattr(renderer, "_enforcement_available", lambda: True)
    monkeypatch.setattr(renderer.signal, "SIGKILL", 9, raising=False)
    target = tmp_path / "page.png"
    events = []
    class Process:
        pid = 321
        def wait(self, *, timeout):
            events.append(("wait", timeout))
            if timeout != 2:
                if failure == "timeout": raise subprocess.TimeoutExpired("hidden", timeout)
                if failure == "interrupted": raise KeyboardInterrupt()
                return 1 if failure == "failed" else 0
            return 0
    def launch(command, **options):
        events.append(("spawn", command, options))
        target.write_bytes(png())
        return Process()
    monkeypatch.setattr(renderer.subprocess, "Popen", launch)
    monkeypatch.setattr(renderer.os, "killpg", lambda pid, sig: events.append(("killpg", pid, sig)), raising=False)
    if failure == "success":
        assert renderer._render_one(Path("/pdftoppm"), tmp_path / "source.pdf", 1, target, 30) == png()
    else:
        error = KeyboardInterrupt if failure == "interrupted" else renderer.KnowledgePdfRenderError
        with pytest.raises(error):
            renderer._render_one(Path("/pdftoppm"), tmp_path / "source.pdf", 1, target, 30)
    assert len([e for e in events if e[0] == "spawn"]) == 1
    assert ("killpg", 321, signal.SIGKILL) in events and events[-1] == ("wait", 2)
    options = events[0][2]
    assert options["start_new_session"] and options["close_fds"]
    assert options["stdout"] == options["stderr"] == subprocess.DEVNULL
    assert "PATH" not in options["env"] and "RAG_SOURCE_JUDGE_API_KEY" not in options["env"]


def test_no_poppler_or_unsafe_executable_has_no_render_fallback(tmp_path, monkeypatch):
    monkeypatch.setattr(renderer.shutil, "which", lambda _: None)
    with pytest.raises(renderer.KnowledgePdfRenderError, match="render_poppler_unavailable"):
        renderer._renderer_path(None)
    with pytest.raises(renderer.KnowledgePdfRenderError, match="render_poppler_unavailable"):
        renderer._renderer_path(Path("relative-poppler"))


def test_default_image_has_no_unconditional_poppler_and_existing_extractor_is_separate():
    root = Path(__file__).resolve().parents[1]
    image = (root / "Dockerfile").read_text()
    assert 'ARG INSTALL_OCR=false' in image
    assert 'if [ "$INSTALL_OCR" = "true" ]' in image
    assert "poppler-utils" in image
    extraction = (root / "app/services/pdf_processor.py").read_text()
    assert "knowledge_pdf_renderer" not in extraction
