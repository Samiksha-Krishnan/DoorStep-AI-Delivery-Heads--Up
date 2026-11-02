"""Measure the message parser against hand-labelled messages (use this table in your report).
Run:  python evaluate_parser.py
To compare a new NLP model, swap parse_message() and run again."""
import json, os
from datetime import datetime
from parser import parse_message

path = os.path.join(os.path.dirname(__file__), "data", "labeled_messages.json")
data = json.load(open(path, encoding="utf-8"))
today = datetime(2026, 11, 2)
fields = {}
for row in data:
    got = parse_message(row["text"], today=today)
    for k, v in row["expected"].items():
        ok = (got.get("date", "")[5:] == v) if k == "date_month_day" else (str(got.get(k, "")).lower() == str(v).lower())
        fields.setdefault(k, []).append(ok)
        if not ok: print(f"MISS  {k}: expected {v!r}, got {got.get(k)!r}  <- {row['text'][:55]}...")
print("\nField accuracy")
tot = ok_all = 0
for k, r in sorted(fields.items()):
    print(f"  {k:16s} {sum(r)}/{len(r)}  ({100*sum(r)/len(r):.0f}%)")
    tot += len(r); ok_all += sum(r)
print(f"\nOverall: {ok_all}/{tot} ({100*ok_all/tot:.0f}%)")
