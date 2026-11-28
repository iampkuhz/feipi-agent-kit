/**
 * Issue 分类器
 * 把 Static QA 和 Render QA 的 issues 映射为可修复的类型。
 */

'use strict';

const { TokenStore } = require('../../compiler/token-store');
const tokens = TokenStore.loadDefault();

// Static QA → pipeline 分类映射
const STATIC_QA_TYPE_MAP = {
  // 布局溢出类
  out_of_bounds: 'layout_overflow',
  out_of_region: 'layout_overflow',
  // 文字类
  low_font: 'text_too_small',
  text_may_overflow: 'text_clipping_risk',
  // 语义碰撞类
  connector_cross_text: 'semantic_overlap',
  label_overlap_node: 'semantic_overlap',
  label_near_node: 'semantic_overlap',
  container_small_overlap: 'semantic_overlap',
  container_overlap_text: 'semantic_overlap',
  connector_near_endpoint: 'semantic_overlap',
  container_contains_text: 'semantic_overlap',
  // 脚注碰撞
  footer_collision: 'layout_overflow',
  // 间距
  too_close: 'density_overload',
  // 内容完整性
  missing_title: 'content_policy_violation',
  missing_takeaway: 'content_policy_violation'
};

// Render QA → pipeline 分类映射
const RENDER_QA_TYPE_MAP = {
  slide_image_missing: 'render_unavailable',
  slide_image_empty: 'render_unavailable',
  slide_image_too_small: 'render_unavailable',
  aspect_ratio_mismatch: 'render_unavailable',
  png_header_invalid: 'render_unavailable',
  render_unavailable: 'render_unavailable'
};

/**
 * 分类单个 issue。
 */
function classifyIssue(issue, source) {
  const typeMap = source === 'render' ? RENDER_QA_TYPE_MAP : STATIC_QA_TYPE_MAP;
  const issueType = issue.type || '';

  // 提取 element_ids: static QA 的 issue.element_ids 是实际的元素 ID 数组
  let elemIds = [];
  if (issue.element_ids && issue.element_ids.length > 0) {
    elemIds = issue.element_ids;
  } else if (issue.slide_index) {
    elemIds = [`slide_${issue.slide_index}`];
  }

  if (typeMap[issueType]) {
    return {
      type: typeMap[issueType],
      severity: issue.severity,
      source,
      original_type: issueType,
      element_ids: elemIds,
      message: issue.message,
      detail: issue.detail || null
    };
  }

  // 未知类型，根据 severity 推断
  if (issue.severity === 'hard_fail') {
    return {
      type: 'unknown',
      severity: 'hard_fail',
      source,
      original_type: issueType,
      element_ids: elemIds,
      message: issue.message,
      detail: issue.detail || null
    };
  }

  return {
    type: 'unknown',
    severity: issue.severity,
    source,
    original_type: issueType,
    element_ids: elemIds,
    message: issue.message,
    detail: issue.detail || null
  };
}

/**
 * 分类所有 issues（static + render）。
 */
function classifyAllIssues(staticQAReport, renderQAReport) {
  const classified = [];

  if (staticQAReport && staticQAReport.issues) {
    for (const issue of staticQAReport.issues) {
      classified.push(classifyIssue(issue, 'static'));
    }
  }

  if (renderQAReport && renderQAReport.issues) {
    for (const issue of renderQAReport.issues) {
      classified.push(classifyIssue(issue, 'render'));
    }
  }

  return classified;
}

/**
 * 按类型汇总，返回分类统计 + repair hint。
 */
function summarizeClassified(classified) {
  const groups = {};
  for (const item of classified) {
    if (!groups[item.type]) {
      groups[item.type] = {
        type: item.type,
        count: 0,
        hard_fail: 0,
        warning: 0,
        items: [],
        repair_hint: REPAIR_HINTS[item.type] || '需要人工介入处理'
      };
    }
    groups[item.type].count++;
    if (item.severity === 'hard_fail') groups[item.type].hard_fail++;
    if (item.severity === 'warning') groups[item.type].warning++;
    groups[item.type].items.push(item);
  }
  return Object.values(groups);
}

const REPAIR_HINTS = {
  layout_overflow: '调整元素位置或尺寸，确保不越界。优先考虑缩小内容区域或移动元素到空闲区域。',
  text_too_small: `恢复到角色 token 最小值：body ≥ ${tokens.typographyRole('body').minimum_pt}pt，table_cell ≥ ${tokens.typographyRole('table_cell').minimum_pt}pt；空间不足时返回 overflow。`,
  text_clipping_risk: '缩短文本内容、减少列数、或增大元素高度。',
  semantic_overlap: '分离重叠元素。如果重叠是装饰性（badge 贴角等），可标记为 intentional。',
  density_overload: '减少元素数量或增大间距。考虑删除次要内容或拆页。',
  missing_dependency: '检查引用的 region、source_refs 是否存在。修复 Slide IR 中的引用错误。',
  render_unavailable: '启用 PowerPoint 或 QuickLook/CoreText 权威渲染；LibreOffice 仅作兼容对照。当前不能声称视觉通过。',
  content_policy_violation: '检查 Slide IR 是否缺少必需内容（标题、takeaway）。补充缺失元素。',
  unknown: '该问题类型未知，建议人工审查后决定修复策略。'
};

module.exports = {
  classifyIssue,
  classifyAllIssues,
  summarizeClassified,
  REPAIR_HINTS,
  STATIC_QA_TYPE_MAP,
  RENDER_QA_TYPE_MAP
};
