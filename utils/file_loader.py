from __future__ import annotations

import io
from typing import BinaryIO

import pdfplumber
from docx import Document


def _read_txt(file_obj: BinaryIO) -> str:
    data = file_obj.read()
    try:
        return data.decode("utf-8")
    except Exception:
        return data.decode("cp949", errors="ignore")


def _read_pdf(file_obj: BinaryIO) -> str:
    text_parts = []
    with pdfplumber.open(file_obj) as pdf:
        for page in pdf.pages:
            content = page.extract_text() or ""
            if content:
                text_parts.append(content)
    return "\n".join(text_parts)


def _read_docx(file_obj: BinaryIO) -> str:
    # docx.Document can read from a file-like object
    doc = Document(file_obj)
    paragraphs = [p.text for p in doc.paragraphs if p.text]
    return "\n".join(paragraphs)


def extract_text_from_upload(uploaded_file) -> str:
    name = (uploaded_file.name or "").lower()
    if name.endswith(".txt"):
        return _read_txt(uploaded_file)
    if name.endswith(".pdf"):
        return _read_pdf(uploaded_file)
    if name.endswith(".docx"):
        return _read_docx(uploaded_file)
    # Fallback: attempt as text
    return _read_txt(uploaded_file)








