from io import BytesIO
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

def create_pdf(content: str, font_path: str = "./fonts/NotoSansKR-Regular.ttf") -> bytes:
    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, leftMargin=36, rightMargin=36, topMargin=36, bottomMargin=36)

    # ✅ TTF 등록
    pdfmetrics.registerFont(TTFont("KFONT", font_path))

    styles = getSampleStyleSheet()
    style = styles["Normal"]
    style.fontName = "KFONT"
    style.fontSize = 11
    style.wordWrap = "CJK"

    flow = []
    for line in content.splitlines():
        flow.append(Spacer(1, 8) if not line.strip() else Paragraph(line, style))

    doc.build(flow)
    buffer.seek(0)
    return buffer.getvalue()
