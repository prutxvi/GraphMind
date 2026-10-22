# Data model and entity matching

What is stored, and how the same person or company is recognised across IPOs.

## SQLite tables (`data/footnote.db`)

| Table | Holds |
|---|---|
| `filings` | id (slug), company, issuer_id, pdf_path, status (queued, processing, ready, error), progress JSON, meta JSON |
| `pages` | page text per filing, redacted, for chat and source previews |
| `entities` | kind (`person` or `org`), name, din, cin, reg |
| `entity_keys` | every key that points at an entity — the matching index |
| `facts` | filing, kind, subject → object, attrs JSON, amount (₹), page, quote, verified, section |
| `extractions` | raw model output per chunk, so `--relink` needs no model calls |

## Fact kinds

`director` · `promoter` · `promoter_holding` · `promoter_group` · `group_company` ·
`directorship` (person → other company) · `intermediary` (role and registration) ·
`auditor_change` · `rpt` (related-party transaction: nature, relationship, fiscal, % of
revenue) · `litigation` · `object` (use of money) · `proceeds_to_related` ·
`no_related_proceeds` · `financial`

## Matching rules

> **People link across filings only by DIN.** Names collide ("Rajan" is common), and a wrong
> merge would tie someone to another company's fraud case. Without a DIN a person is keyed
> `pname:<filing>:<name>`, so they match within one filing only.

| Kind | Keys, strongest first |
|---|---|
| Person | `din:01174144` → `pname:<filing>:<normalised name>` |
| Company or firm | `cin:…` → `reg:INM000000016` (SEBI or firm registration) → `org:<normalised name>` |

- **Within one filing**, a name-only mention (a salary row, say) resolves to the DIN of the
  same name seen in the board table.
- **Organisation name normalisation:** lowercase, `&` → and, drop `M/s` and `The`, Pvt →
  Private, Ltd → Limited, strip a trailing Private Limited, Limited or LLP. So "Hill Machines
  Pvt. Ltd." equals "Hill Machines Private Limited".
- **Person or company?** A keyword list (Limited, LLP, Traders, Pipes, Courier, Cargo, Power…),
  widened after "Balaji Courier and Cargo" was taken for a person.
- **Bracket suffixes** on related parties, such as "Opticon Pipes Private Limited (Services)",
  move into the transaction type. HUF and LLP are kept.

> **Known gap.** "Rajan" (director, DIN 03370404) and "Rajan Nandlal" (salary row, no DIN) are
> probably one person and stay separate by design. A possible later fix: match a full-name
> extension within the same filing only.
