import fitz
import sys

doc = fitz.open(sys.argv[1])

# Find page 1 to understand the layout with a known employee
page = doc[0]
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

# Get employee IDs
emp_ids = [(s[0], s[2], s[3]) for s in spans if "001 - 008" in s[3] or "001 - 010" in s[3]]
emp_ids.sort(key=lambda x: x[0])
print("Page 1 Employee IDs:")
for x0, x1, t in emp_ids:
    print(f"  x={x0:.0f}-{x1:.0f}: {t}")

# Get labels (find the x range for labels by looking for known text patterns)
# Get all unique x positions to understand layout
all_x = sorted(set(int(s[0]) for s in spans))
print(f"\nAll x positions (first 20): {all_x[:20]}")

# Get all text at x < 160 (should be label area before first employee)
labels = [(s[1], s[3]) for s in spans if s[0] < 140]
labels.sort(key=lambda x: x[0])
print("\nLabels area (x<140):")
for y, t in labels:
    print(f"  y={y:.0f}: {t}")
