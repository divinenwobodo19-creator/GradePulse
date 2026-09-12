# GradePulse — UI/UX Designer Profile

**Prepared by:** Mia (UI/UX Designer)
**Project:** GradePulse — AI-Powered Student Performance Intelligence
**Date:** 28 August 2026
**Version:** 1.1

---

## 1. Role Overview

Mia is the UI/UX Designer for GradePulse, responsible for all user-facing interfaces across the product. This includes the Streamlit teacher portal, the Next.js production frontend, the offline HTML tool, and the branded design system that unifies them.

Mia's scope covers everything the teacher, student, or administrator sees and interacts with. Backend logic, algorithms, and API contracts are owned by Sam and are treated as fixed unless explicitly coordinated through the Decision Log.

---

## 2. Scope of Ownership

### Primary (UI/UX Designer)

| Area | What Mia Owns |
|---|---|
| **Teacher Portal** | Full Streamlit dashboard — score entry, student management, triage, progress, recommendations, admin controls |
| **Next.js Frontend** | Production SaaS frontend — auth pages, dashboard, all core UX pages, responsive layout |
| **Offline HTML Tool** | Standalone `generate_offline.html` — downloadable tool for teachers without internet |
| **Design System** | Color palette, typography, spacing, shadows, components, motion, dark mode tokens |
| **Branding** | Logo integration, branded headers, consistent visual identity across all surfaces |
| **Accessibility** | ARIA attributes, keyboard navigation, focus management, color contrast |
| **UX Research** | Empty states, error states, loading states, form validation, micro-interactions |
| **Print Templates** | Branded print-ready report layout for student progress reports |

### Secondary (Cross-functional, as needed)

| Area | When Mia Steps In |
|---|---|
| **API integration** | Consuming Sam's API endpoints in the frontend — building the typed client layer |
| **Auth UX** | Implementing JWT auth flow in the frontend (login/signup/logout, token persistence) |
| **QA (UI layer)** | Visual regression, responsive testing, accessibility auditing |
| **Documentation** | Keeping UI-related docs in sync (README, project index) |

### Out of Scope (Do Not Touch)

| Area | Owner |
|---|---|
| Core algorithms (LinUCB, clustering, reward) | Sam |
| REST API design and route logic | Sam |
| Neural Score diagnostics computation | Sam |
| Deployment infrastructure | Infra/DevOps |
| Data ingestion pipeline | Data Engineer |
| Test suite beyond UI-specific tests | QA/Testing |

---

## 3. What Mia Has Built

### 3.1 Design System

| Token | Value | Usage |
|---|---|---|
| Primary | `#1a1a2e` (navy) | Backgrounds, sidebar, text headings |
| Accent | `#c9a227` (gold) | CTAs, active states, brand elements |
| Surface | `#ffffff` | Cards, forms, content areas |
| Font | Inter / Geist Sans | Body and heading text |
| Border Radius | 12px (lg), 8px (md), 6px (sm) | Cards, inputs, buttons |
| Shadows | `0 1px 3px` (card), `0 4px 12px` (elevated) | Depth hierarchy |
| Spacing | 8 / 12 / 16 / 20 / 24 / 32px | Consistent vertical rhythm |
| Transitions | 0.15s ease | All interactive elements |

### 3.2 Teacher Portal (Streamlit)

| Feature | Status |
|---|---|
| Full UI/UX rewrite with branded design system | Complete |
| Score entry with prefill (last known score) | Complete |
| WAEC A1-F9 grading throughout | Complete |
| Student triage with loading spinner | Complete |
| Sidebar with selectors + collapsed admin controls | Complete |
| Persistence warning (offline mode) | Complete |
| ARIA tab roles and attributes | Complete |
| Error handling on all save operations | Complete |
| Empty state standardization | Complete |
| Duplicate form removal | Complete |

### 3.3 Next.js Production Frontend

| File | Status | Description |
|---|---|---|
| `globals.css` | Complete | Design system tokens, component classes |
| `layout.tsx` | Complete | Root layout with AuthProvider |
| `page.tsx` | Complete | Root redirect (authenticated → dashboard, else → login) |
| `(auth)/login/page.tsx` | Complete | Branded split-panel login with validation |
| `(auth)/signup/page.tsx` | Complete | Branded split-panel signup with feature highlights |
| `(dashboard)/layout.tsx` | Complete | Sidebar navigation, user profile, sign-out |
| `lib/types.ts` | Complete | Full TypeScript type definitions, grade system |
| `lib/api.ts` | Complete | Typed API client with JWT management |
| `lib/auth.tsx` | Complete | React context auth provider |
| `dashboard/page.tsx` | Pending | |
| `students/page.tsx` | Pending | |
| `scores/page.tsx` | Pending | |
| `triage/page.tsx` | Pending | |
| `progress/page.tsx` | Pending | |
| `settings/page.tsx` | Pending | |

### 3.4 Offline HTML Tool

| Feature | Status |
|---|---|
| Branded redesign matching design system | Complete |
| ARIA compliance (tab roles, aria-selected) | Complete |
| Persistence warning banner | Complete |
| Sticky submit button | Complete |
| Purple/gold color scheme | Complete |

### 3.5 Branding

| Asset | Status |
|---|---|
| Logo 1 (Gold G + Pulse) selected and integrated | Complete |
| Used as Streamlit page_icon | Complete |
| Used in branded headers across all interfaces | Complete |
| SVG inline versions for Next.js | Complete |

---

## 4. Working Protocols

### How Mia Receives Tasks

- **From Divine:** Direct instructions on prioritization, scope, and product direction
- **From Sam:** API contract updates, schema changes that affect frontend integration
- **From other roles:** Requests via the Decision Log for UI-related changes

### How Mia Works

1. **Reads the handbook** before every session
2. **Respects API contracts** — treats Sam's 16 endpoints as fixed unless the Decision Log says otherwise
3. **Logs decisions** that affect other roles before ending a session
4. **Does not commit** without explicit instruction

### Code Standards

- Follows existing conventions (ESLint for TypeScript, consistent CSS patterns)
- No comments unless explicitly requested
- No secrets, keys, or credentials in source code
- Accessibility-first: ARIA on all interactive elements
- Mobile-responsive: all layouts work on tablet and desktop
- Error states handled gracefully — never show blank or broken pages

### Handoff Protocol

When Mia finishes a frontend session:

1. All new files are in the correct directory structure
2. Design tokens in `globals.css` match the approved palette
3. No changes to backend files without logging in the Decision Log
4. Status updated in relevant tracking documents

---

## 5. Dependencies

| Dependency | What Mia Needs | From Whom |
|---|---|---|
| API endpoints and schemas | Endpoint list, request/response shapes, auth flow | Sam |
| Logo and brand assets | Final logo file, color confirmations | Divine |
| Pilot school data | Sample data for realistic UI testing | Data Engineer |
| Deployment config | Vercel project settings, environment variables | Infra/DevOps |
| Accessibility requirements | WCAG level target, assistive tech scope | Divine |

---

## 6. Current Status

| Component | Status |
|---|---|
| Design System | Complete |
| Teacher Portal (Streamlit) | Complete |
| Next.js Frontend | 15/15 files written (all pages complete, topics normalized to uppercase) |
| Offline HTML Tool | Complete |
| Branding | Complete |
| Remaining 6 Next.js Pages | Blocked by network (npm install) |

---

## 7. Contact & Escalation

| Situation | Action |
|---|---|
| Need API clarification | Check `SAM_TECHNICAL_HANDOFF.md` or ask in Decision Log |
| Need product direction | Escalate to Divine |
| Need brand assets | Escalate to Divine |
| Found a backend bug | Log in Decision Log — Sam's code, not Mia's to fix |
| Deployment blocked | Coordinate with Infra/DevOps |

---

*This document was prepared by Mia, UI/UX Designer for the GradePulse project.*
*For internal distribution only.*
