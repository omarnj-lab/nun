#!/usr/bin/env bash
# Time real /api/chat calls on the running server (router + answer + answer check).
cd "$(dirname "$0")/../.."
for q in "What does this verse mean?" "Did Islam spread by the sword?" "ما معنى هذه الآية؟" "Que signifie ce verset ?"; do
  curl -s -o /tmp/nun_chat.json -w "%{time_total}s  " -H "Content-Type: application/json" \
    -d "{\"sura\":20,\"aya_from\":114,\"aya_to\":114,\"message\":\"$q\"}" http://127.0.0.1:8000/api/chat
  python3 -c "import json;d=json.load(open('/tmp/nun_chat.json'));print(d.get('model'),d.get('language'),d.get('guard_events'),d['answer'][:90])"
done
