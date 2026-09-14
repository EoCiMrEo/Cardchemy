from io import BytesIO

import pytest
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.services.pdf_processor import PDFProcessingError, PDFProcessor


def pdf_bytes(*, pages: int = 1, text: str | None = None, password: str | None = None) -> bytes:
    writer = PdfWriter()
    for _ in range(pages):
        page = writer.add_blank_page(width=612, height=792)
        if text is not None:
            font = DictionaryObject(
                {
                    NameObject("/Type"): NameObject("/Font"),
                    NameObject("/Subtype"): NameObject("/Type1"),
                    NameObject("/BaseFont"): NameObject("/Helvetica"),
                }
            )
            font_reference = writer._add_object(font)
            page[NameObject("/Resources")] = DictionaryObject(
                {
                    NameObject("/Font"): DictionaryObject(
                        {NameObject("/F1"): font_reference}
                    )
                }
            )
            stream = DecodedStreamObject()
            escaped = text.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
            stream.set_data(f"BT /F1 12 Tf 72 720 Td ({escaped}) Tj ET".encode("latin-1"))
            page[NameObject("/Contents")] = writer._add_object(stream)
    if password:
        writer.encrypt(password)
    output = BytesIO()
    writer.write(output)
    return output.getvalue()


def assert_pdf_error(code: str, action) -> None:
    with pytest.raises(PDFProcessingError) as error:
        action()
    assert error.value.code == code


def test_media_type_and_signature_are_both_required():
    assert PDFProcessor.validate_media_type("application/pdf; charset=binary") == "application/pdf"
    assert_pdf_error(
        "unsupported_media_type", lambda: PDFProcessor.validate_media_type("text/plain")
    )
    assert_pdf_error("invalid_pdf_signature", lambda: PDFProcessor.validate_signature(b"not-pdf"))


def test_valid_text_pdf_is_extracted_within_limits():
    content = pdf_bytes(text="Bounded extraction works")
    document = PDFProcessor.extract_text_from_bytes(
        content, max_pages=1, max_extracted_chars=100
    )
    assert document.text == "Bounded extraction works"
    assert len(document.pages) == 1
    assert document.pages[0].page_number == 1
    assert document.pages[0].text == "Bounded extraction works"


@pytest.mark.parametrize(
    "content,code",
    [
        (b"%PDF-1.7\nmalformed", "malformed_pdf"),
        (pdf_bytes(pages=0), "empty_pdf"),
        (pdf_bytes(password="secret"), "encrypted_pdf"),
        (pdf_bytes(), "image_only_pdf"),
    ],
)
def test_pdf_failures_have_stable_safe_codes(content: bytes, code: str):
    assert_pdf_error(
        code,
        lambda: PDFProcessor.extract_text_from_bytes(
            content, max_pages=5, max_extracted_chars=1_000
        ),
    )


def test_page_and_text_limits_stop_processing():
    assert_pdf_error(
        "page_limit_exceeded",
        lambda: PDFProcessor.extract_text_from_bytes(
            pdf_bytes(pages=2, text="text"), max_pages=1, max_extracted_chars=100
        ),
    )
    assert_pdf_error(
        "text_limit_exceeded",
        lambda: PDFProcessor.extract_text_from_bytes(
            pdf_bytes(text="too much text"), max_pages=1, max_extracted_chars=4
        ),
    )


def test_ocr_is_explicitly_unavailable_without_dependencies(monkeypatch):
    monkeypatch.setattr("app.services.pdf_processor.shutil.which", lambda _: None)
    assert_pdf_error(
        "ocr_unavailable",
        lambda: PDFProcessor.extract_text_from_bytes(
            pdf_bytes(),
            max_pages=1,
            max_extracted_chars=100,
            ocr_enabled=True,
        ),
    )


def test_subprocess_boundary_preserves_safe_pdf_errors():
    with pytest.raises(PDFProcessingError) as error:
        PDFProcessor.extract_text_in_subprocess(
            pdf_bytes(),
            max_pages=1,
            max_extracted_chars=100,
            timeout_seconds=10,
            memory_limit_mb=1_024,
        )
    assert error.value.code == "image_only_pdf"
