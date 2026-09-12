---
tags:
  - role
  - team
  - mia
created: 2026-08-28
---

# Mia — UI/UX Designer

> All user-facing interfaces, design system, branding, accessibility.

---

## Scope

| Area | Detail |
|---|---|
| Teacher Portal | Streamlit dashboard — full rewrite complete |
| Next.js Frontend | Production SaaS — 15/15 files complete |
| Offline HTML Tool | Standalone downloadable tool |
| Design System | Navy/gold palette, Inter font, spacing scale |
| Branding | Logo integration across all surfaces |
| Accessibility | ARIA, keyboard nav, focus management |
| UX Research | Empty/error/loading states, micro-interactions |

## Out of Scope

- Core algorithms → [[Sam — AI/ML Engineer]]
- REST API → [[Sam — AI/ML Engineer]]
- Deployment → [[Ali — Infrastructure]]
- Data ingestion → [[Bob — Data Engineer]]

## Key Files

- `teacher_portal.py` — Streamlit dashboard
- `gradepulse-web/` — Next.js frontend
- `generate_offline.py` — Offline HTML generator
- `assets/logo.png` — Brand logo

## Current Status

| Component | Status |
|---|---|
| Design System | Complete |
| Teacher Portal | Complete |
| Next.js Frontend | Complete (15/15) |
| Offline HTML Tool | Complete |
| Branding | Complete |

## Blockers

- Next.js waiting on `npm install` (network)

## Open Items

- Logged [[Decision Log#Flaky test|flaky test]] in `test_adaptive_gamma.py`

## Reference

- [[MIA_ENGINEERING_PROFILE]]
- [[GradePulse Architecture]]

---

*Source: MIA_ENGINEERING_PROFILE.md, MIA_UNDERSTANDING_AND_ROLE.md*
