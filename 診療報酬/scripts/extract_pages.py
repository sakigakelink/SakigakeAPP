import PyPDF2
import sys

pdf_path = r"C:\Users\Mining-Base\SakigakeAPP\診療報酬\001666622.pdf"
out_path = r"C:\Users\Mining-Base\SakigakeAPP\診療報酬\pdf_extract_p20_137.txt"

# Pages 20-137 (1-indexed) => indices 19-136 (0-indexed)
start_page = 20
end_page = 137

try:
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        total_pages = len(reader.pages)
        print(f"Total pages in PDF: {total_pages}")

        if end_page > total_pages:
            print(f"Warning: PDF has only {total_pages} pages. Adjusting end_page to {total_pages}.")
            end_page = total_pages

        with open(out_path, "w", encoding="utf-8") as out:
            for page_num in range(start_page, end_page + 1):
                page_idx = page_num - 1
                page = reader.pages[page_idx]
                text = page.extract_text() or ""
                # Limit to first 5000 chars per page
                text = text[:5000]

                out.write(f"{'='*60}\n")
                out.write(f"Page {page_num}\n")
                out.write(f"{'='*60}\n")
                out.write(text)
                out.write("\n\n")

                if page_num % 20 == 0:
                    print(f"  Processed page {page_num}...")

        print(f"Done. Extracted pages {start_page}-{end_page} to: {out_path}")

except Exception as e:
    print(f"Error: {e}", file=sys.stderr)
    sys.exit(1)
