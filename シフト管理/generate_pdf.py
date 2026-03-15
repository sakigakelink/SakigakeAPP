"""SHIFT_RULES.md → PDF 変換スクリプト"""
import re
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Table, TableStyle, Spacer, PageBreak
)
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# --- フォント登録 ---
FONT = "BIZUDGothic"
pdfmetrics.registerFont(TTFont(FONT, r"C:\Windows\Fonts\BIZ-UDGothicR.ttc", subfontIndex=0))

# --- スタイル定義 ---
STYLES = {
    "title": ParagraphStyle("title", fontName=FONT, fontSize=18, leading=24, spaceAfter=10, alignment=1),
    "h2": ParagraphStyle("h2", fontName=FONT, fontSize=14, leading=20, spaceBefore=16, spaceAfter=6,
                          textColor=colors.HexColor("#1a3c6e"), borderPadding=(0, 0, 2, 0)),
    "h3": ParagraphStyle("h3", fontName=FONT, fontSize=11, leading=16, spaceBefore=10, spaceAfter=4,
                          textColor=colors.HexColor("#2a5ea8")),
    "h4": ParagraphStyle("h4", fontName=FONT, fontSize=10, leading=14, spaceBefore=8, spaceAfter=3,
                          textColor=colors.HexColor("#444444")),
    "body": ParagraphStyle("body", fontName=FONT, fontSize=9, leading=13, spaceAfter=3),
    "quote": ParagraphStyle("quote", fontName=FONT, fontSize=8.5, leading=12, spaceAfter=4,
                             leftIndent=12, textColor=colors.HexColor("#555555")),
    "code": ParagraphStyle("code", fontName=FONT, fontSize=8.5, leading=12, spaceAfter=4,
                            leftIndent=8, backColor=colors.HexColor("#f5f5f5")),
    "toc": ParagraphStyle("toc", fontName=FONT, fontSize=9, leading=14, leftIndent=10),
}

TABLE_STYLE = TableStyle([
    ("FONTNAME", (0, 0), (-1, -1), FONT),
    ("FONTSIZE", (0, 0), (-1, -1), 8),
    ("LEADING", (0, 0), (-1, -1), 11),
    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e8eef6")),
    ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#1a3c6e")),
    ("FONTSIZE", (0, 0), (-1, 0), 8.5),
    ("ALIGN", (0, 0), (-1, -1), "LEFT"),
    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
    ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8f9fc")]),
    ("TOPPADDING", (0, 0), (-1, -1), 3),
    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ("LEFTPADDING", (0, 0), (-1, -1), 5),
    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
])


def escape(text):
    """XML エスケープ + 簡易マークダウン変換"""
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # bold
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    # inline code
    text = re.sub(r"`([^`]+)`", r'<font color="#c7254e" size="8">\1</font>', text)
    return text


def parse_md(filepath):
    """Markdown を解析して reportlab の Story (flowable リスト) に変換"""
    with open(filepath, "r", encoding="utf-8") as f:
        lines = f.readlines()

    story = []
    i = 0
    in_code = False
    code_buf = []
    in_table = False
    table_rows = []

    def flush_table():
        nonlocal in_table, table_rows
        if table_rows:
            # ヘッダ行の幅を推定
            ncols = len(table_rows[0])
            avail = 170 * mm
            col_w = avail / ncols
            t = Table(table_rows, colWidths=[col_w] * ncols)
            t.setStyle(TABLE_STYLE)
            story.append(t)
            story.append(Spacer(1, 4))
        in_table = False
        table_rows = []

    while i < len(lines):
        line = lines[i].rstrip("\n")

        # コードブロック
        if line.startswith("```"):
            if in_code:
                story.append(Paragraph(escape("\n".join(code_buf)), STYLES["code"]))
                code_buf = []
                in_code = False
            else:
                flush_table()
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line)
            i += 1
            continue

        # テーブル
        if "|" in line and line.strip().startswith("|"):
            stripped = line.strip()
            # 区切り行（|---|---|）はスキップ
            if re.match(r"^\|[\s\-:|]+\|$", stripped):
                i += 1
                continue
            cells = [c.strip() for c in stripped.split("|")[1:-1]]
            cells = [Paragraph(escape(c), STYLES["body"]) for c in cells]
            if not in_table:
                in_table = True
            table_rows.append(cells)
            i += 1
            continue
        else:
            flush_table()

        # 空行
        if not line.strip():
            i += 1
            continue

        # 見出し
        if line.startswith("# "):
            story.append(Paragraph(escape(line[2:].strip()), STYLES["title"]))
            story.append(Spacer(1, 6))
            i += 1
            continue
        if line.startswith("## "):
            story.append(Spacer(1, 4))
            story.append(Paragraph(escape(line[3:].strip()), STYLES["h2"]))
            i += 1
            continue
        if line.startswith("### "):
            story.append(Paragraph(escape(line[4:].strip()), STYLES["h3"]))
            i += 1
            continue
        if line.startswith("#### "):
            story.append(Paragraph(escape(line[5:].strip()), STYLES["h4"]))
            i += 1
            continue

        # 水平線
        if line.strip() == "---":
            story.append(Spacer(1, 6))
            i += 1
            continue

        # 引用
        if line.startswith("> "):
            story.append(Paragraph(escape(line[2:].strip()), STYLES["quote"]))
            i += 1
            continue

        # リスト
        if re.match(r"^(\d+\.\s+|- |\* )", line.strip()):
            indent = len(line) - len(line.lstrip())
            bullet_style = ParagraphStyle(
                "bullet", parent=STYLES["body"], leftIndent=8 + indent * 4, bulletIndent=indent * 4
            )
            text = re.sub(r"^(\d+\.\s+|- |\* )", "", line.strip())
            story.append(Paragraph(f"• {escape(text)}", bullet_style))
            i += 1
            continue

        # 通常テキスト
        story.append(Paragraph(escape(line.strip()), STYLES["body"]))
        i += 1

    flush_table()
    return story


def build_pdf(md_path, pdf_path):
    doc = SimpleDocTemplate(
        pdf_path, pagesize=A4,
        topMargin=18 * mm, bottomMargin=18 * mm,
        leftMargin=15 * mm, rightMargin=15 * mm,
        title="シフト作成原則・プロトコル",
        author="Sakigake Shift System",
    )
    story = parse_md(md_path)
    doc.build(story)
    print(f"PDF generated: {pdf_path}")


if __name__ == "__main__":
    import os
    base = os.path.dirname(os.path.abspath(__file__))
    md = os.path.join(base, "SHIFT_RULES.md")
    pdf = os.path.join(base, "SHIFT_RULES.pdf")
    build_pdf(md, pdf)
