#!/usr/bin/env python
import csv
with open('../support_tickets/support_tickets.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    print(f"Column names: {reader.fieldnames}")
    for i, row in enumerate(reader):
        if i < 3:
            print(f"\nRow {i+1}:")
            for key, val in row.items():
                preview = val.strip()[:100] if val else ""
                print(f"  {key}: (len={len(val if val else '')}) {preview}")

