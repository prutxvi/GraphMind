import { useEffect, useState } from 'react';
import { api } from '../api';
import { Link } from '../router';
import { Cite, Skeleton } from '../ui';

export default function Entity({ id }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  useEffect(() => {
    api(`/api/entities/${id}`).then((d) => { setData(d); document.title = `${d.entity.name} · Footnote`; }).catch((e) => setError(e.message));
  }, [id]);

  if (error) return <main className="wrap page"><div className="notice">{error}</div></main>;
  if (!data) return <main className="wrap page"><Skeleton h={52} w="50%" /><Skeleton h={200} /></main>;
  const { entity, appearances } = data;
  const ids = [entity.din && `DIN ${entity.din}`, entity.cin && `CIN ${entity.cin}`, entity.reg && `Registration ${entity.reg}`].filter(Boolean);

  return (
    <main className="wrap page">
      <section className="stack" style={{ maxWidth: 900 }}>
        <div className="kicker">{entity.kind === 'person' ? 'Person' : 'Company or firm'}</div>
        <h1 className="h1">{entity.name}</h1>
        {ids.length > 0 && <div className="stats mono">{ids.map((x) => <span key={x}>{x}</span>)}</div>}
        <p className="lede" style={{ fontSize: 22 }}>
          Appears in <em style={{ color: appearances.length > 1 ? 'var(--accent)' : 'var(--ink)' }}>{appearances.length} filing{appearances.length === 1 ? '' : 's'}</em> Footnote has read.
        </p>
        {entity.kind === 'person' && !entity.din && (
          <div className="notice">No DIN was found for this person, so Footnote does not link them across filings by name alone. Two people can share a name.</div>
        )}
      </section>
      <section className="stack" aria-label="Appearances">
        {appearances.map((a) => (
          <div key={a.filing_id} className="card">
            <div className="card-head">
              <Link to={`/ipo/${encodeURIComponent(a.filing_id)}`} className="h3" style={{ fontFamily: 'var(--serif)' }}>{a.company}</Link>
              <span className="muted">{a.roles.join(' · ')}</span>
            </div>
            {a.facts.length > 0 && (
              <ul className="card-body" style={{ margin: 0, paddingLeft: 36, display: 'flex', flexDirection: 'column', gap: 8 }}>
                {a.facts.slice(0, 12).map((f) => (
                  <li key={f.fact_id}>{f.label} <Cite filingId={a.filing_id} page={f.page} quote={f.quote} verified={f.verified} /></li>
                ))}
              </ul>
            )}
          </div>
        ))}
      </section>
    </main>
  );
}
