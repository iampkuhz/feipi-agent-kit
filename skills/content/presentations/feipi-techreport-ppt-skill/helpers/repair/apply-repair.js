/**
 * 兼容入口：P0 不再自动改写 IR。
 * Repair action 被转换为结构化提案，必须由语义层形成新 IR 后重新校验。
 */
'use strict';

function clone(value) {
  return JSON.parse(JSON.stringify(value));
}

function proposalFor(action) {
  const mapping = {
    shorten_text: 'compress_text',
    change_component_size: 'change_component_size',
    adjust_layout: 'change_layout',
    drop_secondary: 'drop_secondary',
    split_required: 'split_required',
  };
  return {
    action: mapping[action.type] || action.type,
    target_element_ids: action.target_element_ids || [],
    applied: false,
    message: action.type === 'adjust_font'
      ? '字号由 token 锁定，拒绝自动调整'
      : '需由语义层生成新的合法 IR；当前输入未被修改',
  };
}

function applyAction(slideIR, action) {
  return {
    success: true,
    changes: [proposalFor(action)],
    needs_user_decision: ['drop_secondary', 'split_required'].includes(action.type),
    unchanged_ir: clone(slideIR),
  };
}

function applyRepairPlan(slideIR, repairPlan) {
  const changes = (repairPlan.actions || []).map(proposalFor);
  const needsUserDecision = Boolean(repairPlan.requires_user_decision)
    || changes.some(change => ['drop_secondary', 'split_required'].includes(change.action));
  return {
    repaired_ir: clone(slideIR),
    changes,
    needs_user_decision: needsUserDecision,
    split_recommendation: changes.find(change => change.action === 'split_required') || null,
    change_summary: {
      total_changes: 0,
      proposed_changes: changes.length,
      font_adjusted: 0,
    },
  };
}

module.exports = { applyAction, applyRepairPlan };
