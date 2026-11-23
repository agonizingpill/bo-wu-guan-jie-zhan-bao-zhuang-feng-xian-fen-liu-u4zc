import {activity, field, fileIndex, heading, recordHeader, select} from '../components.js';
import {materials, packings, routes} from '../constants.js';
import {escape as e} from '../format.js';

function intake() {
  return `<dialog id="loan-intake"><form data-action="intake"><h2>登记借展</h2>
    <div class="form-grid">${field('借展单号', 'accession', {placeholder: 'BR-2611-030'})}
    ${field('借品名称', 'object_name')}${field('出借机构', 'lender')}${field('接收展厅', 'gallery')}
    ${field('到馆期限（上海时间）', 'must_arrive', {type: 'datetime-local'})}</div>
    <div class="form-actions"><button type="button" class="subtle" data-close-dialog>取消</button><button>登记借展</button></div></form></dialog>`;
}

function inspection(record, editable) {
  const crate = record.crate ?? {};
  const frozen = record.triage && record.triage.status !== 'failed';
  if (!editable) {
    if (!record.crate) return '<p class="empty">等待经办完成包装检查。</p>';
    return `<dl class="facts"><dt>箱号</dt><dd>${e(crate.crate_code)}</dd><dt>封签</dt><dd>${e(crate.seal_code ?? '缺失')}</dd>
      <dt>材质</dt><dd>${e(materials[crate.material])}</dd><dt>包装</dt><dd>${e(packings[crate.packing])}</dd>
      <dt>路线</dt><dd>${e(routes[crate.route_type])}</dd><dt>最高湿度</dt><dd>${crate.max_rh}% RH</dd><dt>转运次数</dt><dd>${crate.transfers}</dd></dl>`;
  }
  return `<form data-action="crate"><div class="form-grid">
    ${field('箱号', 'crate_code', {value: crate.crate_code, readonly: frozen, placeholder: 'BX-030'})}
    ${field('封签编号', 'seal_code', {value: crate.seal_code, required: false, readonly: record.review?.status === 'cleared', placeholder: '未见封签可暂留空'})}
    ${select('器物材质', 'material', materials, crate.material, frozen)}
    ${select('包装结构', 'packing', packings, crate.packing, frozen)}
    ${select('路线类别', 'route_type', routes, crate.route_type, frozen)}
    ${field('最高相对湿度（% RH）', 'max_rh', {type: 'number', value: crate.max_rh ?? 55, min: 0, max: 100, readonly: frozen})}
    ${field('转运次数', 'transfers', {type: 'number', value: crate.transfers ?? 0, min: 0, max: 8, readonly: frozen})}</div>
    <div class="form-actions"><span>${frozen ? '分流输入已归档。' : '包装检查完成后可提交风险分流。'}</span><button>保存包装检查</button></div></form>`;
}

export function archivePage({loans, record, staff}) {
  const operator = staff.role === 'operator';
  return `${heading('借展档案', '核对借展单与木箱记录', operator ? '<button data-open-dialog="loan-intake">登记借展</button>' : '')}
    <div class="workbench">${fileIndex(loans, record, 'archive')}
    ${record ? `<article class="dossier">${recordHeader(record)}
      ${record.crate && !record.crate.seal_code ? '<p class="alert">封签缺失。补录之前，派车会被拦截。</p>' : ''}
      <div class="archive-sheet"><section><h3>包装检查</h3>${inspection(record, operator && record.status !== 'dispatched')}</section>
        <aside class="audit-column"><h3>档案记录</h3>${activity(record.history)}</aside></div></article>` : ''}</div>
    ${operator ? intake() : ''}`;
}
