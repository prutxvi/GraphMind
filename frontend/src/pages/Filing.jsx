import { useEffect, useMemo, useState } from 'react';
import { api, METRIC_LABEL } from '../api';
import MapView from '../MapView';
import { Link } from '../router';
import { SEVERITY_LABEL } from '../context';
import { Cite, Icon, Skeleton, Verified } from '../ui';

const titleCase = (s) => (s || '').replace(/_/g, ' ').replace(/^\w/, (c) => c.toUpperCase());

function Excerpt({ filingId, c }) {
  return (
    <div className="stack" style={{ gap: 8 }}>
      <blockquote className="excerpt"><mark>{c.quote || 'No quote captured.'}</mark></blockquote>
      <div className="row" style={{ justifyContent: 'space-between' }}>
        <Verified ok={c.verified} />
        <Cite filingId={filingId} page={c.page} quote={c.quote} verified={c.verified} label={c.page ? `Open page ${c.page}` : undefined} />
      </div>
    </div>
  );
}

function SourcePanel({ data, selected }) {
  const { graph } = data;
  const nodeName = (id) => graph.nodes.find((n) => n.id === id)?.name ?? 'Unknown';
  let kicker; let title; let sub; let citations = []; let extra = null;

  if (selected?.type === 'flag') {
    const f = data.flags.find((x) => x.id === selected.id);
    if (f) {
      kicker = `${f.label} · ${SEVERITY_LABEL[f.severity]}`;
      title = f.value;
      sub = f.detail;
      citations = f.citations;
      if (f.orders?.length) {
        extra = (
          <ul style={{ margin: 0, paddingLeft: 18 }}>
            {f.orders.map((o) => <li key={o.url}><a href={o.url} target="_blank" rel="noreferrer">{o.title || 'SEBI order'}</a> {o.date && <span className="muted">· {o.date}</span>}</li>)}
          </ul>
        );
      }
    }
  } else if (selected?.type === 'edge') {
    const e = graph.edges.find((x) => x.id === selected.id);
    if (e) {
      kicker = e.kind === 'money' ? 'Money between related parties' : 'Connection';
      title = `${nodeName(e.source)} → ${nodeName(e.target)}`;
      sub = e.kind === 'money' ? `${e.natures.join(', ') || 'Transactions'} · ${e.label}` : titleCase(e.label);
      citations = e.citations;
    }
  } else if (selected?.type === 'node') {
    const n = graph.nodes.find((x) => x.id === selected.id);
    if (n) {
      kicker = n.kind === 'person' ? 'Person' : 'Company';
      title = n.name;
      sub = n.roles.join(' · ');
      const seen = new Set();
      for (const e of graph.edges) {
        if (e.source !== n.id && e.target !== n.id) continue;
        for (const c of e.citations) if (!seen.has(c.fact_id) && citations.length < 6) { seen.add(c.fact_id); citations.push(c); }
      }
      extra = (
        <div className="stack" style={{ gap: 6 }}>
          {(n.din || n.cin || n.reg) && (
            <div className="mono muted">{n.din && `DIN ${n.din}`}{n.cin && `CIN ${n.cin}`}{n.reg && `Reg. ${n.reg}`}</div>
          )}
          <Link to={`/entity/${n.id}`}>Everywhere {n.kind === 'person' ? 'this person' : 'this company'} appears <Icon name="arrow" size={14} /></Link>
        </div>
      );
    }
  }
  if (!title) {
    return <aside className="card side card-body muted">Select a flag, a line or a box to see the page it came from.</aside>;
  }
  return (
    <aside className="card side card-body stack" aria-live="polite">
      <div className="kicker">{kicker}</div>
      <h3 className="h2" style={{ fontSize: 22 }}>{title}</h3>
      {sub && <div style={{ color: 'var(--ink-2)' }}>{sub}</div>}
      {extra}
      {citations.length > 0 && <div className="kicker" style={{ marginTop: 6 }}>From the filing</div>}
      {citations.map((c) => <Excerpt key={c.fact_id} filingId={data.id} c={c} />)}
    </aside>
  );
}

function Lists({ data }) {
  const L = data.lists;
  const tabs = [
    ['money', 'Related-party money', L.money.length],
    ['people', 'People', L.people.length],
    ['companies', 'Group companies', L.companies.length],
    ['advisers', 'Advisers', L.advisers.length],
    ['litigation', 'Cases', L.litigation.length],
    ['objects', 'Use of IPO money', L.objects.length],
    ['financials', 'Financials', L.financials.length],
  ].filter((t) => t[2] > 0);
  const [tab, setTab] = useState(tabs[0]?.[0]);
  if (!tabs.length) return null;
  const fid = data.id;
  const cite = (r) => <Cite filingId={fid} page={r.page} quote={r.quote} verified={r.verified} />;

  return (
    <section className="card" aria-labelledby="lists-h">
      <div className="card-head">
        <h2 id="lists-h" className="h2" style={{ fontSize: 22 }}>Everything Footnote found</h2>
        <div className="seg" role="group" aria-label="Choose a list">
          {tabs.map(([key, label, n]) => (
            <button key={key} type="button" aria-pressed={tab === key} onClick={() => setTab(key)}>{label} <span className="muted">{n}</span></button>
          ))}
        </div>
      </div>
      <div className="table-wrap">
        {tab === 'money' && (
          <table><thead><tr><th>Party</th><th>Relationship</th><th>Transaction</th><th className="num">Amount</th><th className="num">% of revenue</th><th>Source</th></tr></thead>
            <tbody>{L.money.map((r, i) => (
              <tr key={i}><td><Link to={`/entity/${r.party_id}`}>{r.party}</Link></td><td className="muted">{r.relationship}</td><td>{r.nature}</td>
                <td className="num">{r.amount_label}</td><td className="num">{r.pct_of_revenue != null ? `${r.pct_of_revenue}%` : '—'}</td><td>{cite(r)}</td></tr>
            ))}</tbody></table>
        )}
        {tab === 'people' && (
          <table><thead><tr><th>Name</th><th>Role</th><th>DIN</th><th>Source</th></tr></thead>
            <tbody>{L.people.map((p) => (
              <tr key={p.id}><td><Link to={`/entity/${p.id}`}>{p.name}</Link></td><td>{p.roles.join(' · ')}</td><td className="mono">{p.din || '—'}</td>
                <td className="row" style={{ gap: 6 }}>{p.citations.slice(0, 3).map((c) => <span key={c.fact_id}>{cite(c)}</span>)}</td></tr>
            ))}</tbody></table>
        )}
        {tab === 'companies' && (
          <table><thead><tr><th>Company</th><th>Listed as</th><th>Source</th></tr></thead>
            <tbody>{L.companies.map((c) => (
              <tr key={c.id}><td><Link to={`/entity/${c.id}`}>{c.name}</Link></td><td>{c.roles.join(', ')}</td><td>{cite(c)}</td></tr>
            ))}</tbody></table>
        )}
        {tab === 'advisers' && (
          <table><thead><tr><th>Firm</th><th>Role</th><th>Registration</th><th>Source</th></tr></thead>
            <tbody>{L.advisers.map((a, i) => (
              <tr key={i}><td><Link to={`/entity/${a.id}`}>{a.name}</Link></td><td>{a.role}</td><td className="mono">{a.registration || '—'}</td><td>{cite(a)}</td></tr>
            ))}</tbody></table>
        )}
        {tab === 'litigation' && (
          <table><thead><tr><th>Against / by</th><th>Type</th><th className="num">Cases</th><th>Summary</th><th className="num">Amount</th><th>Source</th></tr></thead>
            <tbody>{L.litigation.map((l, i) => (
              <tr key={i}><td>{titleCase(l.direction)} {l.party_type}</td><td>{titleCase(l.category)}</td><td className="num">{l.count}</td>
                <td style={{ minWidth: 260 }}>{l.summary}</td><td className="num">{l.amount_label || '—'}</td><td>{cite(l)}</td></tr>
            ))}</tbody></table>
        )}
        {tab === 'objects' && (
          <table><thead><tr><th>Purpose</th><th className="num">Amount</th><th>Source</th></tr></thead>
            <tbody>{L.objects.map((o, i) => (
              <tr key={i}><td>{o.purpose}</td><td className="num">{o.amount_label}</td><td>{cite(o)}</td></tr>
            ))}</tbody></table>
        )}
        {tab === 'financials' && (
          <table><thead><tr><th>Metric</th><th>Year</th><th className="num">Amount</th><th>Source</th></tr></thead>
            <tbody>{L.financials.map((f, i) => (
              <tr key={i}><td>{METRIC_LABEL[f.metric] || titleCase(f.metric)}</td><td>{f.fiscal}</td><td className="num">{f.amount_label}</td><td>{cite(f)}</td></tr>
            ))}</tbody></table>
        )}
      </div>
    </section>
  );
}

// Minimal rendering for model answers: paragraphs, "- " bullets, **bold**, and [S#] citation chips.
function Answer({ text, citations, filingId }) {
  const byId = Object.fromEntries(citations.map((c) => [c.id, c]));
  const inline = (s, key) => s.split(/(\[S\d+\]|\*\*[^*]+\*\*)/g).map((part, i) => {
    const m = part.match(/^\[(S\d+)\]$/);
    if (m) {
      const c = byId[m[1]];
      return c ? <span key={`${key}-${i}`}> <Cite filingId={filingId} page={c.page} quote={c.quote} verified={c.verified} label={`${c.id} · p.${c.page}`} /></span> : null;
    }
    if (part.startsWith('**')) return <strong key={`${key}-${i}`}>{part.slice(2, -2)}</strong>;
    return part;
  });
  const blocks = [];
  let list = [];
  text.split('\n').forEach((line, i) => {
    const t = line.trim();
    if (/^[-*•]\s+/.test(t)) { list.push(<li key={i}>{inline(t.replace(/^[-*•]\s+/, ''), i)}</li>); return; }
    if (list.length) { blocks.push(<ul key={`u${i}`}>{list}</ul>); list = []; }
    if (t) blocks.push(<p key={i}>{inline(t, i)}</p>);
  });
  if (list.length) blocks.push(<ul key="u-end">{list}</ul>);
  return <div className="answer">{blocks}</div>;
}

function Ask({ data, enabled }) {
  const [q, setQ] = useState('');
  const [turns, setTurns] = useState([]);
  const [busy, setBusy] = useState(false);
  const suggestions = [
    'Who are the promoters and how much do they own?',
    'Which related companies does it trade with?',
    'What will the IPO money be used for?',
    'Are any cases pending against the promoters or directors?',
  ];
  const ask = async (question) => {
    if (!question.trim() || busy) return;
    setBusy(true);
    setQ('');
    setTurns((t) => [...t, { question, pending: true }]);
    try {
      const res = await api(`/api/filings/${encodeURIComponent(data.id)}/chat`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ message: question }),
      });
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { question, ...res } : x)));
    } catch (err) {
      setTurns((t) => t.map((x, i) => (i === t.length - 1 ? { question, error: err.message } : x)));
    }
    setBusy(false);
  };
  return (
    <section className="card card-body stack" aria-labelledby="ask-h" style={{ maxWidth: 920 }}>
      <h2 id="ask-h" className="h2" style={{ fontSize: 22 }}>Ask about this filing</h2>
      {!enabled && <div className="notice">Questions are switched off on this server.</div>}
      {turns.map((t, i) => (
        <div key={i} className="stack" style={{ gap: 8, borderTop: i ? '1px solid var(--line-soft)' : 0, paddingTop: i ? 14 : 0 }}>
          <div style={{ fontWeight: 600 }}>{t.question}</div>
          {t.pending && <div className="stack" style={{ gap: 8 }}><Skeleton w="90%" /><Skeleton w="70%" /></div>}
          {t.error && <div className="notice">{t.error}</div>}
          {t.reply && <Answer text={t.reply} citations={t.citations} filingId={data.id} />}
        </div>
      ))}
      <form className="row" onSubmit={(e) => { e.preventDefault(); ask(q); }}>
        <label htmlFor="ask-q" className="sr">Your question</label>
        <input id="ask-q" className="field" style={{ flex: '1 1 320px' }} value={q} onChange={(e) => setQ(e.target.value)}
          placeholder="Ask anything the filing answers" disabled={!enabled} />
        <button className="btn" type="submit" disabled={!enabled || busy || !q.trim()}><Icon name="send" />Ask</button>
      </form>
      {turns.length === 0 && enabled && (
        <div className="chips">{suggestions.map((s) => <button key={s} type="button" className="chip" onClick={() => ask(s)}>{s}</button>)}</div>
      )}
      <p className="muted" style={{ margin: 0, fontSize: 13 }}>Answers use only this filing and cite the page. If the filing doesn't say, Footnote says so. Not investment advice.</p>
    </section>
  );
}

export default function Filing({ id, health }) {
  const [data, setData] = useState(null);
  const [error, setError] = useState(null);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    let live = true;
    api(`/api/filings/${encodeURIComponent(id)}`)
      .then((d) => {
        if (!live) return;
        setData(d);
        document.title = `${d.company} · Footnote`;
        const first = d.flags.find((f) => f.severity !== 'ok') || d.flags[0];
        setSelected(first ? { type: 'flag', id: first.id } : { type: 'node', id: d.issuer_id });
      })
      .catch((e) => live && setError(e.message));
    return () => { live = false; };
  }, [id]);

  const flaggedIds = useMemo(() => new Set((data?.flags || []).filter((f) => f.severity === 'high' || f.severity === 'medium')
    .flatMap((f) => f.entities || [])), [data]);

  if (error) return <main className="wrap page"><div className="notice">{error} <Link to="/">Back to all filings</Link></div></main>;
  if (!data) {
    return (
      <main className="wrap page" aria-busy="true">
        <div className="stack"><Skeleton w={240} /><Skeleton h={52} w="60%" /><Skeleton h={30} w="80%" /></div>
        <div className="flags">{[0, 1, 2].map((i) => <Skeleton key={i} h={150} />)}</div>
        <Skeleton h={480} />
      </main>
    );
  }

  const m = data.meta;
  const shownFlags = data.flags;
  return (
    <main className="wrap page">
      <section className="stack" style={{ maxWidth: 960 }}>
        <div className="kicker">{m.doc_type} · {m.pages} pages{data.promoter_holding_pct ? ` · Promoters hold ${data.promoter_holding_pct}%` : ''}</div>
        <h1 className="h1">{data.company}</h1>
        {data.headline
          ? <p className="lede" style={{ maxWidth: '40ch' }}>{data.headline}</p>
          : <p className="lede" style={{ maxWidth: '40ch' }}>Nothing in this filing tripped Footnote's checks. Read the map and lists to see who is behind it.</p>}
        <div className="stats mono">
          <span>{data.counts.people} people</span><span>{data.counts.related_parties} related parties</span>
          <span>{data.counts.verified} of {data.counts.facts} quotes verified</span><span>read in {Math.round(m.seconds)}s</span>
        </div>
        {m.failed_sections?.length > 0 && <div className="notice">Some sections couldn't be read and are missing: {m.failed_sections.join(', ')}.</div>}
      </section>

      {shownFlags.length > 0 && (
        <section aria-labelledby="flags-h" className="stack">
          <div className="row" style={{ justifyContent: 'space-between', alignItems: 'baseline' }}>
            <h2 id="flags-h" className="h2">What stands out</h2>
            <span className="muted" style={{ fontSize: 13 }}>Fixed rules over what the filing discloses, not AI opinions. A flag is a reason to read, not proof of wrongdoing. <Link to="/method">How checks work</Link></span>
          </div>
          <div className="flags">
            {shownFlags.map((f) => (
              <button key={f.id} type="button" className={`flag ${f.severity}`} aria-pressed={selected?.type === 'flag' && selected.id === f.id}
                onClick={() => { setSelected({ type: 'flag', id: f.id }); document.getElementById('map-h')?.scrollIntoView({ behavior: 'smooth', block: 'start' }); }}>
                <span className="row" style={{ justifyContent: 'space-between', gap: 8 }}>
                  <span className="kicker">{f.label}</span><span className={`sev ${f.severity}`}>{SEVERITY_LABEL[f.severity]}</span>
                </span>
                <span className="value">{f.value}</span>
                <span className="detail">{f.detail}</span>
                <span className="mono" style={{ color: 'var(--blue)' }}>
                  {[...new Set(f.citations.map((c) => c.page).filter(Boolean))].slice(0, 4).map((p) => `p.${p}`).join(' · ')} →
                </span>
              </button>
            ))}
          </div>
        </section>
      )}

      <section className="split" aria-labelledby="map-h">
        <div className="card main">
          <div className="card-head">
            <h2 id="map-h" className="h2" style={{ fontSize: 22, scrollMarginTop: 90 }}>Who is connected</h2>
            <span className="muted" style={{ fontSize: 13 }}>Tap any box or line to see its source</span>
          </div>
          <div style={{ padding: '8px 4px' }}>
            <MapView graph={data.graph} flaggedIds={flaggedIds} selected={selected} onSelect={setSelected} />
          </div>
          <div className="legend">
            <span><i className="sw person" />Person</span><span><i className="sw" />Company</span>
            <span><i className="sw adviser" />Banker, auditor or adviser</span><span><i className="sw money" />Money, thicker = larger</span>
          </div>
        </div>
        <SourcePanel data={data} selected={selected} />
      </section>

      <Lists data={data} />
      <Ask data={data} enabled={!!health?.llm} />
    </main>
  );
}
