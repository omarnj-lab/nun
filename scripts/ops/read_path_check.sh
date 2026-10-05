#!/usr/bin/env bash
# Scan photos that are NOT in the collection through the live API: exercises the reading path.
cd "$(dirname "$0")/../.."
for f in "$@"; do
  curl -s -o /tmp/nun_scan.json -w "%{time_total}s " -F "image=@$f" -F lang=ar http://127.0.0.1:8000/api/scan
  python3 -c "
import json; d=json.load(open('/tmp/nun_scan.json'))
r=d.get('reading') or {}; s=d.get('seen') or {}
print('$(basename $f)', d['status'], d.get('reason',''), d.get('card',{}).get('ref',{}).get('label',''), r.get('score',''), r.get('styles') or s.get('styles'), r.get('theme') or s.get('theme'), d.get('timings_ms'))"
done
