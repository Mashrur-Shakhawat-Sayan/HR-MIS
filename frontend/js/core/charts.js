/** Lightweight SVG charts (no external libraries). Colours come from CSS variables, so they follow the theme. */
import { esc } from './ui.js';

export const PALETTE = ['var(--brand)', 'var(--attn)', 'var(--info)', 'var(--plum)', 'var(--teal)', 'var(--danger)', 'var(--muted)'];

/**
 * Vertical columns. data: [{label, value}]. The most recent (last) column is solid, earlier ones lighter.
 * opts: suffix, max, target (draws a dashed reference line, e.g. 95 for an attendance goal)
 */
export function columns(data, { suffix = '', max, target } = {}) {
  if (!data.length) return '<div class="empty"><b>No data yet</b></div>';
  const W = 480, H = 150, top = 18, bw = W / data.length;
  const peak = max || Math.max(1, ...data.map((d) => d.value));
  const y = (v) => top + H - (v / peak) * H;
  const cols = data.map((d, i) => {
    const h = Math.max(2, (d.value / peak) * H);
    const last = i === data.length - 1;
    return `<g><rect x="${i * bw + bw * 0.24}" y="${top + H - h}" width="${bw * 0.52}" height="${h}" rx="5" style="fill:var(--brand);opacity:${last ? 1 : 0.38}"><title>${esc(d.label)}: ${d.value}${suffix}</title></rect>
      <text x="${i * bw + bw / 2}" y="${top + H - h - 6}" text-anchor="middle" class="cv">${Math.round(d.value)}${suffix}</text>
      <text x="${i * bw + bw / 2}" y="${top + H + 20}" text-anchor="middle" class="cl">${esc(d.label)}</text></g>`;
  }).join('');
  const gutter = target ? 56 : 0; // room on the right for the goal label, clear of the bars
  const ref = target ? `<line x1="0" x2="${W + 6}" y1="${y(target)}" y2="${y(target)}" class="grid"/><text x="${W + 10}" y="${y(target) + 4}" class="cl">${target}${suffix} goal</text>` : '';
  return `<svg viewBox="0 0 ${W + gutter} ${top + H + 28}" class="chart" role="img" aria-label="Column chart">${ref}${cols}</svg>`;
}

/** Horizontal bars. data: [{label, value}] */
export function bars(data) {
  if (!data.length) return '<div class="empty"><b>No data yet</b></div>';
  const max = Math.max(1, ...data.map((d) => d.value));
  return data.map((d) => `<div class="hb"><span title="${esc(d.label)}">${esc(d.label)}</span><div class="bar"><i style="width:${(d.value / max) * 100}%"></i></div><b>${d.value}</b></div>`).join('');
}

/** Donut with legend. data: [{label, value}] */
export function donut(data) {
  const total = data.reduce((s, d) => s + d.value, 0) || 1;
  const C = 2 * Math.PI * 40;
  let off = 0;
  const arcs = data.map((d, i) => {
    const len = (d.value / total) * C;
    const s = `<circle cx="50" cy="50" r="40" fill="none" style="stroke:${PALETTE[i % PALETTE.length]}" stroke-width="14" stroke-dasharray="${Math.max(0, len - 1.5)} ${C - len + 1.5}" stroke-dashoffset="${-off}"><title>${esc(d.label)}: ${d.value}</title></circle>`;
    off += len;
    return s;
  }).join('');
  return `<div style="display:flex;align-items:center;gap:22px;flex-wrap:wrap"><svg viewBox="0 0 100 100" width="116" height="116" style="transform:rotate(-90deg)" role="img" aria-label="Donut chart">${arcs}</svg>
    <div class="legend">${data.map((d, i) => `<div><i style="background:${PALETTE[i % PALETTE.length]}"></i>${esc(d.label)} <b>${d.value}</b> <span class="muted">${Math.round((d.value / total) * 100)}%</span></div>`).join('')}</div></div>`;
}
