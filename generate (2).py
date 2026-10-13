#!/usr/bin/env python3
"""Fetch public market data from Yahoo Finance and write data/data.json.

Standard library only. No secrets. Public data only (no company or Platts data).
If one symbol fails, its previous series is kept and marked stale.
If every symbol fails, the existing file is left untouched and the script exits with an error.
"""
import json
import os
import sys
import time
import urllib.parse
import urllib.request

OUT = os.path.join("data", "data.json")

# sym, display name, unit, group
SERIES = [
    ("BZ=F", "Brent 原油期貨", "美元/桶", "oil"),
    ("CL=F", "WTI 原油期貨", "美元/桶", "oil"),
    ("TWD=X", "美元兌台幣", "TWD", "fx"),
    ("CNY=X", "美元兌人民幣", "CNY", "fx"),
    ("MYR=X", "美元兌馬幣", "MYR", "fx"),
    ("IDR=X", "美元兌印尼盾", "IDR", "fx"),
    ("INR=X", "美元兌盧比", "INR", "fx"),
    ("DX-Y.NYB", "美元指數", "指數", "macro"),
    ("NG=F", "天然氣期貨", "美元/百萬英熱", "macro"),
    ("^TNX", "美國10年期公債殖利率", "%", "macro"),
]


def fmt_day(ts, off):
    return time.strftime("%Y-%m-%d", time.gmtime(ts + off))


def fetch(sym):
    url = ("https://query1.finance.yahoo.com/v8/finance/chart/"
           + urllib.parse.quote(sym) + "?range=1y&interval=1d")
    last = None
    for attempt in range(3):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=30) as r:
                return json.loads(r.read().decode("utf-8"))
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(3 * (attempt + 1))
    raise last


def parse(d):
    res = d["chart"]["result"][0]
    meta = res["meta"]
    off = meta.get("gmtoffset", 0) or 0
    closes = res["indicators"]["quote"][0]["close"]
    by_day = {}
    for t, c in zip(res["timestamp"], closes):
        if c is None:
            continue
        by_day[fmt_day(t, off)] = round(c, 4)  # exchange-local date; a later bar of the same date wins
    pts = [[d, v] for d, v in sorted(by_day.items())]
    rt = meta.get("regularMarketTime")
    reg = time.strftime("%Y-%m-%d %H:%M", time.gmtime(rt)) if rt else ""
    return pts, reg


def main():
    old = {}
    if os.path.exists(OUT):
        try:
            with open(OUT, encoding="utf-8") as f:
                old = {s["sym"]: s for s in json.load(f)["series"]}
        except Exception:  # noqa: BLE001
            old = {}
    series, errors = [], []
    for sym, name, unit, grp in SERIES:
        item = {"sym": sym, "name": name, "unit": unit, "grp": grp}
        try:
            pts, reg = parse(fetch(sym))
            if len(pts) < 30:
                raise ValueError("too few points: %d" % len(pts))
            item.update({"regTime": reg, "pts": pts})
            print(sym, "OK", len(pts), pts[-1])
        except Exception as e:  # noqa: BLE001
            msg = type(e).__name__ + " " + str(e)[:100]
            errors.append({"sym": sym, "error": msg})
            print(sym, "FAILED", msg)
            if sym in old:
                item.update({"regTime": old[sym].get("regTime", ""), "pts": old[sym]["pts"], "stale": True})
            else:
                continue
        series.append(item)
    if len(errors) == len(SERIES) or not series:
        print("All symbols failed; existing file is left untouched.")
        sys.exit(1)
    out = {
        "fetched": time.strftime("%Y-%m-%d %H:%M", time.gmtime()),
        "source": "Yahoo Finance (unofficial interface)",
        "errors": errors,
        "series": series,
    }
    os.makedirs("data", exist_ok=True)
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, separators=(",", ":"))
    print("written", OUT, "series", len(series), "errors", len(errors))
    if errors:
        sys.exit(2 if len(errors) > 2 else 0)


if __name__ == "__main__":
    main()
