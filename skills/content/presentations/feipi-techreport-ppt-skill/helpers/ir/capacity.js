/**
 * 布局容量检查。
 * 每类 layout pattern 有基本容量估计，超限时输出 needs_user_decision 建议。
 */
'use strict';

const CAPACITY_LIMITS = {
  'architecture-map': {
    component_node: { max: 10, warning_at: 8 },
    step_marker: { max: 12, warning_at: 9 },
    connector: { max: 30, warning_at: 20 },
  },
  'comparison-matrix': {
    comparison_objects: { max: 4, warning_at: 4 },
    comparison_dimensions: { max: 5, warning_at: 5 },
  },
  'flow-diagram': {
    step_marker: { max: 10, warning_at: 8, optimal_max: 7 },
    connector: { max: 15, warning_at: 10 },
  },
  'layered-stack': {
    component_node: { max: 20, warning_at: 15 },
  },
  'metrics-dashboard': {
    kpi_card: { max: 6, warning_at: 5 },
  },
  'roadmap-timeline': {
    step_marker: { max: 10, warning_at: 8 },
  },
  'decision-tree': {
    component_node: { max: 15, warning_at: 10 },
    connector: { max: 20, warning_at: 15 },
  },
  'capability-map': {
    component_node: { max: 18, warning_at: 14 },
  },
};

// Global limits per element kind
const GLOBAL_LIMITS = {
  bullet_text: { max: 5, warning_at: 4 },
};

function checkCapacity(ir) {
  const issues = [];
  const pattern = ir.layout_pattern;
  if (!pattern) return issues;

  const limits = CAPACITY_LIMITS[pattern];
  if (!limits) return issues;

  // Count elements by kind
  const counts = {};
  const bulletTexts = [];
  for (const el of ir.elements || []) {
    counts[el.kind] = (counts[el.kind] || 0) + 1;
    if (el.kind === 'text' && el.semantic_role === 'evidence') {
      bulletTexts.push(el);
    }
  }

  // Check pattern-specific limits
  for (const [kind, limit] of Object.entries(limits)) {
    const count = counts[kind] || 0;
    if (count > limit.max) {
      issues.push({
        type: 'capacity_exceeded',
        kind,
        count,
        max: limit.max,
        severity: 'needs_user_decision',
        message: `${pattern}: ${kind} 数量 ${count} 超过上限 ${limit.max}，建议拆页或降维`,
      });
    } else if (count > limit.warning_at) {
      issues.push({
        type: 'capacity_warning',
        kind,
        count,
        warning_at: limit.warning_at,
        severity: 'warning',
        message: `${pattern}: ${kind} 数量 ${count} 接近建议上限 ${limit.warning_at}`,
      });
    }
    // Optimal max for flow-diagram
    if (limit.optimal_max && count > limit.optimal_max && count <= limit.warning_at) {
      issues.push({
        type: 'capacity_optimal',
        kind,
        count,
        optimal_max: limit.optimal_max,
        severity: 'info',
        message: `${pattern}: ${kind} 数量 ${count} 超过最佳值 ${limit.optimal_max}，建议精简`,
      });
    }
  }

  // Check global bullet text limit
  const bulletCount = bulletTexts.length;
  if (bulletCount > GLOBAL_LIMITS.bullet_text.max) {
    issues.push({
      type: 'bullet_text_exceeded',
      count: bulletCount,
      max: GLOBAL_LIMITS.bullet_text.max,
      severity: 'needs_user_decision',
      message: `bullet 文字数量 ${bulletCount} 超过上限 ${GLOBAL_LIMITS.bullet_text.max}，建议拆页`,
    });
  } else if (bulletCount > GLOBAL_LIMITS.bullet_text.warning_at) {
    issues.push({
      type: 'bullet_text_warning',
      count: bulletCount,
      severity: 'warning',
      message: `bullet 文字数量 ${bulletCount} 接近建议上限 ${GLOBAL_LIMITS.bullet_text.warning_at}`,
    });
  }

  return issues;
}

module.exports = { checkCapacity, CAPACITY_LIMITS };
