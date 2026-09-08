/**
 * 向后兼容入口：不再计算或写入新字号，只返回结构化 overflow 状态。
 */
'use strict';

const { ORDERED_OVERFLOW_STATES } = require('../../compiler/overflow-evaluator');

function tryAutofit(element) {
  const hasText = typeof element.content === 'string' || Boolean(element.content?.label || element.content?.text);
  return hasText
    ? { fitStatus: 'requires_evaluation', overflow_state: 'compress_text', next_actions: [...ORDERED_OVERFLOW_STATES] }
    : { fitStatus: 'fit', overflow_state: 'fit', next_actions: [] };
}

function autofitPage(ir) {
  const evaluations = (ir.elements || []).map(element => ({ element_id: element.id, ...tryAutofit(element) }));
  return {
    adjustments: [],
    warnings: evaluations.filter(item => item.overflow_state !== 'fit'),
    total_elements: evaluations.length,
    adjusted: 0,
    policy: 'font-size-is-token-locked',
  };
}

module.exports = { tryAutofit, autofitPage };
