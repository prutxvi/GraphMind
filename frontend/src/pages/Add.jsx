import { useEffect, useRef, useState } from 'react';
import { api } from '../api';
import { navigate } from '../nav';
import { Icon } from '../ui';

const FOUND_LABEL = {
  directors: 'directors', intermediaries: 'advisers', transactions: 'related-party transactions',
  promoters: 'promoters', group_companies: 'group companies', items: 'cases', objects: 'uses of money',
};

export default function Add({ health }) {
  const [file, setFile] = useState(null);
  const [over, setOver] = useState(false);
  const [job, setJob] = useState(null);
  const [error, setError] = useState(null);
  const input = useRef(null);

  useEffect(() => { document.title = 'Add a filing · Footnote'; }, []);

  useEffect(() => {
    if (!job?.id || job.status === 'ready' || job.status === 'error') return undefined;
    const t = setInterval(async () => {
      try {
        const s = await api(`/api/filings/${encodeURIComponent(job.id)}/status`);
        setJob(s);
        if (s.status === 'ready') setTimeout(() => navigate(`/ipo/${encodeURIComponent(s.id)}`), 600);
      } catch (e) { setError(e.message); }
    }, 1200);
    return () => clearInterval(t);
  }, [job]);

  const start = async (f) => {
    setFile(f); setError(null);
    const body = new FormData();
    body.append('file', f);
    try {
      const { id } = await api('/api/filings', { method: 'POST', body });
      setJob({ id, status: 'queued', progress: { stage: 'reading', message: 'Uploading' } });
    } catch (e) { setError(e.message); }
  };

  const p = job?.progress || {};
  const stages = [
    ['reading', 'Reading the PDF'],
    ['extracting', p.total ? `Reading ${p.total} section parts (${p.done || 0} done)` : 'Reading the sections that matter'],
    ['linking', 'Linking people, companies and money'],
    ['done', 'Ready'],
  ];
  const at = Math.max(0, stages.findIndex(([k]) => k === p.stage));
  const found = Object.entries(p.found || {}).filter(([k, v]) => FOUND_LABEL[k] && v > 0);

  return (
    <main className="wrap page" style={{ maxWidth: 760 }}>
      <section className="stack">
        <div className="kicker">Add a filing</div>
        <h1 className="h1">Read a new IPO filing</h1>
        <p style={{ margin: 0, color: 'var(--ink-2)' }}>
          Upload a DRHP, RHP or prospectus PDF downloaded from SEBI, NSE or BSE. Footnote reads the sections that matter,
          which usually takes two to four minutes.
        </p>
      </section>
      {!health?.uploads && <div className="notice">Adding filings is switched off on this server.</div>}
      {!job && health?.uploads && (
        <label className={`dropzone${over ? ' over' : ''}`}
          onDragOver={(e) => { e.preventDefault(); setOver(true); }} onDragLeave={() => setOver(false)}
          onDrop={(e) => { e.preventDefault(); setOver(false); const f = e.dataTransfer.files[0]; if (f) start(f); }}>
          <Icon name="upload" size={28} />
          <strong style={{ fontSize: 17 }}>Drop the PDF here, or choose a file</strong>
          <span className="muted">Up to 60 MB · text PDFs only (not scans)</span>
          <input ref={input} type="file" accept="application/pdf,.pdf" className="sr" onChange={(e) => e.target.files[0] && start(e.target.files[0])} />
        </label>
      )}
      {error && <div className="notice">{error}</div>}
      {job && (
        <section className="card card-body stack" aria-live="polite">
          <div className="row" style={{ justifyContent: 'space-between' }}>
            <strong style={{ fontFamily: 'var(--serif)', fontSize: 20 }}>{file?.name}</strong>
            <span className="muted mono">{job.status}</span>
          </div>
          <div className="bar" aria-hidden="true">
            <div style={{ width: `${job.status === 'ready' ? 100 : 10 + (p.total ? (70 * (p.done || 0)) / p.total : 0) + (p.stage === 'linking' ? 15 : 0)}%` }} />
          </div>
          <ol className="steps">
            {stages.map(([key, label], i) => (
              <li key={key}>
                <span className={`dot ${i < at || job.status === 'ready' ? 'done' : i === at ? 'now' : ''}`}>
                  {(i < at || job.status === 'ready') && <Icon name="check" size={13} />}
                </span>
                <span style={{ color: i <= at ? 'var(--ink)' : 'var(--muted)' }}>{label}</span>
              </li>
            ))}
          </ol>
          {p.message && job.status !== 'error' && <div className="muted mono">{p.message}</div>}
          {found.length > 0 && (
            <div className="stats" style={{ color: 'var(--ink-2)' }}>
              Found so far: {found.map(([k, v]) => <span key={k}><strong>{v}</strong> {FOUND_LABEL[k]}</span>)}
            </div>
          )}
          {job.status === 'error' && (
            <div className="notice">
              {p.message}{' '}
              <button type="button" className="btn ghost" style={{ marginTop: 10 }} onClick={() => { setJob(null); setFile(null); }}>Try another file</button>
            </div>
          )}
        </section>
      )}
    </main>
  );
}
