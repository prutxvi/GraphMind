# Real filing test: Annu Projects Limited

The first run on a real offer document, 22 October 2026 — what came out, how it was checked,
and what got fixed.

## The filing

**Annu Projects Limited**, Red Herring Prospectus dated 18 August 2026, **462 pages**,
mainboard, fetched from SEBI's site as a single document. Chosen because it is a smaller
mainboard issuer, the nearest stand-in for the SME filings that are the target.

## Run

| | |
|---|---|
| Sections found from the filing's own table of contents | 9 of 9, page offset 3 |
| Model calls | 22 |
| Time | 2 min 22 s |
| Facts | 122, of which **120 verified word for word** |
| Connection map | 34 nodes, 55 edges |

## Accuracy check against pages read by hand

| Item | Footnote | ✓ |
|---|---|---|
| Promoters | Sanjay Kumar Sarraf, Krishna Ranjan, together 87.64% | ✅ |
| Directors' DINs | 01174144, 01265320, 03370404, 00996242, 09698462, 00701892 | ✅ all six |
| Lead manager | Mefcom Capital Markets, INM000000016 | ✅ |
| Registrar, legal counsel, syndicate | KFin (INR000000221), Dentons Link Legal, Mefcom Securities | ✅ |
| Auditor change | SCAN Associates resigned 23 May 2024, "pre-occupation" | ✅ |
| Group companies | Opticon Pipes, Terragon Techno Machines, Balaji Travco, Ann Projects | ✅ |
| FY26 related-party amounts | ₹33.78 M, 27.82 M, 24.24 M, 15.44 M, 14.31 M (₹ million) | ✅ to the decimal |
| Use of IPO money | Capex ₹15.41 Cr, working capital ₹115 Cr, GCP to be decided | ✅ |

## What it flagged

- **Business with related companies, 5.36% of revenue** (₹12.95 Cr, mainly Terragon and
  Opticon) → the headline
- **Profit without cash:** ₹21.10 Cr profit in FY25 with −₹35.38 Cr operating cash
- **Auditor resigned** (2024)
- **16 pending cases**, mostly tax, ₹2.13 Cr at stake where stated (for context)
- **Reassuring:** the filing states no IPO money goes to related parties

Asking "Who are the promoters and how much do they own?" returned the correct answer citing
p.279. The PDF viewer highlighted the exact Terragon row on page 74.

## Problems found, and fixed with `--relink` (no extra model calls)

1. "Opticon Pipes (Services)" became a separate company; the bracket now moves into the
   transaction type.
2. The cash rule used only FY26 (−₹24.7 lakh) and missed FY25; it now checks all years with a
   10% floor.
3. Duplicate advisers and uses of money; now de-duplicated, with the summary table only.
4. Committee roles ("Member", "Chairperson") showed as job titles; dropped.
5. Quotes shortened with "…" or ";" failed verification; they now verify part by part.
6. Salaries were drawn in red on the map; they are now grey *pay* edges.
7. "Balaji Courier and Cargo" was taken for a person; the company keyword list was widened.

## Still open

- "Rajan" (director, DIN 03370404) and "Rajan Nandlal" (salary row, no DIN) are probably the
  same person and stay separate on purpose.
- 2 unverified quotes: the model stitched separate lines.
