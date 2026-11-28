/**
 * 静态 QA 引擎
 * 读取 Slide IR 对象，应用语义化碰撞规则，返回结构化报告。
 */

'use strict';

const geo = require('./geometry');
const rules = require('./semantic-rules');
const { estimateTextFit } = require('./layout/text-measure');

/**
 * 计算 canvas safe bounds。
 * @param {Object} canvas
 * @returns {{x: number, y: number, w: number, h: number}}
 */
function calcSafeBounds(canvas) {
  const sm = canvas.safe_margin_in;
  let mt, mr, mb, ml;
  if (typeof sm === 'number') {
    mt = mr = mb = ml = sm;
  } else {
    mt = sm.top || 0;
    mr = sm.right || 0;
    mb = sm.bottom || 0;
    ml = sm.left || 0;
  }
  return {
    x: ml,
    y: mt,
    w: canvas.width_in - ml - mr,
    h: canvas.height_in - mt - mb
  };
}

/**
 * 主入口：读取 Slide IR 对象，返回结构化 QA report。
 * @param {Object} slideIR
 * @returns {{status: string, summary: Object, issues: Array<Object>}}
 */
function runStaticQA(slideIR) {
  if (slideIR.version === 'v1' || slideIR.version === 'v2') {
    const { compileRenderPlan, toLegacyQAIR } = require('../compiler/render-plan-compiler');
    slideIR = toLegacyQAIR(compileRenderPlan(slideIR));
  }
  const issues = [];
  const elements = slideIR.elements || [];
  const regions = slideIR.regions || [];
  const canvas = slideIR.canvas;
  const safeBounds = calcSafeBounds(canvas);

  // 建立 region 查找表
  const regionMap = {};
  for (const r of regions) {
    regionMap[r.id] = r;
  }

  // 计算每个元素的 bounds
  const elemData = [];
  const elementBoundsMap = new Map();
  for (const e of elements) {
    const b = geo.elementBounds(e);
    elemData.push({ element: e, bounds: b, region: regionMap[e.region_id] || null });
    if (b) elementBoundsMap.set(e.id, b);
  }

  // 单元素检查：字号、越界、文本溢出
  for (const { element, bounds, region } of elemData) {
    // 字号检查
    const fontIssue = rules.check_low_font(element);
    if (fontIssue) issues.push(fontIssue);

    // 越界检查（仅对有 layout 坐标的元素）
    if (bounds) {
      const boundIssue = rules.check_out_of_bounds(element, bounds, safeBounds, region);
      if (boundIssue) issues.push(boundIssue);

      // 修复 3：文本高度估算检查
      const overflowIssue = rules.check_text_overflow(element, bounds);
      if (overflowIssue) issues.push(overflowIssue);
    }
  }

  // 元素对检查
  const checked = new Set();
  for (let i = 0; i < elemData.length; i++) {
    for (let j = i + 1; j < elemData.length; j++) {
      const { element: a, bounds: boundsA } = elemData[i];
      const { element: b, bounds: boundsB, region: regionB } = elemData[j];

      // 只对两个元素都有 bounds 的情况做几何检查
      if (!boundsA || !boundsB) continue;

      // 避免重复检查同一对
      const pairKey = [a.id, b.id].sort().join('||');
      if (checked.has(pairKey)) continue;
      checked.add(pairKey);

      let issue;

      // 修复 1：连接器交叉文本（带端点感知）
      issue = rules.check_connector_cross_text(a, b, boundsA, boundsB, elementBoundsMap);
      if (issue) issues.push(issue);
      issue = rules.check_connector_cross_text(b, a, boundsB, boundsA, elementBoundsMap);
      if (issue) issues.push(issue);

      // 修复 2：标签重叠节点（带小重叠容忍）
      issue = rules.check_label_overlap_node(a, b, boundsA, boundsB);
      if (issue) issues.push(issue);

      // 修复 2：容器包含文本（带小重叠容忍）
      issue = rules.check_container_contains_text(a, b, boundsA, boundsB);
      if (issue) issues.push(issue);
      issue = rules.check_container_contains_text(b, a, boundsB, boundsA);
      if (issue) issues.push(issue);

      // 脚注碰撞
      issue = rules.check_footer_collision(a, b, boundsA, boundsB);
      if (issue) issues.push(issue);

      issue = rules.check_text_overlap(a, b, boundsA, boundsB);
      if (issue) issues.push(issue);

      // 间距过小
      issue = rules.check_too_close(a, b, boundsA, boundsB);
      if (issue) issues.push(issue);
    }
  }

  // 内容完整性检查
  const roles = new Set(elements.map(e => e.semantic_role));
  if (!roles.has('title')) {
    issues.push({
      severity: 'hard_fail',
      type: 'missing_title',
      element_ids: [],
      message: '页面缺少 title 元素',
      metrics: {},
      suggestion: '添加页面标题元素'
    });
  }
  if (!roles.has('takeaway')) {
    issues.push({
      severity: 'warning',
      type: 'missing_takeaway',
      element_ids: [],
      message: '页面缺少 takeaway 元素',
      metrics: {},
      suggestion: '添加一行结论元素'
    });
  }

  // Region density check: 检查每个区域内的元素数量是否超出容量
  for (const region of regions) {
    const regionEls = elements.filter(e => e.region_id === region.id);
    const maxItems = region.capacity?.max_items;
    if (maxItems && regionEls.length > maxItems) {
      issues.push({
        severity: 'warning',
        type: 'region_density_exceeded',
        element_ids: regionEls.map(e => e.id),
        message: `区域 "${region.id}" 包含 ${regionEls.length} 个元素，超过容量上限 ${maxItems}`,
        metrics: { count: regionEls.length, max: maxItems },
        suggestion: '减少元素数量或建议拆页'
      });
    }
  }

  // Layout unsolved check: 检查有多少元素缺少 bounds
  const unsolvedElements = elements.filter(e =>
    !e.layout || e.layout.x === undefined || e.layout.w === undefined
  );
  if (unsolvedElements.length > 0) {
    issues.push({
      severity: 'warning',
      type: 'layout_unsolved',
      element_ids: unsolvedElements.map(e => e.id),
      message: `${unsolvedElements.length} 个元素缺少布局坐标，需要运行 solver`,
      metrics: { unsolved_count: unsolvedElements.length },
      suggestion: '运行 solve_slide_layout.js 自动分配坐标'
    });
  }

  // 汇总
  let hardFail = 0;
  let warning = 0;
  let acceptable = 0;
  for (const issue of issues) {
    if (issue.severity === 'hard_fail') hardFail++;
    else if (issue.severity === 'warning') warning++;
    else if (issue.severity === 'acceptable_intentional') acceptable++;
  }

  return {
    status: hardFail > 0 ? 'fail' : 'pass',
    summary: {
      hard_fail: hardFail,
      warning: warning,
      acceptable_intentional: acceptable
    },
    issues
  };
}

module.exports = {
  runStaticQA,
  calcSafeBounds
};
