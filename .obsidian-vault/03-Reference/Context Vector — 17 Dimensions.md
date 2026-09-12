---
tags:
  - concept
  - context-vector
  - architecture
created: 2026-08-28
---

# Context Vector — 17 Dimensions

> The model's input contract. Every agent must respect this shape.

---

## Shared Features (z, 8 dims)

| Index | Feature | Source |
|---|---|---|
| 0 | `performance_score` | Student's overall score (0-1) |
| 1 | `session_count` | `log1p(sessions) / log1p(100)` |
| 2 | `grade_trend_slope` | Linear regression slope of recent grades |
| 3 | `education_level` | Numeric education level |
| 4 | `age_band` | Numeric age band |
| 5 | `credits_studied` | Credits completed |
| 6 | `imd_band` | Deprivation index (default 0.5) |
| 7 | `region_code` | Numeric region |

## Arm-Specific Features (x, 9 dims)

| Index | Feature | Source |
|---|---|---|
| 0 | `difficulty` | `(content.difficulty - 1) / 4` |
| 1 | `topic_match` | 1.0 if student topic matches content topic |
| 2-5 | `content_type` | One-hot: video, quiz, exercise, reading |
| 6 | `perf_diff` | performance × difficulty interaction |
| 7 | `perf_video` | performance × video interaction |
| 8 | `perf_quiz` | performance × quiz interaction |

## Why It Matters

- Data Engineer ([[Bob — Data Engineer]]) must map real pilot data into this exact shape
- If the shape changes, [[Sam — AI/ML Engineer]]'s model breaks
- Any changes require a [[Decision Log]] entry

## Owner

[[Sam — AI/ML Engineer]] — defines the contract
[[Bob — Data Engineer]] — maps data into it

---

*Source: SAM_TECHNICAL_HANDOFF.md*
