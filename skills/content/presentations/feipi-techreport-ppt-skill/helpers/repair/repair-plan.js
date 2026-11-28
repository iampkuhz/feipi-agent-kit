/**
 * Repair Plan 生成器
 * 根据分类后的 issues 生成结构化 repair plan。
 * 当前阶段不自动做激进改写，只做保守调整或输出建议。
 */

'use strict';

/**
 * 生成 repair plan。
 * @param {Array} classified - classify-issues 的分类结果
 * @param {Object} slideIR - 当前 Slide IR
 * @param {number} round - 当前迭代轮次 (1-3)
 * @returns {Object} repair plan
 */
function generateRepairPlan(classified, slideIR, round) {
  const hardFails = classified.filter(c => c.severity === 'hard_fail');
  const warnings = classified.filter(c => c.severity === 'warning');

  if (hardFails.length === 0 && warnings.length === 0) {
    return {
      status: 'no_repair_needed',
      round,
      actions: [],
      requires_user_decision: false,
      message: '所有检查通过，无需修复。'
    };
  }

  const actions = [];

  for (const item of hardFails) {
    const action = _generateActionForType(item, slideIR);
    if (action) {
      actions.push(action);
    }
  }

  // 第 3 轮仍有 hard_fail → needs_user_decision
  if (round >= 3 && hardFails.length > 0) {
    return {
      status: 'needs_user_decision',
      round,
      actions: [],
      requires_user_decision: true,
      recommendation: '建议拆成两页',
      reason: _buildFailureReason(hardFails, slideIR),
      remaining_issues: hardFails.map(h => ({
        type: h.type,
        message: h.message
      }))
    };
  }

  // 内容过载 → 也需要用户决策
  const densityIssues = classified.filter(c => c.type === 'density_overload');
  if (densityIssues.length > 2 || _isContentOverloaded(slideIR)) {
    return {
      status: 'needs_user_decision',
      round,
      actions,
      requires_user_decision: true,
      recommendation: '建议拆成两页',
      reason: '页面内容密度过高，无法在不损失可读性的前提下自动修复',
      remaining_issues: densityIssues.map(d => ({
        type: d.type,
        message: d.message
      }))
    };
  }

  const hasRepairableActions = actions.length > 0;

  return {
    status: hasRepairableActions ? 'repairable' : 'needs_user_decision',
    round,
    actions,
    requires_user_decision: !hasRepairableActions,
    message: hasRepairableActions
      ? `生成 ${actions.length} 项修复动作，将在下一轮应用。`
      : '无自动修复方案，需要人工介入。'
  };
}

function _generateActionForType(item, slideIR) {
  const elemIds = item.element_ids;

  switch (item.type) {
    case 'layout_overflow':
      return {
        type: elemIds.length > 0 ? 'move_or_resize' : 'adjust_layout',
        target_element_ids: elemIds,
        reason: _extractReason(item.message),
        instruction: _instructionForOverflow(item),
        conservative: true
      };

    case 'text_too_small':
      // 只有在非第 1 轮才尝试缩小内容，否则优先缩短文本
      return {
        type: elemIds.length > 0 ? 'shorten_text' : 'adjust_font',
        target_element_ids: elemIds,
        reason: _extractReason(item.message),
        instruction: '缩短文本内容以适配最小字号要求，或提高字号至阈值下限。',
        conservative: true
      };

    case 'text_clipping_risk':
      return {
        type: elemIds.length > 0 ? 'shorten_text' : 'reduce_content',
        target_element_ids: elemIds,
        reason: _extractReason(item.message),
        instruction: '缩短文本、减少行数、或增大元素区域。',
        conservative: true
      };

    case 'semantic_overlap':
      return {
        type: elemIds.length > 0 ? 'move_or_resize' : 'adjust_layout',
        target_element_ids: elemIds,
        reason: _extractReason(item.message),
        instruction: '调整元素位置以分离重叠区域。',
        conservative: true
      };

    case 'density_overload':
      return {
        type: 'reduce_content',
        target_element_ids: elemIds,
        reason: _extractReason(item.message),
        instruction: '删除次要内容、合并相似项、或建议拆页。',
        conservative: true
      };

    case 'content_policy_violation':
      return {
        type: 'add_missing_element',
        target_element_ids: elemIds,
        reason: _extractReason(item.message),
        instruction: '补充 Slide IR 中缺失的必需元素（标题或 takeaway）。',
        conservative: true
      };

    case 'render_unavailable':
      // 这不是可自动修复的问题
      return null;

    default:
      return {
        type: 'manual_review',
        target_element_ids: elemIds,
        reason: _extractReason(item.message),
        instruction: '未知问题类型，需要人工审查。',
        conservative: true
      };
  }
}

function _instructionForOverflow(item) {
  if (item.original_type === 'footer_collision') {
    return '将脚注下移至页面底部，或压缩脚注文本。';
  }
  if (item.original_type === 'out_of_bounds' || item.original_type === 'out_of_region') {
    return '将元素移回安全区域内，或缩小元素尺寸。';
  }
  return '调整元素位置或尺寸，确保不越界。';
}

function _extractReason(message) {
  if (!message) return '未知原因';
  // 去掉 "[✗]" 等前缀
  return message.replace(/^\[.*?\]\s*/, '').trim();
}

function _isContentOverloaded(slideIR) {
  const elements = slideIR.elements || [];
  // 元素数超过版式合理容量
  const elementCount = elements.length;
  if (elementCount > 20) return true;
  return false;
}

function _buildFailureReason(hardFails, slideIR) {
  const types = new Set(hardFails.map(h => h.type));
  const reasons = [];
  if (types.has('layout_overflow')) reasons.push('布局溢出');
  if (types.has('text_too_small')) reasons.push('字号过小');
  if (types.has('text_clipping_risk')) reasons.push('文本截断风险');
  if (types.has('semantic_overlap')) reasons.push('元素重叠');
  if (types.has('content_policy_violation')) reasons.push('内容策略违规');

  const reasonStr = reasons.length > 0 ? reasons.join('、') : '多项硬失败';
  return `经过 3 轮自动修复仍存在 ${reasonStr}，${hardFails.length} 项问题未解决。`;
}

module.exports = {
  generateRepairPlan,
  // 暴露内部函数供测试
  _generateActionForType,
  _isContentOverloaded
};
