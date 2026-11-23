import {activity, field, fileIndex, heading, note, recordHeader, select, stamp} from '../components.js';
import {reviewStates} from '../constants.js';
import {dateTime, escape as e, percent} from '../format.js';

function reviewForm(record, staff) {
  const review = record.review;
  if (review.status === 'awaiting_witness' && staff.role === 'operator') {
    return `<form data-action="witness">${note('开箱观察', 'note', '记录内托、器物和外箱的实见情况')}<div class="form-actions"><button>签署见证</button></div></form>`;
  }
  if (review.status === 'awaiting_supervisor' && staff.role === 'supervisor') {
    return `<form data-action="decision">${select('主管决定', 'verdict', {downgrade: '改判低风险，转封签抽检', hold: '保留高风险，暂缓运输'})}
      ${note('决定理由', 'reason', '记录现场证据及决定依据')}<div class="form-actions"><button>签署复核</button></div></form>`;
  }
  if (review.status === 'sampling' && staff.role === 'operator') {
    return `<form data-action="sample">${field('实见封签号', 'seal_code', {placeholder: '请核对木箱封签后录入'})}<div class="form-actions"><button>提交抽检</button></div></form>`;
  }
  if (review.status === 'held' && staff.role === 'supervisor') {
    return `<form data-action="reopen">${note('重开理由', 'reason', '记录整改完成的依据')}<div class="form-actions"><button>重开复核</button></div></form>`;
  }
  return '';
}

export function reviewPage({loans, record, staff}) {
  const review = record?.review;
  return `${heading('开箱复核', '确认开箱见证、主管签字及封签抽检')}
    <div class="workbench">${fileIndex(loans, record, 'review')}${record ? `<article class="dossier">${recordHeader(record)}
      ${review ? `<div class="review-strip"><span class="mono">复核单 / ${review.case_id}</span>${stamp(review.status, reviewStates)}
        <span>模型风险 ${percent(record.triage.probability)}</span></div>
        <div class="review-sheet"><section><ol class="signoffs">
          <li><div><h3>开箱见证</h3><p>${e(review.witness_note ?? '等待经办开箱并记录器物状态。')}</p>
          ${review.witness_by ? `<small>${e(review.witness_by)} · ${dateTime(review.witnessed_at)}</small>` : ''}</div></li>
          <li><div><h3>主管签字</h3><p>${e(review.decision_reason ?? '见证签署后，由主管决定改判或暂缓。')}</p>
          ${review.supervisor_by ? `<small>${e(review.supervisor_by)} · ${dateTime(review.decided_at)}</small>` : ''}</div></li>
          <li><div><h3>封签抽检</h3><p>${review.sample_seal ? `最近一次实见封签 ${e(review.sample_seal)}` : '主管改判后，必须实地核对封签。'}</p>
          ${review.sample_by ? `<small>${e(review.sample_by)} · ${dateTime(review.sampled_at)}</small>` : ''}</div></li></ol>
          ${reviewForm(record, staff)}</section><aside class="audit-column"><h3>复核留痕</h3>${activity(record.history)}</aside></div>` :
      '<p class="empty">此批没有开箱复核单。风险分流判定为高风险时会自动生成。</p>'}</article>` : ''}</div>`;
}
