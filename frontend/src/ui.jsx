import { useViewer } from './context';

export function Icon({ name, size = 16, ...rest }) {
  const paths = {
    search: <><circle cx="11" cy="11" r="7" /><path d="M20 20l-3.5-3.5" /></>,
    check: <path d="M5 12l5 5 9-10" />,
    alert: <><path d="M12 4l9 16H3z" /><path d="M12 10v4M12 17v.5" /></>,
    page: <><path d="M6 3h8l4 4v14H6z" /><path d="M14 3v4h4" /></>,
    close: <path d="M6 6l12 12M18 6L6 18" />,
    sun: <><circle cx="12" cy="12" r="4" /><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4" /></>,
    moon: <path d="M20 14.5A8 8 0 019.5 4a8 8 0 1010.5 10.5z" />,
    arrow: <path d="M5 12h14M13 6l6 6-6 6" />,
    upload: <><path d="M12 16V4M7 9l5-5 5 5" /><path d="M4 16v4h16v-4" /></>,
    ext: <><path d="M14 4h6v6M20 4l-9 9" /><path d="M18 14v6H4V6h6" /></>,
    send: <path d="M4 12l16-8-6 16-2-7z" />,
  };
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"
      strokeLinecap="round" strokeLinejoin="round" aria-hidden="true" {...rest}>
      {paths[name]}
    </svg>
  );
}

// A citation: opens the filing at that page with the quote highlighted.
export function Cite({ filingId, page, quote, verified, label }) {
  const viewer = useViewer();
  if (!page) return <span className="cite unverified" title="Page not found">p.?</span>;
  return (
    <button type="button" className={`cite${verified === false ? ' unverified' : ''}`}
      onClick={(e) => { e.stopPropagation(); viewer.open({ filingId, page, quote }); }}
      title={verified === false ? 'Quote not found word for word; check the page' : 'Open this page of the filing'}>
      {verified === false ? <Icon name="alert" size={12} /> : null}
      {label ?? `p.${page}`}
    </button>
  );
}

export function Verified({ ok }) {
  return ok
    ? <div className="verified"><Icon name="check" size={15} />Quote found word for word in the filing</div>
    : <div className="verified no"><Icon name="alert" size={15} />Not found word for word, so check the page</div>;
}

export function Skeleton({ h = 18, w = '100%', style }) {
  return <div className="skeleton" style={{ height: h, width: w, ...style }} />;
}
