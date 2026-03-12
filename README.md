# Project Babs

Local-first autonomous AI assistant running on MSI EdgeXpert (DGX Spark platform).

## Directory Layout

- `config/` - Version-controlled configuration (model registry, memory budgets, thresholds)
- `docker/` - Docker compose files for all services
- `src/` - Application source code (Supervisor service, orchestrator, tools)
- `docs/` - Architecture documents, philosophy document, character bible
- `scripts/` - Utility scripts, reasoning parsers, deployment helpers
- `seeds/` - Procedural Memory seed entries (Python Code Standards, personality, etc.)
- `tests/` - Test suite

## Runtime Data (not in repo)

`~/babs-data/` holds model weights, vector databases, memory stores, logs, and caches.
Backed up via three-tier backup (local USB, G14 LAN, Google Drive encrypted).
