---
tags:
  - concept
  - infrastructure
  - multi-worker
created: 2026-08-28
---

# Multi-Worker Sync

> File-based brain state synchronization — resolves the single-worker constraint.

---

## The Problem

Brain state was in-memory. Multiple uvicorn workers forked separate copies that **silently diverged**. System could only run with `--workers 1`.

## The Solution

`linucb_brain/sync.py` — `BrainSynchronizer` class:

| Feature | Detail |
|---|---|
| File-based locking | `fcntl` — prevents concurrent writes |
| Periodic auto-save | 30s default, configurable via `AUTO_SAVE_INTERVAL` env var |
| Independent load | Each worker loads brain state from disk, not parent's fork |

## Status

**RESOLVED** — [[Ali — Infrastructure]] implemented on 2026-08-28.

8 new tests in `test_sync.py`.

## Owner

[[Ali — Infrastructure]]

---

*Source: TEAM_HANDBOOK.md, Decision Log*
