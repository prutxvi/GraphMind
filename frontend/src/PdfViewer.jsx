import { useEffect, useRef, useState } from 'react';
import * as pdfjs from 'pdfjs-dist';
import workerUrl from 'pdfjs-dist/build/pdf.worker.min.mjs?url';
import { pdfUrl } from './api';
import { Icon } from './ui';

pdfjs.GlobalWorkerOptions.workerSrc = workerUrl;

const docs = new Map(); // filingId -> Promise<PDFDocumentProxy>, so reopening is instant
const loadDoc = (filingId) => {
  if (!docs.has(filingId)) docs.set(filingId, pdfjs.getDocument({ url: pdfUrl(filingId) }).promise);
  return docs.get(filingId);
};

const alnum = (s) => s.toLowerCase().replace(/[^a-z0-9]/g, '');

// Find the text items that make up the quote, comparing letters and digits only
// (PDF tables extract with irregular spacing), and return their rectangles in page pixels.
function highlightRects(items, quote, viewport) {
  const needle = alnum(quote || '');
  if (needle.length < 8) return [];
  let joined = '';
  const owners = [];
  items.forEach((item, idx) => {
    const a = alnum(item.str);
    joined += a;
    for (let i = 0; i < a.length; i++) owners.push(idx);
  });
  let at = joined.indexOf(needle);
  let len = needle.length;
  if (at < 0) { // reflowed rows: fall back to the opening 40 characters
    len = Math.min(40, needle.length);
    at = joined.indexOf(needle.slice(0, len));
  }
  if (at < 0) return [];
  const hit = new Set(owners.slice(at, at + len));
  return [...hit].map((idx) => {
    const item = items[idx];
    const tx = pdfjs.Util.transform(viewport.transform, item.transform);
    const h = Math.hypot(tx[2], tx[3]);
    return { left: tx[4], top: tx[5] - h, width: item.width * viewport.scale, height: h * 1.15 };
  });
}

export default function PdfViewer({ target, onClose }) {
  const { filingId, quote } = target;
  const [page, setPage] = useState(target.page);
  const [total, setTotal] = useState(null);
  const [state, setState] = useState({ status: 'loading' });
  const canvasRef = useRef(null);
  const bodyRef = useRef(null);
  const closeRef = useRef(null);

  useEffect(() => {
    closeRef.current?.focus();
    const onKey = (e) => { if (e.key === 'Escape') onClose(); };
    window.addEventListener('keydown', onKey);
    document.body.style.overflow = 'hidden';
    return () => { window.removeEventListener('keydown', onKey); document.body.style.overflow = ''; };
  }, [onClose]);

  useEffect(() => {
    let cancelled = false;
    let task;
    (async () => {
      try {
        setState({ status: 'loading' });
        const doc = await loadDoc(filingId);
        if (cancelled) return;
        setTotal(doc.numPages);
        const p = await doc.getPage(page);
        const width = Math.min(bodyRef.current?.clientWidth - 40 || 800, 820);
        const base = p.getViewport({ scale: 1 });
        const scale = width / base.width;
        const viewport = p.getViewport({ scale });
        const ratio = window.devicePixelRatio || 1;
        const canvas = canvasRef.current;
        canvas.width = Math.floor(viewport.width * ratio);
        canvas.height = Math.floor(viewport.height * ratio);
        canvas.style.aspectRatio = `${viewport.width} / ${viewport.height}`;
        const ctx = canvas.getContext('2d');
        task = p.render({ canvasContext: ctx, viewport, transform: ratio !== 1 ? [ratio, 0, 0, ratio, 0, 0] : null });
        await task.promise;
        const text = await p.getTextContent();
        if (cancelled) return;
        const rects = page === target.page ? highlightRects(text.items, quote, viewport) : [];
        setState({ status: 'ready', rects, width: viewport.width, height: viewport.height });
        if (rects[0]) bodyRef.current?.scrollTo({ top: Math.max(0, rects[0].top - 120), behavior: 'smooth' });
      } catch (err) {
        if (!cancelled && err?.name !== 'RenderingCancelledException') setState({ status: 'error', message: err.message });
      }
    })();
    return () => { cancelled = true; task?.cancel(); };
  }, [filingId, page, quote, target.page]);

  const pct = (v, of) => `${(100 * v) / of}%`;

  return (
    <div className="viewer" role="dialog" aria-modal="true" aria-label={`Filing page ${page}`} onClick={onClose}>
      <div className="viewer-panel" onClick={(e) => e.stopPropagation()}>
        <div className="viewer-head">
          <strong style={{ fontFamily: 'var(--serif)', fontSize: 18 }}>Page {page}{total ? <span className="muted" style={{ fontWeight: 400 }}> of {total}</span> : null}</strong>
          <div className="row" style={{ marginLeft: 'auto' }}>
            <button className="btn ghost" type="button" disabled={page <= 1} onClick={() => setPage(page - 1)}>Previous</button>
            <button className="btn ghost" type="button" disabled={total && page >= total} onClick={() => setPage(page + 1)}>Next</button>
            <a className="btn ghost" href={`${pdfUrl(filingId)}#page=${page}`} target="_blank" rel="noreferrer">
              <Icon name="ext" />Full PDF
            </a>
            <button ref={closeRef} className="icon-btn" type="button" aria-label="Close" onClick={onClose}><Icon name="close" /></button>
          </div>
        </div>
        <div className="viewer-body" ref={bodyRef}>
          {state.status === 'error' && <div className="notice">Could not open the PDF: {state.message}</div>}
          <div className="pdf-page" style={{ maxWidth: 820 }}>
            <canvas ref={canvasRef} aria-label={`Rendered page ${page} of the filing`} />
            {state.status === 'ready' && state.rects.map((r, i) => (
              <div key={i} className="pdf-hl" style={{ left: pct(r.left, state.width), top: pct(r.top, state.height),
                width: pct(r.width, state.width), height: pct(r.height, state.height) }} />
            ))}
            {state.status === 'loading' && <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center' }} className="muted">Opening page…</div>}
          </div>
        </div>
        {quote && page === target.page && (
          <div className="viewer-quote">
            <span className="kicker" style={{ display: 'block', marginBottom: 4 }}>
              {state.status === 'ready' && state.rects.length === 0 ? 'Quote (not located on the rendered page, read it in full)' : 'Highlighted quote'}
            </span>
            “{quote}”
          </div>
        )}
      </div>
    </div>
  );
}
