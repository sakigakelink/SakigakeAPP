import fitz
import sys

doc = fitz.open(sys.argv[1])
target = sys.argv[2] if len(sys.argv) > 2 else None

for i, page in enumerate(doc):
    text = page.get_text()
    if target and target not in text:
        continue
    print(f"=== Page {i+1} ===")
    print(text)
    if target:
        break
