import {auditActions, loanStates} from './constants.js';
import {dateTime, escape as e} from './format.js';

export function stamp(code, labels = loanStates) {
  return `<span class="stamp" data-state="${e(code)}">${e(labels[code] ?? code)}</span>`;
}

export function heading(title, subtitle, extra = '') {
  return `<header class="page-heading"><div><h1>${e(title)}</h1><p>${e(subtitle)}</p></div>${extra}</header>`;
}

export function recordHeader(record) {
  return `<header class="record-header"><span class="mono accession">${e(record.accession)}</span>
    <div class="record-title"><h2>${e(record.object_name)}</h2>${stamp(record.status)}</div>
    <p>${e(record.lender)} <span aria-hidden="true">／</span> ${e(record.gallery)}
      <span aria-hidden="true">／</span> ${dateTime(record.must_arrive)} 前到馆</p></header>`;
}

export function fileIndex(loans, record, section) {
  return `<aside class="file-index" aria-label="借展批次"><div class="index-head"><h2>借展批次</h2><span class="mono">${loans.length} 件</span></div>
    ${loans.length ? loans.map((loan) => `<a class="index-entry${loan.id === record?.id ? ' selected' : ''}"
      href="#${section}/${loan.id}" ${loan.id === record?.id ? 'aria-current="true"' : ''}>
      <div><span class="mono">${e(loan.accession)}</span>${stamp(loan.status)}</div>
      <strong>${e(loan.object_name)}</strong><small>${e(loan.gallery)} · ${dateTime(loan.must_arrive).slice(11)} 前</small></a>`).join('') :
      `<p class="empty">还没有借展批次。经办可在借展档案登记第一件借品。</p>`}</aside>`;
}

export function activity(history) {
  if (!history?.length) return '<p class="empty">档案变更会自动记录在这里。</p>';
  return `<ol class="activity">${history.slice(0, 9).map((event) => {
    const reason = event.details.reason ?? event.details.observation ?? (event.action === 'sample_mismatch'
      ? `实见 ${event.details.observed}，登记 ${event.details.expected ?? '缺失'}` : '');
    return `<li><div><strong>${e(auditActions[event.action] ?? event.action)}</strong>
      ${reason ? `<p>${e(reason)}</p>` : ''}</div>
      <small>${e(event.actor)}<br><span class="mono">${dateTime(event.recorded_at)}</span></small></li>`;
  }).join('')}</ol>`;
}

export function field(label, name, {type = 'text', value = '', min, max, required = true, placeholder = '', readonly = false} = {}) {
  return `<label>${e(label)}<input name="${e(name)}" type="${type}" value="${e(value)}" placeholder="${e(placeholder)}"
    ${min !== undefined ? `min="${min}"` : ''} ${max !== undefined ? `max="${max}"` : ''}
    ${required ? 'required' : ''} ${readonly ? 'readonly' : ''}></label>`;
}

export function select(label, name, options, selected, locked = false) {
  return `<label>${e(label)}<select name="${e(name)}" ${locked ? 'disabled' : ''}>${Object.entries(options).map(([value, text]) =>
    `<option value="${e(value)}" ${value === selected ? 'selected' : ''}>${e(text)}</option>`).join('')}</select></label>`;
}

export function note(label, name, placeholder) {
  return `<label>${e(label)}<textarea name="${name}" minlength="8" maxlength="600" placeholder="${e(placeholder)}" required></textarea></label>`;
}
