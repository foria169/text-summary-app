from __future__ import annotations

import io
from typing import Optional


def build_txt_bytes(text: str) -> bytes:
    return text.encode("utf-8")


def build_pdf_bytes(text: str) -> bytes:
    try:
        from reportlab.lib.pagesizes import A4
        from reportlab.pdfgen import canvas
        from reportlab.lib.units import mm
    except Exception as e:
        raise RuntimeError("reportlab 패키지가 필요합니다. requirements.txt를 설치하세요.") from e

    buffer = io.BytesIO()
    c = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    # Basic word wrapping
    margin = 20 * mm
    max_width = width - margin * 2
    text_obj = c.beginText(margin, height - margin)
    text_obj.setFont("Helvetica", 11)

    def wrap_line(line: str, charset_width: float = 6.0) -> list[str]:
        # naive wrap by character count approximation
        max_chars = int(max_width // charset_width)
        out = []
        while len(line) > max_chars:
            out.append(line[:max_chars])
            line = line[max_chars:]
        out.append(line)
        return out

    for para in text.split("\n"):
        parts = wrap_line(para)
        for p in parts:
            text_obj.textLine(p)
        text_obj.textLine("")

    c.drawText(text_obj)
    c.showPage()
    c.save()

    buffer.seek(0)
    return buffer.read()








