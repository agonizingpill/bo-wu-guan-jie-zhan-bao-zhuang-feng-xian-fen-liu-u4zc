export const escape = (value) => String(value ?? '').replace(/[&<>"']/g, (part) => ({
  '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
})[part]);

const localFormat = new Intl.DateTimeFormat('sv-SE', {
  timeZone: 'Asia/Shanghai', year: 'numeric', month: '2-digit', day: '2-digit',
  hour: '2-digit', minute: '2-digit', hourCycle: 'h23',
});
export const dateTime = (value) => value ? localFormat.format(new Date(value)) : '—';
export const toLocal = (value) => value ? dateTime(value).replace(' ', 'T') : '';
export const fromLocal = (value) => `${value}:00+08:00`;
export const clock = (value) => dateTime(value).slice(11);
export const percent = (value) => `${(value * 100).toFixed(1)}%`;
