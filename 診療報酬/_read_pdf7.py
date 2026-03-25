import fitz
import sys

doc = fitz.open(sys.argv[1])

# Find page with 000561 and also extract another known employee for comparison
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

    # Find all employee ID spans on this page
    emp_ids = [(s[0], s[2], s[3]) for s in spans if "001 - 008" in s[3]]
    emp_ids.sort(key=lambda x: x[0])

    print("Employee IDs on page (sorted by x):")
    for x0, x1, t in emp_ids:
        print(f"  x={x0:.0f}-{x1:.0f}: {t}")

    # Get left-side labels
    labels = [(s[1], s[3]) for s in spans if s[0] < 50]
    labels.sort(key=lambda x: x[0])
    print("\nLabels (x<50):")
    for y, t in labels:
        print(f"  y={y:.0f}: {t}")

    break
