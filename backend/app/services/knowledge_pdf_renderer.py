"""Isolated full-page PNGs from already authenticated original PDF bytes.

This dormant service grants no authorization and makes no provider request.
The caller must authenticate the complete revision and reauthorize before use.
Linux is the only supported enforcement mode; other hosts fail closed. Poppler
is optional in the existing image and must be present before this can be used.
"""
from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import threading
import time

VERSION = "knowledge_pdf_full_page_renderer_v1"
ADAPTIVE_VERSION = "knowledge_pdf_full_page_renderer_v2"
ADAPTIVE_LONG_SIDES = (1600, 1400, 1200, 1000)
MAX_PDF_BYTES = 100 * 1024 * 1024
MAX_PAGE_NUMBER = 100
MAX_RENDER_PAGES = 4
MAX_LONG_SIDE = 1600
MAX_PIXELS = 2_000_000
MAX_PNG_BYTES = 1024 * 1024
MAX_MEMORY_BYTES = 512 * 1024 * 1024
MAX_CPU_COUNT = 4
PAGE_TIMEOUT_SECONDS = 30
TOTAL_TIMEOUT_SECONDS = 120
RENDER_PARAMETERS = {"renderer": "poppler_pdftoppm", "format": "png", "scale_to": MAX_LONG_SIDE,
                     "singlefile": True, "full_page": True, "crop": False,
                     "ocr": False, "annotation": False}


class KnowledgePdfRenderError(RuntimeError):
    """Closed error code; never source bytes, paths or process diagnostics."""
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise KnowledgePdfRenderError(code)


@dataclass(frozen=True)
class RenderedPdfPage:
    physical_page: int
    pdf_sha256: str
    png_bytes: bytes
    sha256: str
    width: int
    height: int
    renderer_sha256: str
    render_long_side: int = MAX_LONG_SIDE

    def image_binding(self, document_id: str) -> dict:
        """Attach a caller-issued document identity without granting access."""
        _require(type(document_id) is str and 0 < len(document_id) <= 64, "render_document_id_invalid")
        return {"document_id": document_id, "physical_page": self.physical_page,
                "pdf_sha256": self.pdf_sha256, "png_bytes": self.png_bytes,
                "sha256": self.sha256, "width": self.width, "height": self.height,
                "bytes": len(self.png_bytes), "renderer_sha256": self.renderer_sha256,
                "render": dict(RENDER_PARAMETERS, scale_to=self.render_long_side)}


def _admit_source(pdf_bytes: bytes, source_sha256: str, page_numbers: list[int]) -> None:
    _require(type(pdf_bytes) is bytes and 0 < len(pdf_bytes) <= MAX_PDF_BYTES
             and pdf_bytes.startswith(b"%PDF-"), "render_pdf_invalid")
    _require(type(source_sha256) is str and len(source_sha256) == 64
             and all(c in "0123456789abcdef" for c in source_sha256)
             and hashlib.sha256(pdf_bytes).hexdigest() == source_sha256, "render_source_mismatch")
    _require(type(page_numbers) is list and 1 <= len(page_numbers) <= MAX_RENDER_PAGES
             and all(type(page) is int and 1 <= page <= MAX_PAGE_NUMBER for page in page_numbers)
             and len(set(page_numbers)) == len(page_numbers), "render_page_roster_invalid")


def _enforcement_available() -> bool:
    return sys.platform.startswith("linux") and hasattr(os, "sched_getaffinity") and hasattr(os, "sched_setaffinity")


def _renderer_path(path: Path | None) -> Path:
    found = shutil.which("pdftoppm") if path is None else str(path)
    _require(bool(found), "render_poppler_unavailable")
    executable = Path(found)
    _require(executable.is_absolute() and executable.is_file() and not executable.is_symlink(),
             "render_poppler_unavailable")
    return executable


def _child_environment(directory: Path) -> dict[str, str]:
    # Absolute executables need no PATH. No provider, SMTP or signing settings
    # are inherited by the parser; native loaders use their normal OS search.
    return {"LANG": "C", "LC_ALL": "C", "HOME": str(directory),
            "TMPDIR": str(directory), "PYTHONNOUSERSITE": "1", "PYTHONUTF8": "1"}


def _kill_group_and_reap(process) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    except OSError:
        raise KnowledgePdfRenderError("render_cleanup_failed") from None
    try:
        process.wait(timeout=2)
    except (subprocess.TimeoutExpired, OSError):
        raise KnowledgePdfRenderError("render_cleanup_failed") from None


def _render_one(executable: Path, source: Path, page: int, target: Path, timeout: float,
                *, cancel_event: threading.Event | None = None, long_side: int = MAX_LONG_SIDE) -> bytes:
    _require(_enforcement_available(), "render_resource_mode_unavailable")
    _require(0 < timeout <= PAGE_TIMEOUT_SECONDS and not target.exists(), "render_admission_invalid")
    _require(type(long_side) is int and long_side in ADAPTIVE_LONG_SIDES, "render_admission_invalid")
    command = [sys.executable, "-I", str(Path(__file__).resolve()), "--render-child",
               str(executable), str(source), str(page), str(target.with_suffix("")), str(timeout), str(os.getpid())]
    if long_side != MAX_LONG_SIDE:
        command.append(str(long_side))
    process = None
    try:
        process = subprocess.Popen(command, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                                   stderr=subprocess.DEVNULL, env=_child_environment(source.parent),
                                   cwd=source.parent, start_new_session=True, close_fds=True)
        if cancel_event is None:
            try:
                status = process.wait(timeout=timeout)
            except subprocess.TimeoutExpired:
                raise KnowledgePdfRenderError("render_timeout") from None
        else:
            deadline = time.monotonic() + timeout
            while True:
                _require(not cancel_event.is_set(), "render_cancelled")
                remaining = deadline - time.monotonic()
                _require(remaining > 0, "render_timeout")
                try:
                    status = process.wait(timeout=min(0.1, remaining))
                    break
                except subprocess.TimeoutExpired:
                    continue
        # The child's unchanged 1 MiB+1 file limit can end native writing with
        # SIGXFSZ. A safe owned regular target over the accepted byte ceiling
        # proves oversize even when the child did not exit successfully.
        if target.is_file() and not target.is_symlink():
            _require(target.stat().st_size <= MAX_PNG_BYTES, "render_png_byte_limit")
        _require(status == 0, "render_failed")
        _require(target.is_file() and not target.is_symlink(), "render_failed")
        with target.open("rb") as stream:
            raw = stream.read(MAX_PNG_BYTES + 1)
        _require(0 < len(raw) <= MAX_PNG_BYTES, "render_png_byte_limit")
        return raw
    except OSError:
        raise KnowledgePdfRenderError("render_unavailable") from None
    finally:
        if process is not None:
            # Kill the entire isolated session even if the direct child exited.
            # A timeout, caller interruption or descendant never escapes cleanup.
            _kill_group_and_reap(process)


def _render_adaptive(executable: Path, source: Path, page: int, directory: Path, timeout: float,
                     *, cancel_event: threading.Event | None = None) -> tuple[bytes, int]:
    """Reduce full-page resolution only after definitive oversize, within one deadline."""
    deadline = time.monotonic() + timeout
    for long_side in ADAPTIVE_LONG_SIDES:
        _require(cancel_event is None or not cancel_event.is_set(), "render_cancelled")
        remaining = deadline - time.monotonic()
        _require(remaining > 0, "render_timeout")
        target = directory / f"page-{page:03d}-{long_side}.png"
        try:
            raw = _render_one(executable, source, page, target, remaining,
                              cancel_event=cancel_event, long_side=long_side)
        except KnowledgePdfRenderError as error:
            if error.code != "render_png_byte_limit" or long_side == ADAPTIVE_LONG_SIDES[-1]:
                raise
            continue
        _require(time.monotonic() <= deadline, "render_timeout")
        _require(cancel_event is None or not cancel_event.is_set(), "render_cancelled")
        return raw, long_side
    raise KnowledgePdfRenderError("render_png_byte_limit")


def render_pdf_pages(pdf_bytes: bytes, *, source_sha256: str,
                     page_numbers: list[int], renderer_path: Path | None = None,
                     cancel_event: threading.Event | None = None,
                     adaptive: bool = False) -> tuple[RenderedPdfPage, ...]:
    """Synchronously render 1–4 selected physical pages in isolated children.

    Intended for a worker's bounded thread, never the API event loop. No PDF is
    parsed in the parent. The complete source hash is repeated before writing
    its owned temporary copy. Results are returned atomically; any failure
    clears all temporary source/raster files and returns no partial pages.
    """
    _admit_source(pdf_bytes, source_sha256, page_numbers)
    _require(type(adaptive) is bool, "render_admission_invalid")
    _require(cancel_event is None or isinstance(cancel_event, threading.Event), "render_cancel_control_invalid")
    _require(cancel_event is None or not cancel_event.is_set(), "render_cancelled")
    _require(_enforcement_available(), "render_resource_mode_unavailable")
    executable = _renderer_path(renderer_path)
    try:
        with executable.open("rb") as stream:
            renderer_sha256 = hashlib.file_digest(stream, "sha256").hexdigest()
    except OSError:
        raise KnowledgePdfRenderError("render_poppler_unavailable") from None
    from app.ai.source_judgment_visual import inspect_png, VisualSourceJudgmentError
    started = time.monotonic()
    result = []
    try:
        with tempfile.TemporaryDirectory(prefix="cardchemy-pdf-render-") as temporary:
            directory = Path(temporary)
            directory.chmod(0o700)
            source = directory / "source.pdf"
            with source.open("xb") as stream:
                stream.write(pdf_bytes)
            source.chmod(0o400)
            for page in page_numbers:
                _require(cancel_event is None or not cancel_event.is_set(), "render_cancelled")
                remaining = TOTAL_TIMEOUT_SECONDS - (time.monotonic() - started)
                _require(remaining > 0, "render_total_timeout")
                arguments = (executable, source, page, directory / f"page-{page:03d}.png",
                             min(PAGE_TIMEOUT_SECONDS, remaining))
                if adaptive:
                    raw, long_side = _render_adaptive(executable, source, page, directory,
                        min(PAGE_TIMEOUT_SECONDS, remaining), cancel_event=cancel_event)
                else:
                    raw = _render_one(*arguments) if cancel_event is None else _render_one(*arguments, cancel_event=cancel_event)
                    long_side = MAX_LONG_SIDE
                try:
                    metadata = inspect_png(raw)
                except VisualSourceJudgmentError:
                    raise KnowledgePdfRenderError("render_png_invalid") from None
                if adaptive:
                    _require(max(metadata["width"], metadata["height"]) == long_side,
                             "render_scale_mismatch")
                _require(time.monotonic() - started <= TOTAL_TIMEOUT_SECONDS, "render_total_timeout")
                _require(cancel_event is None or not cancel_event.is_set(), "render_cancelled")
                result.append(RenderedPdfPage(physical_page=page, pdf_sha256=source_sha256, png_bytes=raw,
                    sha256=metadata["sha256"], width=metadata["width"], height=metadata["height"],
                    renderer_sha256=renderer_sha256, render_long_side=long_side))
    except OSError:
        raise KnowledgePdfRenderError("render_storage_unavailable") from None
    return tuple(result)


def _child_parent_guard(expected_parent: int) -> None:
    """Kill the native renderer if its supervising worker abruptly exits."""
    import ctypes
    _require(type(expected_parent) is int and expected_parent >= 1 and
             os.getppid() == expected_parent, "render_parent_unavailable")
    libc = ctypes.CDLL(None, use_errno=True)
    libc.prctl.argtypes = [ctypes.c_int, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong, ctypes.c_ulong]
    libc.prctl.restype = ctypes.c_int
    # PR_SET_PDEATHSIG. Check the parent again to close the registration race.
    _require(libc.prctl(1, signal.SIGKILL, 0, 0, 0) == 0 and os.getppid() == expected_parent,
             "render_parent_guard_unavailable")


def _child_limits(timeout: float) -> None:
    """Fail closed before native parsing; every limit must be installed."""
    _require(_enforcement_available() and 0 < timeout <= PAGE_TIMEOUT_SECONDS,
             "render_resource_mode_unavailable")
    import resource
    allowed = sorted(os.sched_getaffinity(0))[:MAX_CPU_COUNT]
    _require(bool(allowed), "render_resource_mode_unavailable")
    os.sched_setaffinity(0, allowed)
    resource.setrlimit(resource.RLIMIT_AS, (MAX_MEMORY_BYTES, MAX_MEMORY_BYTES))
    cpu_seconds = max(1, math.ceil(timeout))
    resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))
    resource.setrlimit(resource.RLIMIT_FSIZE, (MAX_PNG_BYTES + 1, MAX_PNG_BYTES + 1))
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (64, 64))


def _child_main(arguments: list[str]) -> int:
    if len(arguments) not in (7, 8) or arguments[0] != "--render-child":
        return 2
    try:
        executable, source, page, prefix, timeout, parent = arguments[1:7]
        long_side = int(arguments[7]) if len(arguments) == 8 else MAX_LONG_SIDE
        _require(long_side in ADAPTIVE_LONG_SIDES, "render_admission_invalid")
        number, seconds = int(page), float(timeout)
        _require(1 <= number <= MAX_PAGE_NUMBER, "render_page_roster_invalid")
        _child_parent_guard(int(parent))
        _child_limits(seconds)
        command = [executable, "-f", str(number), "-l", str(number), "-singlefile", "-png",
                   "-hide-annotations", "-scale-to", str(long_side), source, prefix]
        os.execve(executable, command, _child_environment(Path(source).parent))
    except BaseException:
        return 2
    return 2


if __name__ == "__main__":
    sys.exit(_child_main(sys.argv[1:]))
