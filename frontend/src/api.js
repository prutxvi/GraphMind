const BASE = import.meta.env.VITE_API_URL ?? '';

// FastAPI errors arrive as {detail: "..."}; surface that text instead of a generic failure.
export async function api(path, options) {
  const res = await fetch(`${BASE}${path}`, options);
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? data.detail : `Request failed (${res.status})`);
  return data;
}

export const pdfUrl = (filingId) => `${BASE}/api/filings/${encodeURIComponent(filingId)}/pdf`;

export const ROLE_ORDER = ['Promoter', 'Director', 'Independent director', 'Related party'];

export const METRIC_LABEL = {
  revenue_from_operations: 'Revenue from operations',
  profit_after_tax: 'Profit after tax',
  net_cash_from_operating_activities: 'Cash from operations',
  total_borrowings: 'Total borrowings',
  net_worth: 'Net worth',
};
