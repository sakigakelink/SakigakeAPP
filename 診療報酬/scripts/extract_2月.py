import os
import fitz  # pymupdf

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
input_dir = os.path.join(BASE_DIR, "2月", "元データ")
output_file = os.path.join(BASE_DIR, "2月_extract.txt")

MAX_CHARS = 10000

pdf_files = sorted([f for f in os.listdir(input_dir) if f.lower().endswith(".pdf")])
print(f"Found {len(pdf_files)} PDF files.")

with open(output_file, "w", encoding="utf-8") as out:
    for fname in pdf_files:
        fpath = os.path.join(input_dir, fname)
        out.write("=" * 80 + "\n")
        out.write(f"FILE: {fname}\n")
        out.write("=" * 80 + "\n")
        try:
            doc = fitz.open(fpath)
            num_pages = len(doc)
            text_parts = []
            for page_num in range(num_pages):
                page = doc[page_num]
                page_text = page.get_text()
                if page_text and page_text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n{page_text}")
            doc.close()
            full_text = "\n".join(text_parts)
            if len(full_text) > MAX_CHARS:
                full_text = full_text[:MAX_CHARS] + "\n... [TRUNCATED at 10000 chars]"
            out.write(full_text + "\n\n")
            print(f"  OK: {fname} ({num_pages} pages, {len(full_text)} chars)")
        except Exception as e:
            out.write(f"[ERROR] Could not extract text: {e}\n\n")
            print(f"  ERROR: {fname} -> {e}")

print(f"\nOutput written to: {output_file}")
