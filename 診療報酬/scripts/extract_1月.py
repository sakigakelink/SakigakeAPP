import os
import PyPDF2

input_dir = r"C:/Users/Mining-Base/SakigakeAPP/診療報酬/1月/元データ"
output_file = r"C:/Users/Mining-Base/SakigakeAPP/診療報酬/1月_extract.txt"

pdf_files = sorted([f for f in os.listdir(input_dir) if f.lower().endswith('.pdf')])

print(f"Found {len(pdf_files)} PDF files")

with open(output_file, 'w', encoding='utf-8') as out:
    for filename in pdf_files:
        filepath = os.path.join(input_dir, filename)
        print(f"Processing: {filename}")
        out.write("=" * 80 + "\n")
        out.write(f"FILE: {filename}\n")
        out.write("=" * 80 + "\n\n")

        try:
            with open(filepath, 'rb') as f:
                reader = PyPDF2.PdfReader(f)
                num_pages = len(reader.pages)
                out.write(f"[Pages: {num_pages}]\n\n")

                full_text = ""
                for page_num, page in enumerate(reader.pages):
                    text = page.extract_text()
                    if text:
                        full_text += f"--- Page {page_num + 1} ---\n"
                        full_text += text + "\n\n"

                # Limit to first 10000 chars per file
                if len(full_text) > 10000:
                    out.write(full_text[:10000])
                    out.write(f"\n\n[... TRUNCATED at 10000 chars, total was {len(full_text)} chars ...]\n")
                else:
                    out.write(full_text)

                out.write("\n\n")
                print(f"  -> {num_pages} pages, {len(full_text)} chars extracted")

        except Exception as e:
            out.write(f"[ERROR reading file: {e}]\n\n")
            print(f"  -> ERROR: {e}")

print(f"\nDone. Output written to: {output_file}")
