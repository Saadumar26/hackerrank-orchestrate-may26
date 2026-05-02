#!/usr/bin/env python
import csv

# Show statistics
with open('../support_tickets/output.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

replied = sum(1 for r in rows if r['status'] == 'replied')
escalated = sum(1 for r in rows if r['status'] == 'escalated')

print(f"\n{'='*70}")
print(f"AGENT OUTPUT SUMMARY")
print(f"{'='*70}")
print(f"Total tickets processed: {len(rows)}")
print(f"✓ Replied:    {replied:2d} ({100*replied//len(rows):2d}%)")
print(f"⚠ Escalated: {escalated:2d} ({100*escalated//len(rows):2d}%)")
print()

# Show first replied example
print(f"{'='*70}")
print("EXAMPLE 1: REPLIED TICKET")
print(f"{'='*70}")
for r in rows:
    if r['status'] == 'replied':
        print(f"Status:       {r['status']}")
        print(f"Product Area: {r['product_area']}")
        print(f"Request Type: {r['request_type']}")
        print(f"\nResponse:")
        print(f"  {r['response'][:250]}...")
        print(f"\nJustification:")
        print(f"  {r['justification'][:150]}...")
        break
print()

# Show first escalated example
print(f"{'='*70}")
print("EXAMPLE 2: ESCALATED TICKET")
print(f"{'='*70}")
for r in rows:
    if r['status'] == 'escalated':
        print(f"Status:       {r['status']}")
        print(f"Product Area: {r['product_area']}")
        print(f"Request Type: {r['request_type']}")
        print(f"\nResponse:")
        print(f"  {r['response'][:250]}...")
        print(f"\nJustification:")
        print(f"  {r['justification'][:150]}...")
        break

print(f"\n{'='*70}")
print("Full output saved to: support_tickets/output.csv")
print(f"{'='*70}\n")
