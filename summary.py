#!/usr/bin/env python3
import csv, sys
from collections import defaultdict
rows = list(csv.DictReader(open(sys.argv[1])))
agg = defaultdict(lambda: {"n": 0, "c": 0, "t": 0, "wall": 0.0, "toks": []})
for r in rows:
    a = agg[r["model"]]; a["n"] += 1; a["c"] += int(r["compile"]); a["t"] += int(r["tests"])
    a["wall"] += float(r["wall_s"]); a["toks"].append(float(r["tok_s"]))
print(f"\n{'model':12} {'compile':>8} {'tests':>7} {'avg wall':>9} {'avg tok/s':>10}")
for m, a in agg.items():
    ts = sum(a["toks"]) / len(a["toks"]) if a["toks"] else 0
    print(f"{m:12} {a['c']:>3}/{a['n']:<4} {a['t']:>3}/{a['n']:<3} {a['wall']/a['n']:>8.0f}s {ts:>10.1f}")
