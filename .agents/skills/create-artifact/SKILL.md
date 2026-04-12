---
name: create-artifact
description: >
  Use this skill whenever the user wants a comprehensive, standalone document
  rendered as a markdown artifact. Triggers include /create-artifact, write a
  research report, create a comprehensive document, write a thorough analysis,
  make this a deliverable, deep dive on, write up a full report on, or any
  request where the user clearly wants a polished, well-sourced, long-form
  document rather than a conversational answer. Also trigger when the user says
  artifact in the context of wanting a document output, or when a research
  question is complex enough that the answer warrants structured sections,
  citations, and 2000+ words. Do NOT trigger for quick answers, code edits,
  conversational Q&A, or file format conversions (use docx/pdf/pptx skills for
  those).
---

# Create Artifact — Comprehensive Markdown Document Skill

## Purpose

Produce a thorough, well-sourced, standalone markdown document rendered as an artifact. The output should read as a finished deliverable — not a chat response with headers bolted on.

## When This Skill Applies

- User explicitly requests `/create-artifact` or similar trigger phrases
- User asks for a research report, analysis, deep dive, literature review, or any long-form written deliverable
- The topic is complex enough to warrant structured sections, evidence, and 2000+ words

## Workspace Vault Contract

For this workspace, `docs/` means the shared Obsidian vault rooted at
`C:\Users\olefa\dev\pete-workspace\docs`, not a repo-local `docs/` folder
inside an individual project repo or uploaded snapshot. Treat YAML
frontmatter, `[[wikilinks]]`, and backlink-oriented body linking as part of
the operating contract whenever reading or writing notes there.

When the current workspace uses the Pete docs vault, read and follow:

- `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`
- `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`
- `docs/reference/workspace/reference_workspace-conventions.md`
- `docs/reference/workspace/reference_vault-context-intake-and-link-strengthening_v1_2026-03-19.md`

Use the shared intake and backlink workflow from the last note for `links`,
`related`, lineage fields, body wikilinks, and backlink fallback search. The
report-specific rules below are deltas, not substitutes.

## Output Format

- Produce one canonical report-family markdown document rather than ad hoc markdown
- Canonical vault path: `docs/reports/artifacts/report_<slug>_<YYYY-MM-DD>.md`
- Use the report-family contract from `docs/reference/workspace/reference_frontmatter-contract-canonical_v1_2026-03-17.md`, routing rules from `docs/reference/workspace/reference_generated-document-routing_v1_2026-03-17.md`, and the canonical body structure from `docs/templates/template_report-canonical_v1_2026-03-17.md`
- Even though this skill is named create-artifact, the filename prefix remains `report_`; represent the subtype with `report_kind: artifact-report`
- Required frontmatter for vault-native output: `project`, `status`, `report_kind: artifact-report`, `production_mode: generated`, `produced_by: create-artifact`, `agent_surface`, `created`, `updated`, `links`, `related`, `external_links`
- Recommended when known: `repos`, `subject`, `supersedes`, `superseded_by`
- Use `status: published` for a finished first-pass deliverable, `status: updated` when revising an existing report, and `status: draft` only when the user explicitly wants an unfinished draft
- Put governing notes and must-read source notes in `links`, adjacent notes in `related`, preserve lineage in `supersedes` / `superseded_by`, and use body wikilinks so the finished report strengthens backlink navigation instead of becoming an orphan
- The body outline must follow the canonical report family:
  - `# Report: <Human Readable Title>`
  - `## Report Type`
  - `## Scope`
  - `## Basis / Inputs`
  - `## Findings / Observations`
  - `## Interpretation`
  - `## Implications / Suggested Follow-up`
  - `## Change Notes`
- Never dump 3000+ words of markdown inline in chat
- Write the artifact directly to the vault at the canonical path using `repo-engineer:repo_create_file`, and also present via `present_files` for convenient access
- After rendering the artifact, provide a brief (2-3 sentence) summary in chat — do not rehash the document

## Research Protocol

Before writing, gather evidence using available tools. The document should be grounded in sources, not generated from training data alone.

1. **Use web search** for current data, market figures, recent developments, news, and industry reports
2. **Use Scholar Gateway** for academic/peer-reviewed claims when the topic warrants it (engineering, science, medicine, policy)
3. **Use Google Drive search** if the user references internal/personal documents as source material
4. **Use conversation search** if the user references prior discussions that should inform the document

Scale research effort to the topic:
- Narrow factual topic → 3-5 searches
- Broad industry analysis → 10-20 searches across multiple subtopics
- Multi-section research report → 15-30+ searches, including Scholar Gateway for academic grounding

## Document Standards

### Structure
- Open with a **bold thesis or executive summary paragraph** — the reader should know the document's core argument within the first 100 words
- Use clear **section headers** (## level) that convey content, not generic labels
- Sections should flow logically — each section should build on or contrast with the previous one
- Close with a conclusion that synthesizes findings rather than merely summarizing them

### Depth and Rigor
- **Substantiate claims with evidence.** If a claim is important, it needs a source or explicit qualification ("evidence suggests," "practitioners report," "no rigorous data exists")
- **State uncertainty explicitly.** If sources conflict, say so. If data is sparse, say so. Do not paper over gaps with confident prose
- **Quantify where possible.** Prefer "market grew 14% YoY to $9.8B" over "the market grew significantly"
- **Include specific examples, case studies, or named entities** rather than generalities
- Use tables or structured comparisons when comparing multiple items across dimensions

### Length Calibration
- **Minimum:** 2,000 words for a focused analysis
- **Typical:** 3,000-6,000 words for a comprehensive report
- **Maximum:** Let the topic dictate length — don't pad, don't truncate prematurely
- Every paragraph should earn its place. Cut filler

### Citation and Sourcing
- Follow the system-level citation instructions (use antml:cite tags for web search sourced claims)
- For Scholar Gateway results, include author, year, journal, and DOI where available
- Distinguish between primary sources (SPE papers, SEC filings, company reports) and secondary sources (analyst reports, news articles, vendor whitepapers)
- Flag vendor-sourced claims with appropriate skepticism

### Tone
- Analytical and direct — this is a technical document, not marketing copy
- Write for a knowledgeable reader. Don't over-explain basics unless the user requests an introductory treatment
- Avoid hedging language that adds no information ("it is worth noting that," "interestingly," "it should be mentioned")
- Use precise language over vague qualifiers

## What NOT To Do

- Do not produce a bulleted listicle and call it a report
- Do not skip research and generate the document purely from training data when tools are available
- Do not add a table of contents unless the document exceeds ~5,000 words
- Do not include a references/bibliography section at the end — citations should be inline
- Do not over-format with excessive bold, italics, or decorative elements
- Do not ask the user clarifying questions if the request is clear enough to produce a solid first draft — produce the draft, then offer to refine
