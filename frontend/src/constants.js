export const roles = {operator: '借展经办', supervisor: '文保主管', viewer: '展务阅览'};
export const loanStates = {
  registered: '待查箱', packing: '包装检查', triage_pending: '分流中', ready: '可放行',
  review_required: '待开箱复核', sampling: '待抽检', hold: '暂停运输', dispatched: '已派车',
};
export const reviewStates = {
  awaiting_witness: '待开箱见证', awaiting_supervisor: '待主管签字',
  sampling: '待封签抽检', held: '暂缓放行', cleared: '抽检通过',
};
export const materials = {porcelain: '瓷器', paper: '纸本', bronze: '青铜器'};
export const packings = {foam: '泡棉贴合', suspension: '悬托固定', double_wall: '双层箱'};
export const routes = {direct: '直达', transfer: '中转', mountain: '山地运输'};
export const windowStates = {setup: '展厅布置', booked: '窗口确认', conflict: '窗口冲突', dispatched: '已派车'};
export const sections = {
  archive: ['借展档案', '借展单、包装材料与封签'],
  transit: ['运输窗口', '展厅布置、车辆占用与派车'],
  triage: ['风险分流', '包装快照与模型判定'],
  review: ['开箱复核', '双人签署、改判和封签抽检'],
};
export const auditActions = {
  loan_registered: '登记借展', crate_checked: '保存包装检查', window_conflict: '登记冲突窗口',
  window_reserved: '确认运输窗口', dispatch_blocked: '拦截派车', dispatched: '派车封存',
  triage_queued: '进入分流队列', triage_retried: '重试风险分流', triage_scored: '模型判定已归档',
  triage_failed: '分流计算失败', unpack_witnessed: '开箱见证签署', downgrade_sample_required: '主管改判，转抽检',
  unpack_held: '主管暂停运输', unpack_reopened: '主管重开复核', sample_mismatch: '抽检封签不符', sample_cleared: '抽检通过',
};
