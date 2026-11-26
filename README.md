<img src="assets/icon.svg" width="64" height="64" alt="">

# Cupbearer — Hacksgiving 2026

Cupbearer is a two-Sprite zero-secret security butler. A persistent Butler Sprite receives Telegram and Box artifacts, while an ephemeral Airlock Sprite detonates them behind an explicit wildcard-deny network policy and rolls back to a clean checkpoint after every run.

## Local verification

```bash
uv run --extra dev pytest
uv run python deploy/setup_sprites.py --probe --dry-run
```

The probe validates payload shapes and required configuration without printing secrets. Live smoke verification is `uv run python deploy/setup_sprites.py --smoke` after Fly.io connectors and Sprites are provisioned.

## Architecture

- `cupbearer`: persistent FastAPI/Telegram/Box service and Forensic Light Table.
- `cupbearer-airlock`: connector-free detonation Sprite with PyMuPDF, script execution, Playwright-capable link capture, planted canaries, sanitized PDF output, deny-all egress, and checkpoint rollback.
- Sprites Connectors Gateway carries Telegram, Box, Pinecone, LLM, and path-pinned Airlock control calls. Raw third-party credentials must never be present on either Sprite.
- Pinecone's integrated-embedding index must be pre-created in the Pinecone console because connector-side index creation is not currently supported.
- The artifact ceiling is 16 MiB because Sprites `fs/write` is capped at 16 MiB.

## Deployment shape

`deploy/cupbearer-service.json` describes the public Butler service. `deploy/airlock-baseline.sh` prepares the clean Airlock image before the baseline checkpoint is captured. `deploy/setup_sprites.py --probe` is the early contract probe required before live gateway wiring.

The Light Table is served at `/` and `/i/{id}` with a strict CSP, external JavaScript only, and `textContent`-based rendering for untrusted evidence.
