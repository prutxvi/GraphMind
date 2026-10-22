# Red-flag rules

Every check Footnote runs. All of them are **fixed rules over cited facts** — no model decides
what is suspicious. Code: `backend/footnote/report.py`.

> **Wording rule.** A flag is **a reason to read, not proof of wrongdoing.** Related-party
> transactions are legal and often ordinary. Severity labels in the UI: **Look closely**
> (high) · **Worth reading** (medium) · **For context** (info) · **Reassuring** (ok).

| Flag | Rule | Severity |
|---|---|---|
| **Business with related companies** | Sum of sales, purchases, services, rent, lease, commission and similar with related **companies** in the latest fiscal, as a share of revenue (the filing's own percentage column where present, otherwise computed from revenue). Salaries excluded. | ≥10% high · ≥3% medium · else info. Thresholds `RPT_HIGH_PCT`, `RPT_MEDIUM_PCT` |
| **Money lent to related parties** | Related-party rows whose nature is a loan or advance **given** | medium |
| **IPO money to related parties** | Any `proceeds_to_related` fact | high |
| ↳ reassuring version | The filing states that no proceeds go to promoters, directors or group companies | ok |
| **Auditor resigned** | An auditor change whose reason mentions resignation, within the 3-year window disclosed | medium |
| **Pending cases** | Cases **against** the company, promoters or directors | high if criminal against a promoter or director · medium if regulatory or disciplinary against them · else info |
| **Lead manager's record** | Lead manager matched by normalised name or SEBI registration in the hand-checked `data/sebi_orders.json` | high, with the orders linked |
| ↳ context version | The same lead manager appears on other filings in the database | info, "N IPOs here" |
| **Profit without cash** | Any year shown with PAT > 0 and operating cash < 0, where the cash burn is at least 10% of that profit; the worst year is shown | medium |

## The headline

The first **high or medium** flag that has a headline template becomes the page's one-liner:

- *"Annu Projects did ₹12.95 Cr of business with its own related companies in Fiscal 2026,
  5.36% of its revenue."*
- *"X reported a ₹21.10 Cr profit in 2025, but its operations used ₹35.38 Cr of cash."*

If no flag fires: *"Nothing in this filing tripped Footnote's checks."*

## The SEBI orders file

`data/sebi_orders.json`, following the format in `data/sebi_orders.example.json`: `entity`,
`registration`, `date`, `title`, `url`, `status` (interim or final). **Hand-checked, one entry
per order, SEBI URL required.** It is empty today, so the lead-manager check cannot fire yet.

## Changed after the real filing test

- The cash rule first used only the latest year and flagged a tiny −₹24.7 lakh FY26 dip while
  missing FY25's −₹35.38 Cr. It now checks every year shown, with a 10% floor.
- Map and money: salaries and sitting fees became grey **pay** edges, with red kept for
  business money only.
