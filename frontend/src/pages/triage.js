import {fileIndex, heading, recordHeader, stamp} from '../components.js';
import {materials, packings, routes} from '../constants.js';
import {dateTime, escape as e, percent} from '../format.js';

function riskResult(result) {
  const evidence = result.evidence;
  const snapshot = result.input_snapshot;
  const p = result.probability;
  const threshold = evidence.risk_threshold;
  return `<div class="scoring-sheet"><section class="scoring-slip">
    <h3>模型判定 ${stamp(result.risk, {low: '低风险', high: '高风险'})}</h3>
    <div class="probability">${percent(p)}<small>模型风险概率</small></div>
    <div class="risk-bar" role="img" aria-label="风险 ${percent(p)}，阈值 ${percent(threshold)}"><i style="width:${p * 100}%"></i>
      <b style="left:${threshold * 100}%"></b></div><div class="risk-labels"><span>0%</span><span>复核阈值 ${percent(threshold)}</span><span>100%</span></div>
    <p>${result.risk === 'high' ? '已生成开箱复核单。' : '风险环节已放行。派车仍需确认封签与窗口。'}</p></section>
    <section class="feature-sheet"><h3>包装输入快照</h3><dl class="facts">
      <dt>器物材质</dt><dd>${e(materials[snapshot.material])}</dd><dt>包装结构</dt><dd>${e(packings[snapshot.packing])}</dd>
      <dt>路线类别</dt><dd>${e(routes[snapshot.route_type])}</dd><dt>最高相对湿度</dt><dd>${snapshot.max_rh}% RH</dd>
      <dt>转运次数</dt><dd>${snapshot.transfers} 次</dd></dl></section></div>
    <section class="evidence"><div><h3>模型留档</h3><p>${e(evidence.model_version)} · ${dateTime(result.computed_at)} · 合成样本</p>
      <dl class="facts"><dt>训练 / 留出</dt><dd>${evidence.train_count} / ${evidence.test_count}</dd><dt>ROC AUC</dt><dd>${evidence.roc_auc.toFixed(3)}</dd>
      <dt>Brier 分数</dt><dd>${evidence.brier_score.toFixed(3)}</dd><dt>随机种子</dt><dd>${evidence.random_seed}</dd></dl></div>
      <details><summary>查看编码与输入指纹</summary><dl class="facts">${Object.entries(evidence.encoded_features).map(([label, value]) =>
        `<dt>${e(label)}</dt><dd>${value.toFixed(4)}</dd>`).join('')}</dl><p class="fingerprint mono">${e(evidence.input_sha256)}</p></details></section>`;
}

export function triagePage({loans, record, staff}) {
  const result = record?.triage;
  return `${heading('风险分流', '以包装快照确定是否安排开箱复核')}
    <div class="workbench">${fileIndex(loans, record, 'triage')}${record ? `<article class="dossier">${recordHeader(record)}
    ${result?.status === 'scored' ? riskResult(result) : `<section class="triage-intake"><h3>${result?.status === 'queued' ? '风险分流排队中' : '提交包装记录'}</h3>
      <p>${e(result?.error ?? (result?.status === 'queued' ? '模型完成后，本页会更新判定与复核任务。' : '先完成包装检查，再将材质、包装、路线、湿度与转运次数归档计算。'))}</p>
      ${staff.role === 'operator' && record.crate && result?.status !== 'queued' ? `<form data-action="triage"><button>${result?.status === 'failed' ? '重试分流' : '提交风险分流'}</button></form>` : ''}</section>`}
    </article>` : ''}</div>`;
}
