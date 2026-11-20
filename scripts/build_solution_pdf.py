"""Render docs/solution.md to a compact two-page PDF."""

from __future__ import annotations

import re
import sys
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_LEFT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    BaseDocTemplate,
    Frame,
    ListFlowable,
    ListItem,
    PageTemplate,
    Paragraph,
    Preformatted,
    Spacer,
    Table,
    TableStyle,
)


ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "docs" / "solution.md"
OUTPUT = ROOT / "docs" / "solution.pdf"


def inline(text: str) -> str:
    text = (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
    )
    text = re.sub(r"\*\*(.+?)\*\*", r"<b>\1</b>", text)
    text = re.sub(
        r"`(.+?)`",
        r'<font name="Courier" size="8.5">\1</font>',
        text,
    )
    return text


def build_styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "Title2", parent=base["Title"], fontSize=19, leading=22,
            spaceAfter=2, textColor=colors.HexColor("#0f172a"),
        ),
        "subtitle": ParagraphStyle(
            "Subtitle", parent=base["Normal"], fontSize=9.5, leading=13,
            textColor=colors.HexColor("#475569"), spaceAfter=6,
        ),
        "h2": ParagraphStyle(
            "H2", parent=base["Heading2"], fontSize=11.5, leading=13.5,
            spaceBefore=7, spaceAfter=2, textColor=colors.HexColor("#0f172a"),
        ),
        "body": ParagraphStyle(
            "Body", parent=base["BodyText"], fontSize=9.1, leading=11.8,
            alignment=TA_LEFT, spaceAfter=3.5,
        ),
        "bullet": ParagraphStyle(
            "Bullet", parent=base["BodyText"], fontSize=9.0, leading=11.4,
            leftIndent=10, bulletIndent=2, spaceAfter=0.5,
        ),
        "quote": ParagraphStyle(
            "Quote", parent=base["BodyText"], fontSize=9.4, leading=12.4,
            leftIndent=12, textColor=colors.HexColor("#334155"),
            borderPadding=4, spaceBefore=3, spaceAfter=5,
        ),
        "code": ParagraphStyle(
            "Code", parent=base["Code"], fontSize=7.9, leading=9.8,
            backColor=colors.HexColor("#f1f5f9"), borderPadding=4,
        ),
        "cell": ParagraphStyle(
            "Cell", parent=base["BodyText"], fontSize=8.1, leading=10.0,
        ),
        "cellhead": ParagraphStyle(
            "CellHead", parent=base["BodyText"], fontSize=8.1, leading=10.0,
            textColor=colors.white,
        ),
    }


def add_footer(canvas, doc):
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(colors.HexColor("#64748b"))
    canvas.drawString(
        1.6 * cm, 1.0 * cm,
        "Kuku AI Generalist · Problem 1 · Ayan Dhal",
    )
    canvas.drawRightString(
        A4[0] - 1.6 * cm, 1.0 * cm, f"Page {doc.page} of 2",
    )
    canvas.restoreState()


def parse_markdown(text: str, styles):
    lines = text.splitlines()
    story = []
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()

        if not line.strip():
            i += 1
            continue

        if line.startswith("# "):
            story.append(Paragraph(inline(line[2:]), styles["title"]))
            i += 1
            continue

        if line.startswith("## "):
            story.append(Paragraph(inline(line[3:]), styles["h2"]))
            i += 1
            continue

        if line.startswith("```"):
            block = []
            i += 1
            while i < len(lines) and not lines[i].startswith("```"):
                block.append(lines[i])
                i += 1
            i += 1
            story.append(Preformatted("\n".join(block), styles["code"]))
            continue

        if line.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                raw = [cell.strip() for cell in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", cell) for cell in raw):
                    rows.append(raw)
                i += 1

            if rows:
                data = []
                for row_index, row in enumerate(rows):
                    style = styles["cellhead"] if row_index == 0 else styles["cell"]
                    data.append([Paragraph(inline(cell), style) for cell in row])

                width = A4[0] - 3.4 * cm
                table = Table(
                    data,
                    colWidths=[width * 0.55, width * 0.45],
                    repeatRows=1,
                )
                table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0f172a")),
                    ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                    ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#cbd5e1")),
                    ("VALIGN", (0, 0), (-1, -1), "TOP"),
                    ("LEFTPADDING", (0, 0), (-1, -1), 5),
                    ("RIGHTPADDING", (0, 0), (-1, -1), 5),
                    ("TOPPADDING", (0, 0), (-1, -1), 2.4),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2.4),
                ]))
                story.append(table)
                story.append(Spacer(1, 4))
            continue

        if line.startswith("> "):
            block = [line[2:].strip()]
            i += 1
            while i < len(lines) and lines[i].startswith("> "):
                block.append(lines[i][2:].strip())
                i += 1
            story.append(Paragraph(inline(" ".join(block)), styles["quote"]))
            continue

        if re.match(r"^\d+\.\s", line):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s", lines[i]):
                items.append(Paragraph(
                    inline(re.sub(r"^\d+\.\s", "", lines[i])),
                    styles["bullet"],
                ))
                i += 1
            story.append(ListFlowable(
                [ListItem(item, leftIndent=12) for item in items],
                bulletType="1", start=1, leftIndent=12,
            ))
            continue

        if line.startswith("- "):
            items = []
            while i < len(lines) and lines[i].startswith("- "):
                items.append(Paragraph(
                    inline(lines[i][2:]), styles["bullet"],
                ))
                i += 1
            story.append(ListFlowable(
                [ListItem(item, leftIndent=10) for item in items],
                bulletType="bullet", start="•", leftIndent=10,
            ))
            continue

        # Paragraph: join wrapped lines until blank / block marker.
        block = [line]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
            r"^(#|\||>|```|- |\d+\. )", lines[i]
        ):
            block.append(lines[i].strip())
            i += 1
        story.append(Paragraph(inline(" ".join(block)), styles["body"]))

    return story


def build():
    text = SOURCE.read_text(encoding="utf-8")
    styles = build_styles()
    story = parse_markdown(text, styles)

    doc = BaseDocTemplate(
        str(OUTPUT),
        pagesize=A4,
        leftMargin=1.7 * cm,
        rightMargin=1.7 * cm,
        topMargin=1.35 * cm,
        bottomMargin=1.35 * cm,
        title="Kuku AI Generalist — Problem 1",
        author="Ayan Dhal",
    )
    frame = Frame(
        doc.leftMargin, doc.bottomMargin,
        doc.width, doc.height, id="normal",
    )
    doc.addPageTemplates([
        PageTemplate(id="main", frames=[frame], onPage=add_footer)
    ])
    doc.build(story)
    print("Wrote", OUTPUT)


if __name__ == "__main__":
    build()
