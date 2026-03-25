import fitz
import sys

doc = fitz.open(sys.argv[1])

for i, page in enumerate(doc):
    text = page.get_text()
    if "000561" not in text:
        continue

    print(f"=== Page {i+1} ===")
    # Get text blocks with positions
    blocks = page.get_text("dict")

    # Collect all spans with their positions
    spans = []
    for block in blocks.get("blocks", []):
        if "lines" in block:
            for line in block["lines"]:
                for span in line["spans"]:
                    x0 = span["bbox"][0]
                    y0 = span["bbox"][1]
                    x1 = span["bbox"][2]
                    y1 = span["bbox"][3]
                    t = span["text"].strip()
                    if t:
                        spans.append((x0, y0, x1, y1, t))

    # Find the x-range for 000561 column
    target_span = None
    for s in spans:
        if "000561" in s[4]:
            target_span = s
            break

    if not target_span:
        continue

    # 000561 column center
    col_center = (target_span[0] + target_span[2]) / 2
    col_width = target_span[2] - target_span[0]

    print(f"000561 column: x={target_span[0]:.0f}-{target_span[2]:.0f}, center={col_center:.0f}")

    # Get all spans in this column (within reasonable x range)
    margin = col_width * 0.8
    col_spans = []
    for s in spans:
        span_center = (s[0] + s[2]) / 2
        if abs(span_center - col_center) < margin:
            col_spans.append(s)

    # Sort by y position
    col_spans.sort(key=lambda s: s[1])

    print(f"\nAll values in 000561 column ({len(col_spans)} items):")
    for s in col_spans:
        print(f"  y={s[1]:.0f}: {s[4]}")

    break
