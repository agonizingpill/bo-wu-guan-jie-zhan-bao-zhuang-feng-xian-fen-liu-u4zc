import {field, fileIndex, heading, recordHeader, stamp} from '../components.js';
import {windowStates} from '../constants.js';
import {clock, dateTime, escape as e, toLocal} from '../format.js';

function board(windows, day) {
  const midnight = Date.parse(`${day}T00:00:00+08:00`);
  const entries = windows.filter((item) => Date.parse(item.begins_at) < midnight + 86400000 && Date.parse(item.ends_at) > midnight);
  if (!entries.length) return '<p class="empty">当天没有布置或运输窗口。可切换日期查看其他安排。</p>';
  const ranges = entries.map((item) => [Math.max(0, (Date.parse(item.begins_at) - midnight) / 60000),
    Math.min(1440, (Date.parse(item.ends_at) - midnight) / 60000)]);
  const start = Math.floor(Math.min(660, ...ranges.map(([from]) => from)) / 60) * 60;
  const end = Math.ceil(Math.max(1020, ...ranges.map(([, till]) => till)) / 60) * 60;
  const step = Math.ceil((end - start) / 420) * 60;
  const ticks = Array.from({length: Math.floor((end - start) / step) + 1}, (_, i) => start + i * step);
  return `<div class="board-grid"><div class="axis">${ticks.map((tick) => `<span style="left:${100 * (tick - start) / (end - start)}%">${tick / 60}:00</span>`).join('')}</div>
    ${entries.map((item, index) => {
      const [from, till] = ranges[index];
      return `<div class="board-row"><div><strong>${e(item.gallery)}</strong><small>${e(item.label)}</small></div>
        <div class="track"><span class="span" data-state="${item.status}" title="${e(windowStates[item.status])} ${clock(item.begins_at)}–${clock(item.ends_at)}"
          style="left:${100 * (from - start) / (end - start)}%;width:${100 * (till - from) / (end - start)}%"></span></div>
        <span class="hours mono">${clock(item.begins_at)}–${clock(item.ends_at)}</span></div>`;
    }).join('')}</div><p class="legend"><span>展厅布置</span><span>确认／已派车</span><span>有冲突</span></p>`;
}

function setupForm() {
  return `<dialog id="setup"><form data-action="setup"><h2>登记展厅布置</h2><div class="form-grid">
    ${field('展厅', 'gallery')}${field('布置作业', 'label')}${field('开始', 'begins_at', {type: 'datetime-local'})}
    ${field('结束', 'ends_at', {type: 'datetime-local'})}</div>
    <div class="form-actions"><button type="button" class="subtle" data-close-dialog>取消</button><button>保存布置</button></div></form></dialog>`;
}

export function transitPage({loans, record, staff, schedule, scheduleDay}) {
  const supervisor = staff.role === 'supervisor';
  const canReserve = staff.role === 'operator' && record?.status !== 'dispatched';
  const current = record?.transit;
  const day = scheduleDay || dateTime(current?.begins_at ?? schedule[0]?.begins_at).slice(0, 10).replace('—', '');
  return `${heading('运输窗口', '借品装卸与展厅布置的时间台账', supervisor ? '<button data-open-dialog="setup">登记展厅布置</button>' : '')}
    <div class="workbench">${fileIndex(loans, record, 'transit')}
      <article class="dossier">${record ? recordHeader(record) : ''}
        <section class="timeboard"><div class="section-line"><h3>展厅与车辆占用</h3><label>查看日期 <input type="date" id="schedule-day" value="${e(day)}"></label></div>
        ${board(schedule, day)}</section>
        ${record ? `<section class="dispatch-panel"><h3>本批运输单 ${current ? stamp(current.status, windowStates) : ''}</h3>
          ${current ? `<p>${e(current.vehicle)} · ${dateTime(current.begins_at)} 至 ${clock(current.ends_at)}</p>` : '<p class="empty">尚未提交窗口。</p>'}
          ${record.dispatch_issue ? `<p class="${record.status === 'dispatched' ? 'muted' : 'alert'}">${e(record.dispatch_issue)}</p>` : '<p class="success-line">封签、窗口与风险放行均已确认。</p>'}
          ${canReserve ? `<form data-action="transit"><div class="form-grid transit-fields">
            ${field('车辆标识', 'vehicle', {value: current?.vehicle, placeholder: '沪A·藏照01'})}
            ${field('开始（上海时间）', 'begins_at', {type: 'datetime-local', value: toLocal(current?.begins_at)})}
            ${field('结束（上海时间）', 'ends_at', {type: 'datetime-local', value: toLocal(current?.ends_at)})}</div>
            <div class="form-actions"><button>${current ? '改排窗口' : '登记窗口'}</button>
            <button type="button" class="subtle" data-dispatch>确认派车</button></div></form>` : ''}</section>` : ''}</article></div>
    ${supervisor ? setupForm() : ''}`;
}
