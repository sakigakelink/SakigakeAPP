import fitz
import sys
import json

doc = fitz.open(sys.argv[1])
target = sys.argv[2] if len(sys.argv) > 2 else None

for i, page in enumerate(doc):
    # Try extracting as dict for better structure
    blocks = page.get_text("dict")
    full_text = ""
    for block in blocks.get("blocks", []):
        if "lines" in block:
            for line in block["lines"]:
                line_text = ""
                for span in line["spans"]:
                    line_text += span["text"]
                full_text += line_text + "\n"

    if target and target not in full_text:
        continue

    print(f"=== Page {i+1} ===")
    print(full_text)
    if target:
        break
