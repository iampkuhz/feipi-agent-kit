/**
 * Split Needed — 检测页面是否需要拆分。
 * 处理内容过载、密度过高、无法自动修复的场景。
 */
'use strict';

/**
 * 检测页面是否需要拆分。
 * @param {Object} slideIR - Slide IR
 * @param {Object} staticQAReport - Static QA report
 * @returns {{needs_split: boolean, reason: string, suggestion: string|null}}
 */
function needsSplit(slideIR, staticQAReport) {
  const elements = slideIR?.elements || [];
  const elementCount = elements.length;

  // 规则 1: 元素数过多
  if (elementCount > 25) {
    return {
      needs_split: true,
      reason: `页面包含 ${elementCount} 个元素，超过合理容量 (25)`,
      suggestion: '建议拆分为两页：保留核心结论在一页，详情放在第二页'
    };
  }

  // 规则 2: 多个 hard_fail 且包含密度问题
  const hardFails = staticQAReport?.issues?.filter(i => i.severity === 'hard_fail') || [];
  const densityIssues = hardFails.filter(i =>
    i.type === 'density_overload' ||
    i.type === 'text_may_overflow' ||
    i.type === 'semantic_overlap'
  );

  if (densityIssues.length >= 3) {
    return {
      needs_split: true,
      reason: `${densityIssues.length} 项密度相关 hard_fail 同时存在`,
      suggestion: '建议按主题拆页'
    };
  }

  // 规则 3: 多个 region 同时过载
  const regions = {};
  for (const e of elements) {
    const rid = e.region_id || 'unknown';
    if (!regions[rid]) regions[rid] = 0;
    regions[rid]++;
  }

  const overloadedRegions = Object.entries(regions)
    .filter(([, count]) => count > 10)
    .map(([rid]) => rid);

  if (overloadedRegions.length >= 2) {
    return {
      needs_split: true,
      reason: `${overloadedRegions.length} 个区域同时过载: ${overloadedRegions.join(', ')}`,
      suggestion: '建议按区域主题拆页'
    };
  }

  return { needs_split: false, reason: null, suggestion: null };
}

module.exports = { needsSplit };
