---
tags:
  - concept
  - multi-tenant
  - data-model
created: 2026-08-28
---

# Multi-Tenant Data Model

> Fixed hierarchy: School → SchoolClass → Student.

---

## Hierarchy

```
School (school_id)
  └── SchoolClass (class_id, school_id)
        └── Student (student_id, class_id, school_id)
```

## Rules

- Any new feature must **respect** this hierarchy, not flatten it
- Data ingestion ([[Bob — Data Engineer]]) maps real data into this shape
- API endpoints follow this structure

## Storage

| File | Contents |
|---|---|
| `class_config.json` | School/class registry |
| `brain_state.json` | Model state (students, contents, sessions) |
| `gradepulse_users.db` | User accounts |

## Migration

SQLite migration planned for v0.2 (P2) when student count exceeds ~50.

## Owner

[[Sam — AI/ML Engineer]] — data model
[[Bob — Data Engineer]] — ingestion
[[Ali — Infrastructure]] — storage migration

---

*Source: SAM_TECHNICAL_HANDOFF.md*
