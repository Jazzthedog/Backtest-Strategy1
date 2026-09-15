"""Inline results.json into each report template -> self-contained HTML files."""
import io, os

REPORTS = [
    ("report_template.html",  "01_backtest.html"),
    ("report2_template.html", "02_benchmark.html"),
]

with io.open("results.json", encoding="utf-8") as f:
    data = f.read()

for template, out_name in REPORTS:
    if not os.path.exists(template):
        continue
    with io.open(template, encoding="utf-8") as f:
        html = f.read()
    assert "/*__DATA__*/" in html, "placeholder missing from " + template
    with io.open(out_name, "w", encoding="utf-8") as f:
        f.write(html.replace("/*__DATA__*/", data))
    print("{} written: {:,} bytes".format(out_name, os.path.getsize(out_name)))

print("data payload: {:,} bytes".format(len(data)))
