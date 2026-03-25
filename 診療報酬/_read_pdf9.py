import fitz
import sys

doc = fitz.open(sys.argv[1])

# Find page with 000358 (足立正史 10010358 -> 001-010-000358)
for i, page in enumerate(doc):
    text = page.get_text()
    if "000358" in text:
        print(f"足立 found on page {i+1}")

        blocks = page.get_text("dict")
        spans = []
        for block in blocks.get("blocks", []):
            if "lines" in block:
                for line in block["lines"]:
                    for span in line["spans"]:
                        t = span["text"].strip()
                        if t:
                            x0 = span["bbox"][0]
                            y0 = span["bbox"][1]
                            x1 = span["bbox"][2]
                            spans.append((x0, y0, x1, t))

        # Find 000358 column
        target = None
        for s in spans:
            if "000358" in s[3]:
                target = s
                break
        if not target:
            continue

        col_center = (target[0] + target[2]) / 2
        col_width = target[2] - target[0]
        margin = col_width * 0.8

        col_spans = [(s[1], s[3]) for s in spans
                     if abs((s[0] + s[2])/2 - col_center) < margin]
        col_spans.sort(key=lambda x: x[0])

        print(f"\n000358 column values:")
        for y, t in col_spans:
            print(f"  y={y:.0f}: {t}")
        break
