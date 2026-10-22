import { useEffect, useState } from 'react';
import { api } from '../api';
import { Link } from '../router';
import { SEVERITY_LABEL } from '../context';
import { Icon, Skeleton } from '../ui';

function FilingCard({ f }) {
  const worst = f.flags.filter((x) => x.severity === 'high' || x.severity === 'medium');
  return (
    <Link to={`/ipo/${encodeURIComponent(f.id)}`} className="card filing-card">
      <span className="kicker">{f.meta.doc_type} · {f.meta.pages} pages</span>
      <h3 className="h3">{f.company}</h3>
      <p style={{ margin: 0, fontFamily: 'var(--serif)', fontSize: 17, lineHeight: 1.4, color: 'var(--ink-2)' }}>
        {f.headline || 'Nothing tripped the checks.'}
      </p>
      <div className="row" style={{ marginTop: 'auto', gap: 6 }}>
        {worst.slice(0, 3).map((x) => <span key={x.id} className={`sev ${x.severity}`}>{x.label}</span>)}
        {worst.length === 0 && <span className="sev ok">{SEVERITY_LABEL.ok}</span>}
      </div>
    </Link>
  );
}

const RANK = { high: 0, medium: 1, info: 2, ok: 3 };

// The hero shows a real result instead of a slogan-only page: the filing with the strongest flags.
function Featured({ filings }) {
  if (!filings?.length) return null;
  const score = (f) => Math.min(...f.flags.map((x) => RANK[x.severity]), 9);
  const f = [...filings].sort((a, b) => score(a) - score(b))[0];
  const flags = f.flags.filter((x) => x.severity !== 'ok').slice(0, 3);
  return (
    <Link to={`/ipo/${encodeURIComponent(f.id)}`} className="card featured" aria-label={`Read ${f.company}`}>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <span className="kicker">Latest read · {f.meta.doc_type}, {f.meta.pages} pages</span>
        <span className="mono" style={{ color: 'var(--blue)' }}>Open →</span>
      </div>
      <h2 className="h2" style={{ fontSize: 28 }}>{f.company}</h2>
      {f.headline && <p className="featured-line">{f.headline}</p>}
      <div className="featured-flags">
        {flags.map((x) => (
          <div key={x.id} className={`mini-flag ${x.severity}`}>
            <span className="kicker">{x.label}</span>
            <strong>{x.value}</strong>
          </div>
        ))}
      </div>
      <span className="muted" style={{ fontSize: 13 }}>{f.counts.verified} of {f.counts.facts} quotes checked word for word against the PDF</span>
    </Link>
  );
}

export default function Home({ health }) {
  const [filings, setFilings] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    document.title = 'Footnote · What IPOs bury in the fine print';
    api('/api/filings').then(setFilings).catch((e) => setError(e.message));
  }, []);

  return (
    <main className="wrap page">
      <section className="hero">
      <div className="stack" style={{ gap: 18, paddingTop: 8 }}>
        <div className="kicker">Indian IPO filings, read cover to cover</div>
        <h1 className="h1" style={{ fontSize: 'clamp(40px, 6.4vw, 72px)' }}>What IPOs bury<br />in the fine print.</h1>
        <p className="lede" style={{ maxWidth: '36ch' }}>
          Footnote maps who is connected to a company going public and <em>where the money goes</em>, with the page to prove every line.
        </p>
        <div className="row">
          <a className="btn" href="#filings">See the filings <Icon name="arrow" /></a>
          {health?.uploads && <Link className="btn ghost" to="/add"><Icon name="upload" />Add a filing</Link>}
        </div>
      </div>
      <Featured filings={filings} />
      </section>

      <section className="grid-3" aria-label="How Footnote works">
        {[
          ['Reads the filing', 'Finds the sections that matter: promoters, management, group companies, related-party transactions, litigation, use of proceeds.'],
          ['Maps the connections', 'People are matched by DIN, companies by CIN, bankers by SEBI registration, so the same name links across IPOs.'],
          ['Proves every line', 'Each fact keeps a quote checked word for word against the PDF. Click any page number to see it highlighted.'],
        ].map(([t, d], i) => (
          <div key={t} className="card card-body stack" style={{ gap: 8 }}>
            <span className="mono muted">0{i + 1}</span>
            <h2 className="h3">{t}</h2>
            <p style={{ margin: 0, color: 'var(--ink-2)' }}>{d}</p>
          </div>
        ))}
      </section>

      <section id="filings" className="stack" aria-labelledby="filings-h" style={{ scrollMarginTop: 90 }}>
        <div className="row" style={{ justifyContent: 'space-between' }}>
          <h2 id="filings-h" className="h2">Filings</h2>
          {filings && <span className="muted">{filings.length} read so far</span>}
        </div>
        {error && <div className="notice">Could not reach the server: {error}</div>}
        {!filings && !error && <div className="grid-cards">{[0, 1, 2].map((i) => <Skeleton key={i} h={190} />)}</div>}
        {filings?.length === 0 && (
          <div className="card card-body stack" style={{ alignItems: 'flex-start' }}>
            <h3 className="h3">No filings yet</h3>
            <p style={{ margin: 0 }} className="muted">Add a DRHP, RHP or prospectus PDF and Footnote will read it in a couple of minutes.</p>
            {health?.uploads && <Link className="btn" to="/add"><Icon name="upload" />Add the first filing</Link>}
          </div>
        )}
        {filings?.length > 0 && <div className="grid-cards">{filings.map((f) => <FilingCard key={f.id} f={f} />)}</div>}
      </section>
    </main>
  );
}
