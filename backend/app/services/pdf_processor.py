"""
pdf_processor.py - PDF Text Extraction

Extracts clean text from PDF files using pypdf.
"""

from io import BytesIO
from typing import List, Dict
import pypdf

class PDFProcessor:
    @staticmethod
    def extract_text_from_bytes(file_content: bytes) -> str:
        """
        Extract text from PDF bytes.
        """
        pdf_file = BytesIO(file_content)
        reader = pypdf.PdfReader(pdf_file)
        
        text = []
        for page in reader.pages:
            content = page.extract_text()
            if content:
                text.append(content)
        
        return "\n\n".join(text)

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 1000, overlap: int = 200) -> List[str]:
        """
        Split text into overlapping chunks for processing.
        """
        chunks = []
        start = 0
        text_len = len(text)

        while start < text_len:
            end = start + chunk_size
            chunk = text[start:end]
            chunks.append(chunk)
            start += chunk_size - overlap
            
        return chunks
