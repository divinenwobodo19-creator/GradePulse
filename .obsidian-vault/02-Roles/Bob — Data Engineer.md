---
tags:
  - role
  - team
  - bob
  - data-engineer
created: 2026-08-28
---

# Bob — Data Engineer

> Pilot-school data ingestion into Sam's multi-tenant schema.

---

## Scope

| Area | Detail |
|---|---|
| Data ingestion | CSV/Excel → [[Context Vector — 17 Dimensions]] |
| Validation | Schema enforcement, messy data cleaning |
| Mapping | `School → SchoolClass → Student` hierarchy |
| Sample data | 5 students, 8 content items for UI testing |

## Out of Scope

- Context vector dimensionality → [[Sam — AI/ML Engineer]]
- API contract changes → [[Sam — AI/ML Engineer]]
- Model code → [[Sam — AI/ML Engineer]]

## Key Files

- `ingest.py` — CLI ingestion tool
- `sample_data/sample_students.csv` — 5 students, 2 schools
- `sample_data/sample_content.csv` — 8 content items

## Ingestion Modes

| Mode | Flag |
|---|---|
| Live ingestion | (default) |
| Validate only | `--validate-only` |
| Dry run | `--dry-run` |

## Completed

- `ingest.py` CLI — CSV/Excel, validation, cleaning, hierarchy mapping
- Sample data — Nigerian names, WAEC grades (JSS1-SSS3), realistic scores
- Topics normalized to uppercase — [[Decision Log#Topic normalization|flagged for Sam]]

## Reference

- [[GradePulse Architecture]]
- [[Context Vector — 17 Dimensions]]

---

*Source: TEAM_HANDBOOK.md, data-engineer.md*
