import fitz
import sys

doc = fitz.open(sys.argv[1])

for i, page in enumerate(doc):
    text = page.get_text()
    if "000561" not in text:
        continue

    print(f"=== Page {i+1} - Raw text around 000561 ===")

    # Get all text with positions
    blocks = page.get_text("dict")
    lines_data = []
    for block in blocks.get("blocks", []):
        if "lines" in block:
            for line in block["lines"]:
                y = line["bbox"][1]
                full_line = ""
                for span in line["spans"]:
                    full_line += span["text"]
                lines_data.append((y, full_line.strip()))

    # Sort by y position
    lines_data.sort(key=lambda x: x[0])

    # Find 000561 and print surrounding context
    for idx, (y, text) in enumerate(lines_data):
        if "000561" in text:
            start = max(0, idx - 5)
            end = min(len(lines_data), idx + 30)
            for j in range(start, end):
                yy, tt = lines_data[j]
                # Show hex for garbled chars
                hex_repr = ""
                for c in tt:
                    if ord(c) > 127 and ord(c) < 0x3000:
                        hex_repr += f"[U+{ord(c):04X}]"
                    else:
                        hex_repr += c
                print(f"  y={yy:.0f}: {tt}  |  {hex_repr}")
            break

    # Also try extracting with "rawdict" to get character codes
    print("\n=== Character-level extraction near 000561 ===")
    blocks = page.get_text("rawdict")
    for block in blocks.get("blocks", []):
        if "lines" not in block:
            continue
        for line in block["lines"]:
            line_text = ""
            for span in line["spans"]:
                line_text += span["text"]
            if "000561" in line_text or ("00056" in str(block)):
                # Found the target area, print chars
                for span in line["spans"]:
                    print(f"\n  Font: {span['font']}, size: {span['size']}")
                    if "chars" in span:
                        for ch in span["chars"]:
                            c = ch["c"]
                            print(f"    char='{c}' U+{ord(c):04X} bbox={ch['bbox']}")
                    else:
                        print(f"    text={repr(span['text'])}")
                # Also get next few lines
                break
    break
