# AccessLens — Design Spec

**Date:** 2026-06-12
**Contest:** Microsoft Agents League @ AI Skills Fest (deadline June 14, 2026, 11:59 PM PT)
**Track:** Reasoning Agents (Microsoft Foundry)
**IQ layer:** Foundry IQ (required integration; centerpiece of this project)

## One-liner

A Microsoft Foundry reasoning agent that scans any website live, cross-references real
accessibility violations against a Foundry IQ knowledge base of standards (WCAG 2.2,
EN 301 549, ADA), and produces a prioritized remediation plan where every
recommendation carries a citation.

## Award targets (one prize per person — stack eligibility, maximize odds)

| Award | Why eligible |
|---|---|
| Best Reasoning Agent ($6,468) | Track entry; observable multi-step pipeline |
| Best use of IQ tools ($6,468) | Foundry IQ knowledge base is the grounding core |
| Hack for Good (3 winners) | Accessibility for community orgs = community need |
| Accessibility award (3 winners) | Project subject + our own UI is accessibility-first |
| Best Overall ($16,468) | Automatic consideration |

## Judging rubric mapping

- **Reasoning & Multi-step Thinking (20%)** — named pipeline stages with typed
  handoffs, streamed live to the UI as a reasoning log.
- **Reliability & Safety (20%)** — citation-required rule (no recommendation without
  a grounded source), guardrails pipeline at every stage boundary, graceful
  degradation, "insufficient evidence" over hallucination.
- **Accuracy & Relevance (20%)** — real axe-core scan data mapped to authoritative
  standards via Foundry IQ agentic retrieval.
- **UX & Presentation (15%)** — accessible single-page UI with live agent step log;
  polished 5-min demo ending with AccessLens scanning its own UI.
- **Creativity (15%)** — live tool output fused with grounded retrieval; the
  self-scan closing beat.

## Lessons adopted from previous winner (CertPrep, issue microsoft/agentsleague#76)

1. Named pipeline stages with **Pydantic typed contracts** at every boundary.
2. **Countable guardrails pipeline** run at every stage boundary.
3. **Zero-credential mock mode**: full pipeline runs offline from fixtures, so judges
   can run it without Azure and the demo cannot fail.
4. **pytest suite that needs no credentials**.
5. Submission writeup with technical highlights and a Challenges & Learnings table.

Our differentiator vs. that template: Foundry IQ agentic retrieval (didn't exist last
round; now mandatory + has a dedicated award) and a live tool-augmented scan instead
of synthetic inputs.

## Architecture

```
User (accessible web UI: semantic HTML + vanilla JS)
   │  POST /scan {url}   +  SSE stream of pipeline events
   ▼
FastAPI backend (Python 3.12, uv)
   │  orchestrates the typed pipeline
   ▼
Pipeline (4 named stages, Pydantic contracts, guardrails between each)
   1. Scanner        — Playwright + axe-core → ScanReport
   2. StandardsMapper — Foundry agent + Foundry IQ knowledge base (MCP) → MappedFindings
   3. ImpactAssessor  — Foundry agent reasoning → PrioritizedFindings
   4. RemediationPlanner — Foundry agent → RemediationPlan (citations required)
   ▼
Azure side:
   - Microsoft Foundry project, model deployment (gpt-4o-mini, Global Standard)
   - Foundry Agent Service prompt agent(s) via azure-ai-projects SDK
   - Foundry IQ knowledge base (agentic retrieval) ← knowledge source:
     Azure Blob Storage (curated WCAG 2.2, WCAG techniques, EN 301 549 summary,
     ADA Title II web rule guidance)
```

Stages 2–4 may be implemented as one Foundry prompt agent invoked with
stage-specific instructions, or as separate agents — decided during implementation
by what the SDK makes reliable fastest. Either way each stage has its own typed
input/output contract, guardrail checks, and visible entry in the reasoning log.

## Components

### 1. Scan tool (local Python)
- Playwright (Chromium, headless) loads the URL, injects axe-core, runs `axe.run()`.
- Output: `ScanReport` — list of violations (rule id, impact, WCAG tags, affected
  nodes, HTML snippets), page metadata, timing.
- Registered as a Foundry **function tool** when running in live mode; also callable
  directly by the orchestrator.

### 2. Foundry IQ knowledge base
- Blob container with curated public standards documents (HTML/PDF/markdown):
  WCAG 2.2 spec + Understanding docs (selected), WCAG quick-ref techniques,
  EN 301 549 summary, ADA Title II web accessibility rule guidance.
- Knowledge source (indexed, auto chunking/embedding) wrapped in a knowledge base.
- Retrieval instructions: "Only return answers supported by retrieved evidence.
  Always include source references."
- Connected to the agent via MCP per current docs
  (learn.microsoft.com/azure/foundry/agents/how-to/foundry-iq-connect).

### 3. Pipeline contracts (Pydantic v2)
- `ScanReport` → `MappedFindings` (each finding linked to standard sections w/
  citation ids) → `PrioritizedFindings` (impact × effort scoring with stated
  rationale) → `RemediationPlan` (steps, code-level suggestions, citations,
  "insufficient evidence" entries where retrieval came back empty).

### 4. Guardrails pipeline (target: ~10 named rules, run at every boundary)
Examples: URL scheme/host validation (no file://, no private IPs — SSRF guard);
scan size/time limits; schema validation on every handoff; citation-required rule
(BLOCK any recommendation lacking a source reference); empty-retrieval honesty rule
(must emit "insufficient evidence"); PII scrub on scanned snippets; output length
caps; model-refusal passthrough. Severity levels BLOCK / WARN / INFO; BLOCK halts
the pipeline with a user-readable explanation.

### 5. Web UI (accessibility-first — this is an award criterion)
- FastAPI serves a single page: semantic HTML, landmarks, keyboard navigable,
  visible focus, aria-live region for the streaming reasoning log, WCAG AA contrast.
  No heavy framework (Streamlit's accessibility is poor).
- Live "agent reasoning" step log (SSE): plan → tool call → retrieval queries →
  synthesis, then the final cited report.
- Report: violations grouped by severity, each remediation with citation links to
  the exact standard section.

### 6. Mock mode (zero credentials)
- `ACCESSLENS_MOCK=1`: Scanner returns a recorded `ScanReport` fixture for the
  bundled demo page; stages 2–4 use recorded Foundry/Foundry IQ responses.
- Full pipeline, guardrails, and UI run deterministically offline. Judges'
  quick-start path in the README uses mock mode.

## Error handling

- Unreachable URL / timeout → structured error in `ScanReport`, agent explains and
  stops gracefully (shown in demo as the safety story).
- Empty/low-confidence retrieval → "insufficient evidence" entry, never invented fix.
- Azure throttling/transient errors → bounded retries with backoff; on hard failure,
  fall back to mock-mode messaging rather than crash.
- Run expiry (Foundry runs expire 10 min) → tool outputs submitted promptly;
  pipeline timeboxes each stage.

## Testing

- pytest, zero credentials needed: contract tests for every Pydantic model,
  guardrail rule tests (parameterized), scanner test against a deliberately broken
  local HTML fixture, end-to-end pipeline test in mock mode.
- Manual + automated accessibility check of our own UI (axe scan of AccessLens by
  AccessLens — also the demo's closing beat).

## Deliverables (submission requirements)

1. Working project (this repo, public on GitHub) with README: hero section, quick
   start (mock mode first), architecture, technical highlights, challenges &
   learnings table, award-category mapping.
2. Architecture diagram (Mermaid in README + exported PNG) showing Microsoft
   Foundry + Foundry IQ usage explicitly.
3. Demo video ≤ 5 min (YouTube): live scan of a real site → reasoning log →
   cited plan → graceful-failure beat → self-scan finale.
4. Project description for the contest form.
5. Registration + profile activation at aka.ms/agentsleague/aisf (Krist, manual).

## Timeline (~2.5 days)

- **June 12 (tonight):** Krist: register + Azure free trial. Build: repo scaffold,
  Pydantic contracts, scanner + fixtures, guardrails skeleton, knowledge doc curation.
- **June 13:** Azure: Foundry project, model deployment, blob upload, knowledge
  source/base, agent wiring (function tool + IQ via MCP). UI + SSE log. Mock-mode
  recordings. Tests green.
- **June 14:** Polish, README + diagram, record/edit/upload demo video, submit by
  early evening PT (hours of buffer before 11:59 PM PT).

## Risks & mitigations

- **Azure free-trial quota for model deployments** → gpt-4o-mini Global Standard;
  region fallback; worst case the whole demo ships in mock mode with recorded live
  traces (still shows real Foundry integration in video).
- **Foundry IQ preview API surface shifts** → follow the foundry-iq-connect doc +
  Azure-Samples/azure-search-python-samples agentic-retrieval-pipeline-example.
- **Time** — UI kept to one page; knowledge base kept to 4 curated sources; video
  recorded with a written shot list, single take + trims.

## Out of scope (YAGNI)

Multi-page crawling, auth-gated scanning, PDF report export, user accounts,
persistence beyond a local run log, CI/CD, deployment hosting (runs locally for
judges; live video shows the real Azure wiring).
