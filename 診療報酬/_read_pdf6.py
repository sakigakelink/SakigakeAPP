import fitz
import sys

doc = fitz.open(sys.argv[1])

# Also get the row labels from the leftmost column for context
for i, page in enumerate(doc):
    text = page.get_text()
    if "000561" not in text:
        continue

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

    # Get leftmost column labels (x < 100)
    labels = [(s[1], s[3]) for s in spans if s[0] < 100]
    labels.sort(key=lambda x: x[0])

    print("=== Row labels (left column) ===")
    for y, t in labels:
        print(f"  y={y:.0f}: {t}")

    break
