#!/usr/bin/env bash
# Install the Ollama Linux binary in WSL (user-local, no sudo) and serve the models already downloaded by the
# Windows Ollama app (same on-disk format), on 127.0.0.1:11435 so it never clashes with the Windows instance.
#   bash scripts/ops/install_ollama_wsl.sh            # install (idempotent)
#   bash scripts/ops/install_ollama_wsl.sh serve      # run the server (foreground)
set -euo pipefail
DEST="$HOME/.local/ollama"
PY="$HOME/.venvs/nun/bin/python"
export OLLAMA_MODELS="/mnt/c/Users/User/.ollama/models"
export OLLAMA_HOST="127.0.0.1:11435"

if [ "${1:-}" = "serve" ]; then
  exec "$DEST/bin/ollama" serve
fi

if [ ! -x "$DEST/bin/ollama" ]; then
  mkdir -p "$DEST"
  cd "$DEST"
  for name in ollama-linux-amd64.tar.zst ollama-linux-amd64.tgz; do
    url="https://github.com/ollama/ollama/releases/latest/download/$name"
    if [ -s "$name" ]; then code=200; else code=$(curl -sL -o "$name" -w "%{http_code}" "$url"); fi
    echo "$name: HTTP $code, $(stat -c %s "$name") bytes"
    if [ "$code" = "200" ]; then
      case "$name" in
        *.tgz) tar -xzf "$name" ;;
        *.tar.zst)
          "$PY" -c "import zstandard" 2>/dev/null || VIRTUAL_ENV="$HOME/.venvs/nun" "$HOME/.local/bin/uv" pip install -q zstandard
          "$PY" -c "import sys, tarfile, zstandard
with open(sys.argv[1], 'rb') as f, zstandard.ZstdDecompressor().stream_reader(f) as r, tarfile.open(fileobj=r, mode='r|') as t:
    t.extractall('.')" "$name" ;;
      esac
      rm -f "$name"
      break
    fi
    rm -f "$name"
  done
fi
"$DEST/bin/ollama" --version
