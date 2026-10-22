# Contributing to Footnote

Footnote reads Indian IPO filings, maps who is connected to whom, and links every line to the
page it came from. Contributions are welcome — especially new red-flag rules, better entity
matching, and more filings read and checked.

## Before you start

- **Never commit a filing PDF, a database, or an API key.** `data/.gitignore` excludes
  `filings/` and `*.db`; `.env` is excluded at the root. If a key ever lands in a commit,
  rotate it.
- **A flag is a reason to read, not proof of wrongdoing.** Any rule you add must say what it
  measured and cite the page, and must not name anyone as guilty.
- Filing documents are public, but they print PAN, Aadhaar and home addresses. Keep them out of
  stored text.

## Set up

```bash
git clone https://github.com/prutxvi/GraphMind.git
cd GraphMind
git checkout -b feature/your-feature-name

# Backend
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements-dev.txt
cp .env.example .env                 # set LLM_API_KEY only if you want to read a new filing

# Frontend, second terminal
cd frontend
npm install
```

Running the app, in two terminals:

```bash
cd backend && uvicorn main:app --reload     # http://127.0.0.1:8000/docs
cd frontend && npm run dev                  # http://localhost:5173
```

## Test before you push

```bash
cd backend && pytest          # 16 tests, no network, no API key
cd frontend && npm run lint
cd frontend && npm run build
```

The suite builds offer documents as real PDFs and runs the whole pipeline on a `FakeLLM`.
**A new rule needs a test that fails without it**, and a test for the case where it must stay
silent.

## Changing a red-flag rule

1. Add or change the rule in `backend/footnote/report.py`. Thresholds belong in
   `config.py` and must be settable from the environment.
2. Cite at least one fact per flag; a flag without a page is not allowed.
3. Add the rule to `docs/red-flag-rules.md`, with its rule text and severity.
4. Re-run an existing filing with `python -m footnote.ingest --relink <filing-id>` to see the
   change without spending model calls, then `pytest`.

## Changing extraction or matching

Extraction changes cost model calls, so store the raw output and use `--relink` while you
iterate. If you change how entities match, say in the pull request what happens to names that
collide — the DIN-only rule for people exists to prevent a wrong merge.

## Code style

- **Python:** PEP 8, type hints on function signatures, docstrings on modules and public
  functions, standard library first. Keep the backend dependency list short.
- **JavaScript/React:** functional components with hooks, camelCase, no new dependency without
  a reason in the pull request. The router is 28 lines on purpose.
- **Comments** explain why, not what. The existing code is the reference.

## Commits and pull requests

Atomic commits, imperative subject line, one idea per commit:

```
Add: flag for auditor resignation inside the 3-year window
Fix: verify quotes split by an ellipsis part by part
Docs: describe the DIN-only matching rule
```

In the pull request:

- [ ] `pytest` passes, and a new rule has a test that fails without it
- [ ] `npm run lint` and `npm run build` pass
- [ ] New behaviour is described in `README.md` or `docs/`
- [ ] `CHANGELOG.md` has an entry under *Unreleased*
- [ ] No filing PDF, database file, or secret is committed
- [ ] UI changes include a screenshot

## Reporting a bug

Include the filing (issuer name and page), what Footnote showed, what the page actually says,
and the command you ran. A wrong number with its page is the most useful bug report there is.

## Good first issues

- Populate `data/sebi_orders.json` from `data/sebi_orders.example.json`, so the lead-manager
  check can fire.
- Add a rule for a disclosure that matters and is not checked yet.
- Read the 3 SEBI-acted SME filings (Synoptics, Varyaa, Nirman Agri) and report what the tool
  missed.
- OCR support for scanned, image-only filings.
