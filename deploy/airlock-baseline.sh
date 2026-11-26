#!/usr/bin/env bash
set -euo pipefail
python -m pip install --upgrade pip
python -m pip install 'cupbearer[airlock]'
python -m playwright install --with-deps chromium
command -v git >/dev/null
command -v strace >/dev/null || true
python - <<'PY'
import os
bad=[k for k in os.environ if any(s in k.lower() for s in ('telegram','box','pinecone','gemini','ollama')) and not k.startswith(('TELEGRAM_CONNECTION_ID','BOX_CONNECTION_ID','PINECONE_CONNECTION_ID','LLM_CONNECTION_ID'))]
if bad:
    raise SystemExit('raw provider-like environment keys present: '+','.join(sorted(bad)))
print('airlock baseline ready; create a Sprites checkpoint now')
PY
