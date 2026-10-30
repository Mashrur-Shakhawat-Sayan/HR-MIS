/** Holiday calendar (everyone can view; holidays.manage to edit). */
import { crudView, mountCrud } from '../core/crud.js';
import { badge, esc, fmtDate, parseDate, today } from '../core/ui.js';

export async function render(main, ctx) {
  await mountCrud(main, crudView({
    id: 'holidays', endpoint: '/api/holidays', title: 'Holiday calendar', single: 'Holiday', canManage: ctx.can('holidays.manage'),
    fields: [{ k: 'date', l: 'Date', t: 'date', req: 1 }, { k: 'name', l: 'Holiday', req: 1 }, { k: 'type', l: 'Type', t: 'select', o: ['National', 'Religious', 'Company', 'Optional'], req: 1, d: 'National' }],
    cols: [{ l: 'Date', fmt: (h) => `<b class="nowrap">${fmtDate(h.date)}</b>` }, { l: 'Day', fmt: (h) => parseDate(h.date).toLocaleDateString('en-GB', { weekday: 'long' }) },
      { l: 'Holiday', fmt: (h) => esc(h.name) }, { l: 'Type', fmt: (h) => badge(h.type) }, { l: '', fmt: (h) => (h.date < today() ? '<span class="muted">Past</span>' : badge('Scheduled')) }],
  }), '', '<p class="note">Lunar holidays (Eid, Ashura, Durga Puja, Buddha Purnima …) are marked “tentative”. Confirm the dates with the government gazette each year. Weekly holidays are set in Settings, under Working time.</p>');
}
