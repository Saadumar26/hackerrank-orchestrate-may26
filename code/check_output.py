#!/usr/bin/env python
import csv
with open('../support_tickets/output.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    count = 0
    for row in reader:
        if row['status'] == 'replied' and count < 3:
            print(f"Replied #{count+1}:")
            print(f"  Product Area: {row['product_area']}")
            print(f"  Request Type: {row['request_type']}")
            print(f"  Response: {row['response'][:150]}...")
            print(f"  Justification: {row['justification'][:100]}...")
            print()
            count += 1
