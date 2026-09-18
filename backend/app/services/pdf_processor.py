"""Bounded PDF validation, text extraction, and optional local OCR."""

from __future__ import annotations

from io import BytesIO
import math
import multiprocessing
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Final

import pypdf
from pypdf.errors import FileNotDecryptedError, PdfReadError

from app.ai.contracts import ExtractedDocument, ExtractedPage


PDF_MEDIA_TYPES: Final[frozenset[str]] = frozenset(
    {"application/pdf", "application/x-pdf"}
)


class PDFProcessingError(ValueError):
    """A safe, categorized PDF failure suitable for a job response."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.safe_message = message


class PDFProcessor:
    @staticmethod
    def validate_media_type(media_type: str | None) -> str:
        normalized = (media_type or "").split(";", 1)[0].strip().lower()
        if normalized not in PDF_MEDIA_TYPES:
            raise PDFProcessingError(
                "unsupported_media_type",
                "The uploaded file must use the application/pdf media type.",
            )
        return normalized

    @staticmethod
    def validate_signature(file_content: bytes) -> None:
        if not file_content.startswith(b"%PDF-"):
            raise PDFProcessingError(
                "invalid_pdf_signature",
                "The uploaded file does not have a valid PDF signature.",
            )

    @classmethod
    def extract_text_from_bytes(
        cls,
        file_content: bytes,
        *,
        max_pages: int,
        max_extracted_chars: int,
        ocr_enabled: bool = False,
        ocr_language: str = "eng",
        ocr_dpi: int = 200,
        ocr_page_timeout_seconds: int = 30,
    ) -> ExtractedDocument:
        """Extract text within hard page/character bounds.

        This synchronous method must run in the dedicated worker's thread, not
        on the API event loop. OCR is attempted only when native extraction
        yields no non-whitespace text.
        """

        cls.validate_signature(file_content)
        try:
            reader = pypdf.PdfReader(BytesIO(file_content), strict=True)
            if reader.is_encrypted:
                raise PDFProcessingError(
                    "encrypted_pdf",
                    "Encrypted or password-protected PDFs are not supported.",
                )
            page_count = len(reader.pages)
            if page_count == 0:
                raise PDFProcessingError("empty_pdf", "The PDF does not contain any pages.")
            if page_count > max_pages:
                raise PDFProcessingError(
                    "page_limit_exceeded",
                    f"The PDF exceeds the configured limit of {max_pages} pages.",
                )

            pages: list[ExtractedPage] = []
            extracted_chars = 0
            for page_number, page in enumerate(reader.pages, start=1):
                content = page.extract_text() or ""
                extracted_chars += len(content)
                if extracted_chars > max_extracted_chars:
                    raise PDFProcessingError(
                        "text_limit_exceeded",
                        "The extracted PDF text exceeds the configured character limit.",
                    )
                pages.append(ExtractedPage(page_number=page_number, text=content.strip()))
        except PDFProcessingError:
            raise
        except (PdfReadError, FileNotDecryptedError, EOFError, OSError, ValueError) as exc:
            raise PDFProcessingError(
                "malformed_pdf",
                "The PDF is malformed or cannot be read.",
            ) from exc

        document = ExtractedDocument(pages=pages)
        if document.text:
            return document
        if not ocr_enabled:
            raise PDFProcessingError(
                "image_only_pdf",
                "No selectable text was found. Enable OCR or upload a text-based PDF.",
            )
        return cls._extract_with_ocr(
            file_content,
            page_count=page_count,
            max_extracted_chars=max_extracted_chars,
            language=ocr_language,
            dpi=ocr_dpi,
            page_timeout_seconds=ocr_page_timeout_seconds,
        )

    @classmethod
    def extract_text_in_subprocess(
        cls,
        file_content: bytes,
        *,
        max_pages: int,
        max_extracted_chars: int,
        timeout_seconds: int,
        memory_limit_mb: int,
        ocr_enabled: bool = False,
        ocr_language: str = "eng",
        ocr_dpi: int = 200,
        ocr_page_timeout_seconds: int = 30,
    ) -> ExtractedDocument:
        """Run the parser in a child that can be killed on timeout.

        Linux workers also apply CPU and address-space limits before parsing.
        The parent receives only bounded text or a stable public error tuple.
        """

        context = multiprocessing.get_context("spawn")
        receive_connection, send_connection = context.Pipe(duplex=False)
        process = context.Process(
            target=_extract_child,
            args=(
                send_connection,
                file_content,
                {
                    "max_pages": max_pages,
                    "max_extracted_chars": max_extracted_chars,
                    "ocr_enabled": ocr_enabled,
                    "ocr_language": ocr_language,
                    "ocr_dpi": ocr_dpi,
                    "ocr_page_timeout_seconds": ocr_page_timeout_seconds,
                },
                timeout_seconds,
                memory_limit_mb,
            ),
            daemon=True,
        )
        process.start()
        send_connection.close()
        try:
            if not receive_connection.poll(timeout_seconds):
                process.terminate()
                process.join(2)
                if process.is_alive():
                    process.kill()
                    process.join(2)
                raise PDFProcessingError(
                    "pdf_extraction_timeout",
                    "PDF extraction exceeded the configured timeout.",
                )
            succeeded, value, message = receive_connection.recv()
        except EOFError as exc:
            raise PDFProcessingError(
                "pdf_resource_limit",
                "PDF extraction stopped after reaching a worker resource limit.",
            ) from exc
        finally:
            receive_connection.close()
            process.join(2)
            if process.is_alive():
                process.terminate()
                process.join(2)

        if not succeeded:
            raise PDFProcessingError(value, message)
        return value

    @staticmethod
    def _extract_with_ocr(
        file_content: bytes,
        *,
        page_count: int,
        max_extracted_chars: int,
        language: str,
        dpi: int,
        page_timeout_seconds: int,
    ) -> ExtractedDocument:
        pdftoppm = shutil.which("pdftoppm")
        tesseract = shutil.which("tesseract")
        if not pdftoppm or not tesseract:
            raise PDFProcessingError(
                "ocr_unavailable",
                "OCR is enabled but the worker is missing Poppler or Tesseract.",
            )

        pages: list[ExtractedPage] = []
        total_chars = 0
        with tempfile.TemporaryDirectory(prefix="flashcard-ocr-") as temporary_directory:
            directory = Path(temporary_directory)
            source_path = directory / "source.pdf"
            source_path.write_bytes(file_content)
            for page_number in range(1, page_count + 1):
                output_prefix = directory / f"page-{page_number}"
                try:
                    render = subprocess.run(
                        [
                            pdftoppm,
                            "-f",
                            str(page_number),
                            "-l",
                            str(page_number),
                            "-singlefile",
                            "-png",
                            "-r",
                            str(dpi),
                            str(source_path),
                            str(output_prefix),
                        ],
                        capture_output=True,
                        check=False,
                        timeout=page_timeout_seconds,
                    )
                    if render.returncode != 0:
                        raise PDFProcessingError(
                            "ocr_failed", "OCR could not render one of the PDF pages."
                        )
                    image_path = output_prefix.with_suffix(".png")
                    recognize = subprocess.run(
                        [tesseract, str(image_path), "stdout", "-l", language],
                        capture_output=True,
                        check=False,
                        timeout=page_timeout_seconds,
                    )
                    if recognize.returncode != 0:
                        raise PDFProcessingError(
                            "ocr_failed", "OCR could not recognize one of the PDF pages."
                        )
                except subprocess.TimeoutExpired as exc:
                    raise PDFProcessingError(
                        "ocr_timeout", "OCR exceeded the configured per-page timeout."
                    ) from exc

                page_text = recognize.stdout.decode("utf-8", errors="replace").strip()
                total_chars += len(page_text)
                if total_chars > max_extracted_chars:
                    raise PDFProcessingError(
                        "text_limit_exceeded",
                        "The OCR output exceeds the configured character limit.",
                    )
                pages.append(ExtractedPage(page_number=page_number, text=page_text))

        document = ExtractedDocument(pages=pages)
        if not document.text:
            raise PDFProcessingError(
                "image_only_pdf",
                "OCR did not find readable text in the PDF.",
            )
        return document


def _extract_child(
    connection,
    file_content: bytes,
    extraction_options: dict,
    timeout_seconds: int,
    memory_limit_mb: int,
) -> None:
    """Child-process entry point; it must remain top-level for Windows spawn."""

    # Windows/spawn children have fresh logging state. Parser warnings can
    # include crafted document bytes and must receive the same safe sinks.
    from app.observability import configure_logging
    configure_logging()
    try:
        try:
            import resource

            memory_bytes = memory_limit_mb * 1024 * 1024
            resource.setrlimit(resource.RLIMIT_AS, (memory_bytes, memory_bytes))
            cpu_seconds = max(1, math.ceil(timeout_seconds))
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds + 1))
        except (ImportError, OSError, ValueError):
            # Windows has no ``resource`` module. The hard parent timeout still
            # applies; production Linux containers receive both protections.
            pass

        text = PDFProcessor.extract_text_from_bytes(file_content, **extraction_options)
        connection.send((True, text, ""))
    except PDFProcessingError as exc:
        connection.send((False, exc.code, exc.safe_message))
    except BaseException:
        connection.send(
            (
                False,
                "pdf_processing_failed",
                "The PDF could not be processed safely.",
            )
        )
    finally:
        connection.close()
