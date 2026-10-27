#!/usr/bin/env python3
"""Сводка по одному или нескольким results_*.csv.
С несколькими файлами считает N прогонов на модель: pass как k/N*6,
wall как медиана и min..max — разброс важнее среднего."""
import csv, statistics, sys
from collections import defaultdict

rows = [r for f in sys.argv[1:] for r in csv.DictReader(open(f))]
by = defaultdict(list)
for r in rows:
    by[r["model"]].append(r)

print("| Model | Compiles | Tests pass | Wall median | Wall min..max | Wall-to-pass | tok/s | Flaky tasks |")
print("|---|---|---|---|---|---|---|---|")
for m, rs in sorted(by.items(), key=lambda kv: -sum(int(r["tests"]) for r in kv[1]) / len(kv[1])):
    n = len(rs)
    c = sum(int(r["compile"]) for r in rs); t = sum(int(r["tests"]) for r in rs)
    walls = [float(r["wall_s"]) for r in rs]
    passed = [float(r["wall_s"]) for r in rs if r["tests"] == "1"]
    toks = statistics.mean(float(r["tok_s"]) for r in rs)
    # задача «плавает», если в разных прогонах и проходила, и нет
    per = defaultdict(list)
    for r in rs: per[r["prompt"]].append(r["tests"] == "1")
    flaky = ", ".join(f"{p} {sum(v)}/{len(v)}" for p, v in sorted(per.items()) if 0 < sum(v) < len(v))
    print(f"| {m} | {c}/{n} | {t}/{n} | {statistics.median(walls):.0f} s "
          f"| {min(walls):.0f}..{max(walls):.0f} s | "
          f"{statistics.mean(passed) if passed else float('nan'):.0f} s | {toks:.0f} | {flaky or 'none'} |")
