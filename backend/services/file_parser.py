import io
from docx import Document
import fitz  # PyMuPDF


def extract_text_from_docx(file_bytes: bytes) -> str:
    doc = Document(io.BytesIO(file_bytes))
    paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
    return "\n".join(paragraphs)


def extract_text_from_pdf(file_bytes: bytes) -> str:
    pdf = fitz.open(stream=file_bytes, filetype="pdf")
    pages = [page.get_text() for page in pdf]
    pdf.close()
    return "\n".join(pages)


def extract_text(file_bytes: bytes) -> str:
    # Detect by magic bytes: DOCX is a ZIP (PK header), PDF starts with %PDF
    if file_bytes[:4] == b"PK\x03\x04":
        return extract_text_from_docx(file_bytes)
    elif file_bytes[:4] == b"%PDF":
        return extract_text_from_pdf(file_bytes)
    else:
        raise ValueError("Unsupported file type. Only .docx and .pdf are accepted.")
