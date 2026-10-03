#!/usr/bin/env bash
# Re-run verse_id_eval.py (as a script) on the 896² predictions in a scratch dir and compare with the committed
# verse_id_results_896.csv; then exercise the importable suggest()/ref_text(). Usage: bash check_refactor.sh
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
PY=~/.venvs/nun/bin/python
TMP=$(mktemp -d)
(cd "$TMP" && "$PY" "$HERE/verse_id_eval.py" "$ROOT/data/eval_quranic_896/quranic_ocr_predictions.csv" > out.txt 2>&1) || { tail -20 "$TMP/out.txt"; exit 1; }
"$PY" - "$TMP/verse_id_results.csv" "$HERE/verse_id_results_896.csv" <<'EOF'
import sys, pandas as pd
a, b = pd.read_csv(sys.argv[1]), pd.read_csv(sys.argv[2])
print("rows", len(a), len(b))
for c in a.columns:
    diff = a[c].astype(str) != b[c].astype(str)
    if diff.any():
        print(f"  {c}: differs on {diff.sum()} rows, e.g. {a[c][diff].head(3).tolist()} vs {b[c][diff].head(3).tolist()}")
print("columns compared:", list(a.columns))
EOF
cd "$HERE" && "$PY" - <<'EOF'
import verse_id_eval as v
print([(l["ref"], l["score"]) for l in v.suggest("وقل رب زدني علما")])
print([(l["ref"], l["score"]) for l in v.suggest("بسم الله الرحمن الرحيم\nكهيعص\nذكر رحمة ربك عبده زكريا")])
print(v.ref_text("20:114")[-25:])
EOF
