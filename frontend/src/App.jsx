import { Suspense, lazy, useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { api } from './api';
import { ViewerContext } from './context';
import { match, navigate, usePath } from './nav';
import { Link } from './router';
import { Icon } from './ui';
import Add from './pages/Add';
import Entity from './pages/Entity';
import Filing from './pages/Filing';
import Home from './pages/Home';
import Method from './pages/Method';

// pdf.js is large and only needed once someone opens a page.
const PdfViewer = lazy(() => import('./PdfViewer'));

const THEME_KEY = 'footnote:theme';
const readTheme = () => { try { return localStorage.getItem(THEME_KEY); } catch { return null; } };

function ThemeToggle() {
  const [theme, setTheme] = useState(() => readTheme()
    || (window.matchMedia?.('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'));
  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try { localStorage.setItem(THEME_KEY, theme); } catch { /* storage unavailable */ }
  }, [theme]);
  const next = theme === 'dark' ? 'light' : 'dark';
  return (
    <button type="button" className="icon-btn" aria-label={`Switch to ${next} mode`} onClick={() => setTheme(next)}>
      <Icon name={theme === 'dark' ? 'sun' : 'moon'} />
    </button>
  );
}

function Search() {
  const [q, setQ] = useState('');
  const [res, setRes] = useState(null);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  const box = useRef(null);

  useEffect(() => {
    if (q.trim().length < 2) return undefined;
    const t = setTimeout(() => api(`/api/search?q=${encodeURIComponent(q)}`).then(setRes).catch(() => setRes(null)), 160);
    return () => clearTimeout(t);
  }, [q]);
  useEffect(() => {
    const close = (e) => { if (!box.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('mousedown', close);
    return () => document.removeEventListener('mousedown', close);
  }, []);

  const shown = q.trim().length >= 2 ? res : null;
  const items = useMemo(() => [
    ...(shown?.filings || []).map((f) => ({ key: `f${f.id}`, to: `/ipo/${encodeURIComponent(f.id)}`, label: f.company, hint: 'Filing' })),
    ...(shown?.entities || []).map((e) => ({ key: `e${e.id}`, to: `/entity/${e.id}`, label: e.name,
      hint: e.din ? `DIN ${e.din}` : e.reg ? `Reg. ${e.reg}` : e.kind === 'person' ? 'Person' : 'Company' })),
  ], [shown]);

  const go = (to) => { setOpen(false); setQ(''); navigate(to); };
  const onKey = (e) => {
    if (e.key === 'ArrowDown') { e.preventDefault(); setActive((a) => Math.min(a + 1, items.length - 1)); }
    if (e.key === 'ArrowUp') { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
    if (e.key === 'Enter' && items[active]) { e.preventDefault(); go(items[active].to); }
    if (e.key === 'Escape') setOpen(false);
  };

  return (
    <div className="search" ref={box}>
      <div className="search-box">
        <Icon name="search" />
        <label htmlFor="search" className="sr">Search filings, people, companies or bankers</label>
        <input id="search" type="search" placeholder="Search an IPO, promoter, DIN or merchant banker" value={q} autoComplete="off"
          role="combobox" aria-expanded={open && !!shown} aria-controls="search-results"
          onChange={(e) => { setQ(e.target.value); setOpen(true); setActive(0); }} onFocus={() => setOpen(true)} onKeyDown={onKey} />
      </div>
      {open && shown && (
        <div className="search-results" id="search-results" role="listbox">
          {items.length === 0 && <div className="empty">Nothing matches “{q}” yet.</div>}
          {items.map((it, i) => (
            <a key={it.key} href={it.to} role="option" aria-selected={i === active}
              onClick={(e) => { e.preventDefault(); go(it.to); }} onMouseEnter={() => setActive(i)}>
              <span>{it.label}</span><small>{it.hint}</small>
            </a>
          ))}
        </div>
      )}
    </div>
  );
}

export default function App() {
  const path = usePath();
  const route = match(path);
  const [health, setHealth] = useState(null);
  const [viewer, setViewer] = useState(null);
  useEffect(() => { api('/api/health').then(setHealth).catch(() => setHealth({ llm: false, uploads: false })); }, []);
  const open = useCallback((target) => setViewer(target), []);
  const close = useCallback(() => setViewer(null), []);
  const ctx = useMemo(() => ({ open }), [open]);

  return (
    <ViewerContext.Provider value={ctx}>
      <a href="#content" className="sr">Skip to content</a>
      <header className="top">
        <div className="wrap">
          <Link to="/" className="brand" aria-label="Footnote home"><b>Footnote<sup>1</sup></b><span>IPO filings</span></Link>
          <Search />
          <nav className="nav" aria-label="Main">
            <Link to="/">Filings</Link>
            <Link to="/method">Method</Link>
            {health?.uploads && <Link to="/add">Add</Link>}
            <ThemeToggle />
          </nav>
        </div>
      </header>
      <div id="content">
        {route.page === 'home' && <Home health={health} />}
        {route.page === 'filing' && <Filing key={route.id} id={route.id} health={health} />}
        {route.page === 'entity' && <Entity key={route.id} id={route.id} />}
        {route.page === 'method' && <Method />}
        {route.page === 'add' && <Add health={health} />}
        {route.page === 'missing' && <main className="wrap page"><h1 className="h1">Page not found</h1><Link to="/">Back to filings</Link></main>}
      </div>
      <footer className="foot">
        <div className="wrap">
          <span>Facts from public filings, not allegations. A flag is a reason to read, not proof of wrongdoing. Not investment advice.</span>
          <span>Footnote · open source</span>
        </div>
      </footer>
      {viewer && (
        <Suspense fallback={null}>
          <PdfViewer key={`${viewer.filingId}-${viewer.page}-${viewer.quote}`} target={viewer} onClose={close} />
        </Suspense>
      )}
    </ViewerContext.Provider>
  );
}
