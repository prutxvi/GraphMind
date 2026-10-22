# Changelog

Notable changes to Footnote. Dates are the day the work landed.

## [Unreleased]

### Added
- Professional README with badges, real screenshots and the measured results of the first
  real filing run.
- `docs/`: architecture, red-flag rules, data model and entity matching, and the full
  Annu Projects filing test.
- `screenshots/`: 12 images captured from the running app — home, filing, connection map,
  flags, lists, a highlighted PDF page, an entity page, method, add, dark mode, and two phone
  views.
- `CHANGELOG.md`.
- CI also runs on the `footnote` branch.

### Changed
- `LICENSE`: copyright holder is now Footnote, and the year is 2026.
- `CONTRIBUTING.md`: rewritten against the real project — real clone URL, real commands, the
  real test and lint setup. The old file was a generic template that named a repository that
  does not exist and a `npm test` script that is not defined.

## [0.3.0] — 2026-10-22 — Footnote

The rebuild of GraphMind into a tool for Indian IPO filings. Working end to end on a real
462-page RHP the same day.

### Added
- Section finding from the filing's own table of contents, with a printed→PDF page offset vote.
- Fixed-field extraction per section with a verbatim quote for every item.
- Quote verification against the page: letters and digits only, part-by-part for shortened
  quotes, first-40-characters fallback for reflowed rows. Unverified items are labelled.
- Entity matching by DIN for people and by CIN, SEBI registration or name for companies.
- Rule-based flags: related-party business as a share of revenue, loans to related parties,
  IPO money to related parties, auditor resignations, pending cases, the lead manager's record,
  and profit without operating cash.
- Headline generation from the strongest flag.
- Deterministic connection map, source panel, and a pdf.js viewer that highlights the exact
  quote on the real page.
- TF-IDF cited Q&A over the filing, with `S1 · p.73`-style sources.
- PAN and Aadhaar redaction of stored page text.
- `--relink`, which rebuilds facts and flags from stored raw extraction with no model calls.
- Paper-and-ink design tokens, dark mode, and a phone layout.

### Changed
- The cash rule now checks every year shown, with a 10% floor, instead of only the latest year.
- Salaries and sitting fees draw as grey *pay* edges; red is kept for business money.
- Bracket suffixes on related-party names move into the transaction type.
- Duplicate advisers and uses of money are de-duplicated.

## [0.2.0] — 2026-10-22 — cited GraphRAG rebuild

### Added
- Whole-document reading instead of the first 6,000 characters.
- Per-upload graphs instead of one global graph shared by every user.
- TF-IDF retrieval instead of substring matching.
- 16 tests on hand-built PDFs and a `FakeLLM`.

## [0.1.0] — 2025-12-05 — GraphMind

### Added
- Initial commit: a 3D knowledge graph built from a PDF, with an AI analyst panel, graph export
  and a Railway deployment.
