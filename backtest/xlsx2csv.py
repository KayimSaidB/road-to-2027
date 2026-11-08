"""Minimal .xlsx -> .csv (first sheet), standard library only.
Usage: python3 backtest/xlsx2csv.py in.xlsx out.csv [skip_rows] [sheet_number]
"""
import csv, re, sys, zipfile
import xml.etree.ElementTree as ET

NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}

def col_index(ref):
    letters = re.match(r"[A-Z]+", ref).group(0)
    n = 0
    for ch in letters:
        n = n * 26 + ord(ch) - 64
    return n - 1

def convert(src, dst, skip=0, sheet_no=None):
    z = zipfile.ZipFile(src)
    shared = []
    if "xl/sharedStrings.xml" in z.namelist():
        for si in ET.fromstring(z.read("xl/sharedStrings.xml")).findall("m:si", NS):
            shared.append("".join(t.text or "" for t in si.iter("{%s}t" % NS["m"])))
    sheet = f"xl/worksheets/sheet{sheet_no}.xml" if sheet_no else sorted(n for n in z.namelist() if n.startswith("xl/worksheets/sheet"))[0]
    with open(dst, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f, delimiter=";")
        for i, row in enumerate(ET.fromstring(z.read(sheet)).iter("{%s}row" % NS["m"])):
            vals = {}
            for c in row.findall("m:c", NS):
                v = c.find("m:v", NS)
                if v is None:
                    is_ = c.find("m:is", NS)
                    txt = "".join(t.text or "" for t in is_.iter("{%s}t" % NS["m"])) if is_ is not None else ""
                else:
                    txt = shared[int(v.text)] if c.get("t") == "s" else v.text
                vals[col_index(c.get("r"))] = txt
            if i < skip:
                continue
            w.writerow([vals.get(k, "") for k in range(max(vals) + 1)] if vals else [])

if __name__ == "__main__":
    convert(sys.argv[1], sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 0, sys.argv[4] if len(sys.argv) > 4 else None)
