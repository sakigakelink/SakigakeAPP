import fitz
import sys

doc = fitz.open(sys.argv[1])

# Find page with employee number 000561 (岡﨑　貞夫)
for i, page in enumerate(doc):
    text = page.get_text()
    if "000561" not in text:
        continue

    print(f"=== Page {i+1} ===")
    blocks = page.get_text("dict")
    for block in blocks.get("blocks", []):
        if "lines" in block:
            for line in block["lines"]:
                for span in line["spans"]:
                    t = span["text"].strip()
                    if t:
                        font = span.get("font", "?")
                        print(f"  [{font}] {repr(t)}")
    break
