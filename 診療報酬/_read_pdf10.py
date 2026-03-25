import fitz
import sys

doc = fitz.open(sys.argv[1])

# Compare full structure: get ALL y positions and values for both employees
# 足立 (000358) on page 1, 岡﨑 (000561) on page 12

results = {}

for target_id, target_page_hint in [("000358", None), ("000561", None)]:
    for i, page in enumerate(doc):
        text = page.get_text()
        if target_id not in text:
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

        target_span = None
        for s in spans:
            if target_id in s[3]:
                target_span = s
                break
        if not target_span:
            continue

        col_center = (target_span[0] + target_span[2]) / 2
        col_width = target_span[2] - target_span[0]
        margin = col_width * 0.6  # tighter margin

        col_vals = {}
        for s in spans:
            span_center = (s[0] + s[2]) / 2
            if abs(span_center - col_center) < margin:
                y = round(s[1])
                # Only keep numeric values and first occurrence
                t = s[3].replace(",", "")
                try:
                    val = int(t)
                    if y not in col_vals:
                        col_vals[y] = val
                except ValueError:
                    try:
                        val = float(t.replace("%", ""))
                        # skip percentages
                    except:
                        if y not in col_vals:
                            col_vals[y] = s[3]

        results[target_id] = col_vals
        break

# Print side by side
all_ys = sorted(set(list(results.get("000358", {}).keys()) + list(results.get("000561", {}).keys())))

print(f"{'y':>5} | {'足立(000358)':>15} | {'岡﨑(000561)':>15}")
print("-" * 45)
for y in all_ys:
    v1 = results.get("000358", {}).get(y, "")
    v2 = results.get("000561", {}).get(y, "")
    if isinstance(v1, int):
        v1 = f"{v1:,}"
    if isinstance(v2, int):
        v2 = f"{v2:,}"
    print(f"{y:>5} | {str(v1):>15} | {str(v2):>15}")
