# Footnote¹

**What IPOs bury in the fine print, with the page to prove it.**

An Indian IPO filing (DRHP, RHP or prospectus) runs 300 to 800 pages. Who owns the company, which family companies it does business with, who its bankers are, and which cases it is fighting are all disclosed, but scattered across sections almost nobody reads.

Footnote reads the filing, maps **who is connected to the company and where the money goes**, runs fixed checks over what it finds, and links every line to the page of the PDF it came from, with the quote highlighted.

## What you get for each filing

- **A one-line headline** written from the strongest finding, e.g. *"Acme Agro did ₹36.00 Cr of business with its own related companies in Fiscal 2026, 15% of its revenue."*
- **Red flags from fixed rules**, not AI opinions: related-party business as a share of revenue, money lent to related parties, IPO money going to related parties, auditor resignations, pending criminal or regulatory cases, the lead manager's record across filings and SEBI orders, and profit without operating cash.
- **A connection map**: promoters and directors on the left, group and related companies on the right, bankers and auditors on top, and money drawn in red with thickness by amount.
- **The source, always**: click any flag, line, box or page number and the real PDF page opens with the quote highlighted. Quotes are checked word for word; anything not found is marked unverified.
- **People and companies across IPOs**: people are linked only by DIN, companies by CIN, SEBI or firm registration, so "everywhere this banker appears" is one click.
- **Questions with citations**: answers use only the filing and cite `S1 · p.73`-style sources.

## How it works

```
PDF ──► table of contents ──► ~10 sections that matter (≈60 of 460 pages)
            │
            ▼
   fixed-field extraction per section (LLM), each item with a verbatim quote
            │
            ▼
   quote verified against the page ─► entities matched by DIN / CIN / SEBI reg ─► SQLite
            │
            ▼
   rule-based flags · headline · connection map · cited Q&A
```

A 462-page RHP takes about 22 model calls (roughly 40K input tokens). PAN, Aadhaar and home addresses are scrubbed from everything stored, even though filings print them.

## Run it

Requires Python 3.10+ and Node 20+.

```bash
# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env            # add LLM_API_KEY (any OpenAI-compatible endpoint)
uvicorn main:app --reload       # http://127.0.0.1:8000/docs

# Frontend, second terminal
cd frontend
npm install
npm run dev                     # http://localhost:5173 (proxies /api to :8000)
```

Add filings from the **Add** page, or in bulk from the command line:

```bash
cd backend
python -m footnote.ingest ~/Downloads/filings/*.pdf
```

Download filings by hand from SEBI, NSE Emerge or BSE SME. NSE's terms prohibit automated collection.

### Lead managers with SEBI orders

The lead-manager check reads `data/sebi_orders.json`, a hand-checked list. Copy `data/sebi_orders.example.json`, add one entry per order with its SEBI URL, and the flag appears on every filing that banker handled.

## Tests

```bash
cd backend && pytest
```

The suite builds offer documents as real PDFs and runs the whole pipeline on a fake model, so it needs no network or key. It covers table-of-contents parsing and the page offset, amount units, quote verification, PAN redaction, DIN-based matching, every flag rule, cross-filing links, and the API. CI also lints and builds the frontend.

## Limits

- Extraction can miss or misread items. That's why every line links to its page, and unverified quotes are labelled.
- Scanned (image-only) PDFs need OCR first.
- People without a DIN in the filing are not linked across filings, on purpose: names collide.
- Flags describe what the company disclosed. **A flag is a reason to read, not proof of wrongdoing. Not investment advice.**

## Deploy

One service: the frontend builds into `backend/static` and FastAPI serves both. `railway.json` and `nixpacks.toml` are included. Set `ALLOW_UPLOADS=0` on a public deployment to serve only filings you have already read.

## License

MIT, see [LICENSE](LICENSE).
