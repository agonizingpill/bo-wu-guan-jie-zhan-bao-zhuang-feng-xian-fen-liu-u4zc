import {field, fileIndex, heading, note, recordHeader, select, stamp} from '../components.js';
import {convoyStates, windowStates} from '../constants.js';
import {clock, dateTime, escape as e, percent, toLocal} from '../format.js';

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

function createDialog() {
  return `<dialog id="convoy-create"><form data-action="convoy-create"><h2>新编车次</h2><div class="form-grid">
    ${field('车次名称', 'label', {placeholder: '临展首日专车'})}
    ${field('车辆标识', 'vehicle', {placeholder: '沪A·藏06'})}
    ${field('开始（上海时间）', 'begins_at', {type: 'datetime-local'})}
    ${field('结束（上海时间）', 'ends_at', {type: 'datetime-local'})}</div>
    <p class="convoy-note">车次内借品共用这一趟车的运输窗口，创建后再逐件编入。</p>
    <div class="form-actions"><button type="button" class="subtle" data-close-dialog>取消</button><button>建立车次</button></div></form></dialog>`;
}

function signDialog(convoy) {
  return `<dialog id="convoy-sign-${convoy.id}"><form data-action="convoy-sign" data-convoy="${convoy.id}">
    <h2>整车签字 · ${e(convoy.label)}</h2>
    <p class="convoy-note">同车合计风险 ${percent(convoy.combined_risk)}，达到开箱线 ${percent(convoy.risk_threshold)}。签字锁定当前名单（v${convoy.roster_version}），增减借品将撤销签字。</p>
    ${note('签字理由', 'reason', '记录同车风险评估与放行依据')}
    <div class="form-actions"><button type="button" class="subtle" data-close-dialog>取消</button><button>签署整车放行</button></div></form></dialog>`;
}

function memberRow(convoy, member, canEdit) {
  return `<li><div><span class="mono">${e(member.accession)}</span> ${e(member.object_name)} ${stamp(member.loan_status)}
    <small>${member.scored ? `单箱概率 ${percent(member.probability)}` : '尚未出分'}${member.seal_code ? '' : ' · 缺少封签'}</small></div>
    ${canEdit ? `<form data-action="convoy-remove" data-convoy="${convoy.id}"><input type="hidden" name="loan_id" value="${member.loan_id}"><button class="subtle">移出</button></form>` : ''}</li>`;
}

function convoyCard(convoy, loans, staff) {
  const open = convoy.status === 'open';
  const canEdit = staff.role === 'operator' && open;
  const members = convoy.members;
  const candidates = loans.filter((loan) => !loan.convoy && loan.status !== 'dispatched'
    && !members.some((member) => member.loan_id === loan.id));
  const order = convoy.dispatch_order;
  return `<article class="convoy-card" data-state="${convoy.status}">
    <header><strong>${e(convoy.label)}</strong> ${stamp(convoy.status, convoyStates)}
      <span class="mono">${e(convoy.vehicle)}</span>
      <span>${dateTime(convoy.begins_at)} – ${clock(convoy.ends_at)}</span>
      <small>名单 v${convoy.roster_version}</small></header>
    ${convoy.combined_risk === null ? '<p class="empty">尚未按当前名单评估同车合计风险。</p>' : `
      <div class="convoy-risk"><div class="probability">${percent(convoy.combined_risk)}<small>同车合计风险 · 封顶 100%</small></div>
      <div class="risk-bar" role="img" aria-label="同车合计风险 ${percent(convoy.combined_risk)}，开箱线 ${percent(convoy.risk_threshold)}">
        <i style="width:${convoy.combined_risk * 100}%"></i><b style="left:${convoy.risk_threshold * 100}%"></b></div>
      <div class="risk-labels"><span>0%</span><span>开箱线 ${percent(convoy.risk_threshold)}</span><span>100%</span></div>
      <p>${e(convoy.assessed_by)} 按名单 v${convoy.roster_version} 评估 · ${dateTime(convoy.assessed_at)}</p></div>`}
    <ul class="convoy-members">${members.map((member) => memberRow(convoy, member, canEdit)).join('')}</ul>
    ${members.length ? '' : '<p class="empty">还没有编入借品。</p>'}
    ${canEdit && candidates.length ? `<form data-action="convoy-add" data-convoy="${convoy.id}" class="convoy-join">
      ${select('编入借品', 'loan_id', Object.fromEntries(candidates.map((loan) => [loan.id, `${loan.accession} · ${loan.object_name}`])))}
      <div class="form-actions"><button>编入车次</button></div></form>` : ''}
    ${convoy.signature_valid ? `<p class="success-line">主管 ${e(convoy.signed_by)} 已签字（名单 v${convoy.signed_roster_version}）· ${dateTime(convoy.signed_at)}<small>${e(convoy.signed_reason)}</small></p>` : ''}
    ${open && convoy.signature_required && !convoy.signature_valid ? '<p class="alert">同车合计风险达到开箱线，主管签字后方可派车。</p>' : ''}
    ${open ? (convoy.hold_reasons.length ? `<div class="hold-reasons"><h4>拦车原因</h4><ul>${convoy.hold_reasons.map((reason) => `<li>${e(reason)}</li>`).join('')}</ul></div>`
      : '<p class="success-line">当前无拦车原因，可派车。</p>') : ''}
    ${order ? `<div class="dispatch-order"><h4>车单 #${order.id} · 已签发</h4>
      <p>${e(order.issued_by)} · ${dateTime(order.issued_at)}${order.signed_by ? ` · 主管 ${e(order.signed_by)}` : ''} · 合计风险 ${percent(order.combined_risk)}</p>
      <p>锁定名单：${order.roster.map((item) => e(item.accession)).join('、')}</p></div>` : ''}
    ${canEdit ? `<div class="form-actions convoy-actions">
      <form data-action="convoy-assess" data-convoy="${convoy.id}"><button class="subtle">评估合计风险</button></form>
      <button data-convoy-dispatch="${convoy.id}">确认整车派车</button></div>` : ''}
    ${staff.role === 'supervisor' && open && convoy.signature_required && !convoy.signature_valid
      ? `<div class="form-actions convoy-actions"><button data-open-dialog="convoy-sign-${convoy.id}">整车签字</button></div>` : ''}
  </article>`;
}

function convoyBoard(convoys, loans, staff) {
  const operator = staff.role === 'operator';
  const signable = staff.role === 'supervisor'
    ? convoys.filter((convoy) => convoy.status === 'open' && convoy.signature_required && !convoy.signature_valid) : [];
  return `<section class="convoy-board"><div class="section-line"><h3>同车编组</h3>
    ${operator ? '<button data-open-dialog="convoy-create">新编车次</button>' : ''}</div>
    <p class="convoy-note">同车多箱合并评估：各箱风险概率相加、封顶 100%，达到开箱线需主管签字。增减借品会撤销签字，旧名单的评估记录不得抵用。</p>
    ${convoys.length ? convoys.map((convoy) => convoyCard(convoy, loans, staff)).join('')
      : '<p class="empty">还没有车次。经办可新编车次，让多件借品共用一趟车的运输窗口。</p>'}
    ${operator ? createDialog() : ''}${signable.map(signDialog).join('')}</section>`;
}

export function transitPage({loans, record, staff, schedule, scheduleDay, convoys}) {
  const supervisor = staff.role === 'supervisor';
  const canReserve = staff.role === 'operator' && record?.status !== 'dispatched' && !record?.convoy;
  const current = record?.transit;
  const day = scheduleDay || dateTime(current?.begins_at ?? schedule[0]?.begins_at).slice(0, 10).replace('—', '');
  return `${heading('运输窗口', '借品装卸与展厅布置的时间台账', supervisor ? '<button data-open-dialog="setup">登记展厅布置</button>' : '')}
    <div class="workbench">${fileIndex(loans, record, 'transit')}
      <article class="dossier">${record ? recordHeader(record) : ''}
        <section class="timeboard"><div class="section-line"><h3>展厅与车辆占用</h3><label>查看日期 <input type="date" id="schedule-day" value="${e(day)}"></label></div>
        ${board(schedule, day)}</section>
        ${convoyBoard(convoys ?? [], loans, staff)}
        ${record ? `<section class="dispatch-panel"><h3>本批运输单 ${current ? stamp(current.status, windowStates) : ''}</h3>
          ${record.convoy ? `<p class="alert">${e(record.dispatch_issue)}</p>` : ''}
          ${current ? `<p>${e(current.vehicle)} · ${dateTime(current.begins_at)} 至 ${clock(current.ends_at)}</p>` : '<p class="empty">尚未提交窗口。</p>'}
          ${!record.convoy ? (record.dispatch_issue ? `<p class="${record.status === 'dispatched' ? 'muted' : 'alert'}">${e(record.dispatch_issue)}</p>` : '<p class="success-line">封签、窗口与风险放行均已确认。</p>') : ''}
          ${canReserve ? `<form data-action="transit"><div class="form-grid transit-fields">
            ${field('车辆标识', 'vehicle', {value: current?.vehicle, placeholder: '沪A·藏照01'})}
            ${field('开始（上海时间）', 'begins_at', {type: 'datetime-local', value: toLocal(current?.begins_at)})}
            ${field('结束（上海时间）', 'ends_at', {type: 'datetime-local', value: toLocal(current?.ends_at)})}</div>
            <div class="form-actions"><button>${current ? '改排窗口' : '登记窗口'}</button>
            <button type="button" class="subtle" data-dispatch>确认派车</button></div></form>` : ''}</section>` : ''}</article></div>
    ${supervisor ? setupForm() : ''}`;
}
