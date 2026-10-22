import { useEffect, useMemo, useState } from 'react';

const MAX_PER_COLUMN = 9;
const MAX_TOP = 4;

function useNarrow(limit = 720) {
  const [narrow, setNarrow] = useState(() => window.innerWidth < limit);
  useEffect(() => {
    const on = () => setNarrow(window.innerWidth < limit);
    window.addEventListener('resize', on);
    return () => window.removeEventListener('resize', on);
  }, [limit]);
  return narrow;
}

// The role a box shows when an entity has several, most telling first.
const ROLE_PRIORITY = ['Promoter', 'Lead manager', 'Former auditor (resigned)', 'Receives IPO money', 'Group company',
  'Promoter group', 'Director', 'Related party', 'Independent director', 'Other company of a director'];
const topRole = (roles) => [...roles].sort((a, b) => {
  const ia = ROLE_PRIORITY.indexOf(a); const ib = ROLE_PRIORITY.indexOf(b);
  return (ia < 0 ? 99 : ia) - (ib < 0 ? 99 : ib);
})[0];

const clip = (s, n) => (s.length > n ? `${s.slice(0, n - 1).trimEnd()}…` : s);
const shortName = (s) => s.replace(/\s+(private limited|pvt\.? ltd\.?|limited|ltd\.?)$/i, '');

function rankLeft(n) {
  if (n.roles.includes('Promoter')) return 0;
  if (n.roles.includes('Director')) return 1;
  if (n.roles.includes('Independent director')) return 3;
  return 2;
}

// Deterministic "dossier" layout: readable at a glance and identical on every visit, unlike a force simulation.
function layout(graph, compact) {
  const W = compact ? 380 : 1000;
  const nodeW = compact ? 172 : 230;
  const nodeH = compact ? 50 : 52;
  const gap = compact ? 14 : 14;
  const issuerW = compact ? 240 : 260;
  const issuerH = 62;
  const byId = new Map(graph.nodes.map((n) => [n.id, n]));
  const moneyOf = new Map();
  for (const e of graph.edges) if (e.kind === 'money') moneyOf.set(e.source, (moneyOf.get(e.source) || 0) + e.amount);

  const left = graph.nodes.filter((n) => n.column === 'left').sort((a, b) => rankLeft(a) - rankLeft(b) || (moneyOf.get(b.id) || 0) - (moneyOf.get(a.id) || 0));
  const right = graph.nodes.filter((n) => n.column === 'right').sort((a, b) => (moneyOf.get(b.id) || 0) - (moneyOf.get(a.id) || 0) || a.name.localeCompare(b.name));
  const top = compact ? [] : graph.nodes.filter((n) => n.column === 'top')
    .sort((a, b) => (a.roles[0] === 'Lead manager' ? -1 : 0) - (b.roles[0] === 'Lead manager' ? -1 : 0));

  const pos = new Map();
  const extra = [];
  const place = (list, x, y0, w, max, side) => {
    const shown = list.slice(0, max);
    shown.forEach((n, i) => pos.set(n.id, { x, y: y0 + i * (nodeH + gap), w, h: nodeH, side }));
    if (list.length > max) extra.push({ side, count: list.length - max, x, y: y0 + max * (nodeH + gap), w });
    return y0 + Math.max(shown.length + (list.length > max ? 1 : 0), 1) * (nodeH + gap);
  };

  let issuer;
  let height;
  if (compact) {
    issuer = { x: (W - issuerW) / 2, y: 8, w: issuerW, h: issuerH };
    const y0 = issuer.y + issuerH + 70;
    const lb = place(left, 4, y0, nodeW, MAX_PER_COLUMN, 'left');
    const rb = place(right, W - 4 - nodeW, y0, nodeW, MAX_PER_COLUMN, 'right');
    height = Math.max(lb, rb) + 8;
  } else {
    const topW = 210;
    const shownTop = top.slice(0, MAX_TOP);
    const span = shownTop.length * topW + Math.max(shownTop.length - 1, 0) * 20;
    shownTop.forEach((n, i) => pos.set(n.id, { x: (W - span) / 2 + i * (topW + 20), y: 16, w: topW, h: 48, side: 'top' }));
    if (top.length > MAX_TOP) extra.push({ side: 'top', count: top.length - MAX_TOP, x: (W + span) / 2 + 12, y: 26, w: 90 });
    const y0 = top.length ? 140 : 24;
    const lb = place(left, 24, y0, nodeW, MAX_PER_COLUMN, 'left');
    const rb = place(right, W - 24 - nodeW, y0, nodeW, MAX_PER_COLUMN, 'right');
    const bottom = Math.max(lb, rb, y0 + issuerH + 40);
    issuer = { x: (W - issuerW) / 2, y: Math.max(y0, (y0 + bottom - gap) / 2 - issuerH / 2), w: issuerW, h: issuerH };
    height = bottom + 12;
  }
  pos.set(graph.issuer, { ...issuer, side: 'center' });

  const maxMoney = Math.max(1, ...graph.edges.filter((e) => e.kind === 'money').map((e) => e.amount));
  const edges = [];
  for (const e of graph.edges) {
    const a = pos.get(e.source);
    const b = pos.get(e.target);
    if (!a || !b) continue;
    // On a phone the director-to-company lines cross every box; the lists still show them.
    if (compact && e.kind === 'directorship') continue;
    const anchor = (p, toward) => {
      if (p.side === 'left') return [p.x + p.w, p.y + p.h / 2];
      if (p.side === 'right') return [p.x, p.y + p.h / 2];
      if (p.side === 'top') return [p.x + p.w / 2, p.y + p.h];
      // the issuer: exit from the side facing the other node
      if (compact) return [p.x + p.w / 2 + (toward.side === 'left' ? -40 : 40), p.y + p.h];
      if (toward.side === 'top') return [p.x + p.w / 2, p.y];
      return toward.side === 'left' ? [p.x, p.y + p.h / 2] : [p.x + p.w, p.y + p.h / 2];
    };
    const [x1, y1] = anchor(a, b);
    const [x2, y2] = anchor(b, a);
    let d;
    if (compact && (a.side === 'center' || b.side === 'center')) {
      const other = a.side === 'center' ? b : a;
      const [ox, oy] = other.side === 'left' ? [other.x + other.w / 2, other.y] : [other.x + other.w / 2, other.y];
      const [ix, iy] = a.side === 'center' ? [x1, y1] : [x2, y2];
      d = `M${ix},${iy} C${ix},${iy + 40} ${ox},${oy - 40} ${ox},${oy}`;
    } else if (a.side === 'top' || b.side === 'top') {
      d = `M${x1},${y1} C${x1},${(y1 + y2) / 2} ${x2},${(y1 + y2) / 2} ${x2},${y2}`;
    } else {
      const mx = (x1 + x2) / 2;
      d = `M${x1},${y1} C${mx},${y1} ${mx},${y2} ${x2},${y2}`;
    }
    const money = e.kind === 'money' || e.kind === 'proceeds';
    const width = money ? 1.5 + 6 * Math.sqrt(e.amount / maxMoney) : 1.2;
    const mid = compact && (a.side === 'center' || b.side === 'center')
      ? (() => { const o = a.side === 'center' ? b : a; return [o.x + o.w / 2, o.y - 18]; })()
      : [(x1 + x2) / 2, (y1 + y2) / 2];
    edges.push({ ...e, d, money, width, mid, lateral: e.kind === 'directorship' });
  }
  const moneyLabel = new Map(graph.edges.filter((e) => e.kind === 'money').map((e) => [e.source, e.label]));
  return { W, height, pos, edges, extra, byId, nodeW, moneyLabel };
}

export default function MapView({ graph, flaggedIds, selected, onSelect }) {
  const compact = useNarrow();
  const [hover, setHover] = useState(null);
  const L = useMemo(() => layout(graph, compact), [graph, compact]);

  const focus = hover ?? (selected?.type === 'node' ? selected.id : null);
  const focusEdge = selected?.type === 'edge' ? selected.id : null;
  const linked = useMemo(() => {
    if (focus == null) return null;
    const s = new Set([focus]);
    for (const e of L.edges) if (e.source === focus || e.target === focus) { s.add(e.source); s.add(e.target); }
    return s;
  }, [focus, L.edges]);

  const charsName = compact ? 21 : 28;
  const nodeEls = [];
  for (const [id, p] of L.pos) {
    const n = L.byId.get(id);
    if (!n) continue;
    const isIssuer = p.side === 'center';
    const person = n.kind === 'person';
    const adviser = p.side === 'top';
    const flagged = flaggedIds.has(id);
    const isSel = selected?.type === 'node' && selected.id === id;
    const dim = linked && !linked.has(id);
    const fill = isIssuer ? 'var(--ink)' : person ? 'var(--blue-soft)' : 'var(--surface)';
    const stroke = isIssuer ? 'var(--ink)' : flagged ? 'var(--accent)' : person ? 'var(--blue)' : adviser ? 'var(--muted)' : 'var(--ink)';
    // On phones there is no room for amount labels on the lines, so the amount joins the role line.
    const amount = compact ? L.moneyLabel.get(id) : null;
    const role = isIssuer ? 'Company going public'
      : [amount, topRole(n.roles) || (person ? 'Person' : 'Company')].filter(Boolean).join(' · ');
    nodeEls.push(
      <g key={id} className={`node${dim ? ' dim' : ''}`} tabIndex={0} role="button"
        aria-label={`${n.name}, ${n.roles.join(', ') || role}`} aria-pressed={isSel}
        onClick={() => onSelect({ type: 'node', id })}
        onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); onSelect({ type: 'node', id }); } }}
        onMouseEnter={() => setHover(id)} onMouseLeave={() => setHover(null)}
        onFocus={() => setHover(id)} onBlur={() => setHover(null)}>
        <title>{n.name}</title>
        <rect x={p.x} y={p.y} width={p.w} height={p.h} rx={person ? p.h / 2 : 7} fill={fill} stroke={stroke}
          strokeWidth={isSel ? 3 : flagged ? 2 : 1.4} strokeDasharray={adviser ? '5 4' : undefined} />
        <text x={p.x + p.w / 2} y={p.y + p.h / 2 - 3} textAnchor="middle" fontSize={isIssuer ? 15 : 13.5} fontWeight="600"
          fill={isIssuer ? 'var(--bg)' : 'var(--ink)'}>{clip(isIssuer ? shortName(n.name) : n.name, isIssuer ? 30 : charsName)}</text>
        <text x={p.x + p.w / 2} y={p.y + p.h / 2 + 14} textAnchor="middle" fontSize="11.5"
          fill={isIssuer ? 'var(--bg)' : 'var(--muted)'} opacity={isIssuer ? 0.8 : 1}>{clip(role, charsName + 4)}</text>
      </g>,
    );
  }

  return (
    <div className="map">
      <svg viewBox={`0 0 ${L.W} ${L.height}`} role="group" aria-label="Map of people, companies and advisers connected to this filing">
        <g>
          {L.edges.map((e) => {
            const on = focusEdge === e.id || (focus != null && (e.source === focus || e.target === focus));
            const dim = (focus != null || focusEdge) && !on;
            return (
              <g key={e.id} className={dim ? 'dim' : ''}>
                <path d={e.d} fill="none" stroke="transparent" strokeWidth="14" style={{ cursor: 'pointer' }}
                  onClick={() => onSelect({ type: 'edge', id: e.id })} />
                <path d={e.d} fill="none" stroke={e.money ? 'var(--accent)' : 'var(--edge)'} strokeWidth={on && !e.money ? 2 : e.width}
                  strokeDasharray={e.lateral || e.kind === 'intermediary' ? '4 4' : undefined} opacity={e.lateral && !on ? 0.5 : 1}
                  style={{ pointerEvents: 'none' }} />
              </g>
            );
          })}
        </g>
        {nodeEls}
        {!compact && L.edges.filter((e) => e.money).map((e) => {
          const label = e.label;
          const w = label.length * 7.4 + 14;
          const on = focusEdge === e.id;
          const dim = (focus != null && e.source !== focus && e.target !== focus) || (focusEdge && !on);
          return (
            <g key={`l-${e.id}`} className={dim ? 'dim' : ''} style={{ cursor: 'pointer' }} onClick={() => onSelect({ type: 'edge', id: e.id })}>
              <rect x={e.mid[0] - w / 2} y={e.mid[1] - 11} width={w} height="22" rx="4" fill={on ? 'var(--accent)' : 'var(--surface)'}
                stroke="var(--accent)" strokeWidth="1" />
              <text x={e.mid[0]} y={e.mid[1] + 4.5} textAnchor="middle" fontSize="12" fontWeight="600"
                fill={on ? '#fff' : 'var(--accent)'}>{label}</text>
            </g>
          );
        })}
        {L.extra.map((x) => (
          <text key={x.side} x={x.x + (x.side === 'top' ? 0 : x.w / 2)} y={x.y + 20} textAnchor={x.side === 'top' ? 'start' : 'middle'}
            fontSize="12.5" fill="var(--muted)">+{x.count} more in the lists below</text>
        ))}
      </svg>
    </div>
  );
}
