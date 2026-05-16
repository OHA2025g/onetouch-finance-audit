# Part 7 — UX review, gap analysis, QA, training, maturity, recommendations

## 17. UX / UI deep review

| UX area | Observation | Impact | Recommendation | Priority |
|---------|-------------|--------|------------------|----------|
| CFO cockpit load | Playwright stuck on “Loading command center…” | CFO cannot see KPIs | Optimize `/dashboard/cfo`; add skeleton timeout + retry | High |
| Sidebar density | Many nested sections | Cognitive load | Progressive disclosure / favorites | Medium |
| Filter discoverability | Masters strip on many pages | Users may miss scope | Onboarding tooltip | Medium |
| Theme | Login + header toggles | Good for demos | Document pattern for branding | Low |
| Mobile | Sidebar drawer | Acceptable | Test long tables on small screens | Medium |
| Accessibility | `aria-expanded` on nav toggles | Partial | Full WCAG audit | Medium |

---

## 18. Gap analysis (detailed selection)

| Gap ID | Module | Screen | Current | Expected | Severity | Priority |
|--------|--------|--------|---------|----------|----------|----------|
| G-001 | CFO | Cockpit | Indefinite loading possible | KPIs <3s | High | P0 |
| G-002 | Auth | Login | No forgot password | Self-service reset | Medium | P2 |
| G-003 | Notifications | Global | Toasts only | Email alerts for SLA | Medium | P2 |
| G-004 | Docs | Product | Field dictionary partial | Full OpenAPI-linked dictionary | Medium | P2 |
| G-005 | RBAC | API | UI hides routes | Server must 403 all APIs | Critical | P0 |

### Ranked gaps

| Rank | Gap | Why it matters | Fix |
|------|-----|----------------|-----|
| 1 | API RBAC enforcement | Security / compliance | Backend middleware tests |
| 2 | CFO data SLA | Blocks executive use | Profiling + caching |
| 3 | Password recovery | Ops burden | Add flow |

---

## 19. Recommended enhancements

| ID | Enhancement | Benefit | Complexity | Phase |
|----|-------------|---------|------------|-------|
| E-01 | Health banner when KPI APIs slow | Transparency | Low | Quick win |
| E-02 | Unified search across cases/evidence | Speed | High | Strategic |
| E-03 | Saved views per user | UX | Medium | Medium |
| E-04 | Export audit of downloads | Compliance | Medium | Medium |

---

## 20. QA test scenarios (sample matrix)

| Test ID | Module | Screen | Scenario | Steps (abbrev) | Expected | Priority |
|---------|--------|--------|----------|----------------|----------|----------|
| QA-LOGIN-01 | Auth | Login | Valid CFO | Persona quick login | Redirect `/app/cfo` | P0 |
| QA-LOGIN-02 | Auth | Login | Invalid password | Wrong pwd | Toast error | P1 |
| QA-CFO-01 | CFO | Cockpit | KPI visible | Load `/app/cfo` | `cfo-cockpit` visible | P0 |
| QA-CFO-02 | CFO | Cockpit | Run all | Click run | Toast w counts | P1 |
| QA-NAV-01 | Shell | Layout | CFO hubs | Loop module URLs | `app-layout` | P0 |
| QA-NAV-02 | Shell | Layout | Super admin | Admin routes | No redirect login | P0 |
| QA-KPI-01 | CFO | KPI drill | Direct URL | `/app/kpi/audit_readiness_pct` | Page renders | P1 |
| QA-EV-01 | Evidence | Explorer | List | Open `/app/evidence` | Rows or empty | P1 |
| QA-UP-01 | Admin | Upload | CSV | Upload sample | 200 or validation msg | P2 |

**Full suite:** duplicate patterns from each file in `apps/frontend/tests/e2e/*.spec.js`.

---

## 21. Training guide (outline)

### CFO training topics

| Topic | Screens | Exercise |
|-------|---------|----------|
| Assurance overview | Cockpit | Change entity filter, read KPIs |
| Drill to action | KPI drill, cases | Open KPI → follow contributor link |
| Committee pack | Cockpit | Download PDF pack |
| Close & FP&A | MEC, BvA | Walk one variance comment |

### Auditor training

| Topic | Screens | Exercise |
|-------|---------|----------|
| Engagements | Audit planning | Open engagement, navigate to papers |
| Evidence | Evidence | Filter exceptions, open drill |
| Report studio | Report studio | Preview report |

### Super Admin training

Users, admin console, upload, governance — **Hands-on in staging only**.

---

## 22. Implementation handover notes

| Area | Observation | Implication |
|------|-------------|-------------|
| API surface | Documented in cross-check file | Contract tests per router |
| RBAC | UI-only filtering | Must mirror in FastAPI dependencies |
| LLM | Optional env | Feature flags for demo vs prod |
| Playwright | CFO shell tests flaky on slow API | Add API mocks or longer timeout in CI |

---

## 23. Application maturity assessment

| Dimension | Score /5 | Reason |
|-----------|----------|--------|
| Functional completeness | 4 | Broad routes + backends |
| Workflow completeness | 3 | Many paths need UAT proof |
| Dashboard maturity | 4 | Rich CFO design |
| Drill-down maturity | 4 | KPI + drillPaths |
| Reporting maturity | 3 | Select exports |
| AI maturity | 2 | Optional / variable |
| UX maturity | 3 | Loading edge cases |
| RBAC maturity | 3 | Verify server-side |
| Data quality maturity | 3 | Seed vs prod |
| Admin maturity | 4 | Multiple admin screens |
| Auditability | 3 | Logs exist — coverage TBD |
| Scalability readiness | 3 | Not load-tested here |
| Client-readiness | 3 | Needs customer UAT |
| Training-readiness | 3 | This doc pack helps |
| Implementation-readiness | 4 | Docker + seeds |

---

## 24. Final recommendations

1. **Understanding:** OneTouch Audit AI is a multi-surface assurance platform spanning CFO dashboards, workbenches, audit lifecycle, and admin.
2. **Strongest modules:** CFO cockpit (when API healthy), audit planning subtree, phase L4-tested workbenches.
3. **Weakest areas:** Optional AI reliability, password recovery, notification channels beyond toast.
4. **Critical workflows:** Login → cockpit → KPI/case resolution; exception → drill; engagement → report.
5. **Top 10 improvements:** (1) API performance SLO, (2) server RBAC proofs, (3) forgot password, (4) email alerts, (5) unified search, (6) offline/slow mode UX, (7) mobile table patterns, (8) OpenAPI-linked field dictionary, (9) customer branding pack, (10) telemetry for feature usage.
6. **Next phase:** Customer-specific UAT on staging with credentials; expand Parts 2–3 per screen A–P; wire CI Playwright to stable seed.

---

*End of Part 7.*
