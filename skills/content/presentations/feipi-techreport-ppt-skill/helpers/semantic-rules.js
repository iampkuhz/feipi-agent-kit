/**
 * 语义化碰撞规则
 * 基于 element kind 和 semantic_role 判断重叠问题的严重性。
 */

'use strict';

const geo = require('./geometry');
const { TokenStore } = require('../compiler/token-store');
const tokens = TokenStore.loadDefault();

// --- 默认阈值 ---
const DEFAULTS = {
  MIN_GAP: tokens.resolve('spacing.rules.min_element_gap_in'),
  OVERLAP_TOLERANCE: 0.01,  // inch，极小重叠视为计算误差
  // 连接器端点容差：连接器边界框在端点元素附近的重叠视为正常
  CONNECTOR_ENDPOINT_MARGIN: 0.15,  // inch
  // 容器小重叠容差：重叠面积 < 此比例的较小元素面积时，视为有意包含
  CONTAINER_SMALL_OVERLAP_RATIO: 0.2,
  LINE_HEIGHT_RATIO: 1.3
};

// --- 角色分类 ---
const CONTAINER_KINDS = new Set(['component_node', 'kpi_card']);
const TEXT_KINDS = new Set(['text', 'note', 'footer_note', 'legend', 'kpi_card']);
const CONNECTOR_KINDS = new Set(['connector']);
const LABEL_KINDS = new Set(['step_marker']);
const FOOTER_KINDS = new Set(['footer_note']);

function _isTextKind(kind) { return TEXT_KINDS.has(kind); }
function _isContainerKind(kind) { return CONTAINER_KINDS.has(kind); }
function _isConnector(kind) { return CONNECTOR_KINDS.has(kind); }
function _isLabel(kind) { return LABEL_KINDS.has(kind); }
function _isFooter(kind) { return FOOTER_KINDS.has(kind); }

// --- 字号下限 ---

function minFontForElement(element) {
  let role = element.text_role;
  if (!role) {
    if (element.semantic_role === 'title') role = 'title';
    else if (element.semantic_role === 'subtitle') role = 'subtitle';
    else if (element.kind === 'matrix' || element.kind === 'table') role = 'table_cell';
    else if (element.kind === 'footer_note' || element.semantic_role === 'source_note') role = 'footer';
    else if (element.kind === 'step_marker') role = 'diagram_badge';
    else if (element.kind === 'component_node') role = 'diagram_node';
    else if (element.kind === 'note' || element.kind === 'legend') role = 'caption';
    else role = 'body';
  }
  return tokens.typographyRole(role).minimum_pt;
}

// --- 工具函数 ---

function makeIssue(severity, type, elementIds, message, metrics, suggestion) {
  return { severity, type, element_ids: elementIds, message, metrics, suggestion };
}

function _rectArea(rect) {
  return rect.w * rect.h;
}

/**
 * 估算文本内容所需的渲染高度（inch）。
 * 基于字体大小、内容长度和区域宽度计算。
 * @param {Object} element
 * @param {Rect} bounds
 * @returns {number|null} 估算高度（inch），无法估算时返回 null
 */
function estimateTextRequiredHeight(element, bounds) {
  const style = element.style;
  const role = element.text_role || 'body';
  const fontSize = style?.font_size_pt ?? tokens.typographyRole(role).font_size_pt;
  const content = element.content;
  if (typeof content !== 'string' || content.length === 0) return null;
  if (!bounds || bounds.w <= 0) return null;

  const explicitLines = content.split(/\n/);
  const charsPerLine = Math.max(4, Math.floor(bounds.w * 72 / (fontSize * 0.95)));
  const lines = explicitLines.reduce((sum, line) => sum + Math.max(1, Math.ceil(line.length / charsPerLine)), 0);

  // 字号 pt 转 inch（1pt = 1/72 inch），乘以行高比
  const lineHeightInch = (fontSize / 72) * DEFAULTS.LINE_HEIGHT_RATIO;
  return lines * lineHeightInch;
}

/**
 * 判断重叠位置是否靠近连接器的端点（from/to 节点）。
 * 如果是，属于正常连接，不算 "穿过" 文本。
 * @param {Object} connector
 * @param {Rect} connBounds
 * @param {Rect} textBounds
 * @param {Map<string, Rect>} elementBoundsMap 所有元素 bounds 映射
 * @returns {boolean}
 */
function _isConnectorEndpointOverlap(connector, connBounds, textBounds, elementBoundsMap) {
  const fromId = connector.content && connector.content.from;
  const toId = connector.content && connector.content.to;
  const margin = DEFAULTS.CONNECTOR_ENDPOINT_MARGIN;

  // 检查 text 是否就是 from/to 目标
  if ((fromId && textBounds === elementBoundsMap.get(fromId)) ||
      (toId && textBounds === elementBoundsMap.get(toId))) {
    return true;
  }

  // 检查文本元素是否在 from/to 节点的 bounds 扩展容差范围内
  // 如果是，说明连接器是从该节点发出/到达时的正常重叠
  for (const targetId of [fromId, toId]) {
    if (!targetId) continue;
    const targetBounds = elementBoundsMap.get(targetId);
    if (!targetBounds) continue;
    // 扩展端点节点的边界
    const expanded = {
      x: targetBounds.x - margin,
      y: targetBounds.y - margin,
      w: targetBounds.w + margin * 2,
      h: targetBounds.h + margin * 2
    };
    // 如果文本元素完全在扩展范围内，说明是端点重叠
    if (geo.rectWithinBounds(textBounds, expanded, 0.01)) {
      return true;
    }
  }

  return false;
}

// --- 规则实现 ---

/**
 * 修复 1：连接器穿过文本 — 增加端点感知
 * 如果重叠区域靠近连接器的 from/to 端点，视为正常连接而非 "穿过"。
 */
function check_connector_cross_text(a, b, boundsA, boundsB, elementBoundsMap) {
  if (!_isConnector(a.kind) || !_isTextKind(b.kind)) return null;
  if (!boundsA || !boundsB) return null;

  const overlap = geo.rectOverlapArea(boundsA, boundsB);
  if (overlap <= DEFAULTS.OVERLAP_TOLERANCE * DEFAULTS.OVERLAP_TOLERANCE) return null;

  // 端点感知：如果重叠在连接器端点附近，跳过
  if (_isConnectorEndpointOverlap(a, boundsA, boundsB, elementBoundsMap)) {
    return makeIssue(
      'acceptable_intentional',
      'connector_near_endpoint',
      [a.id, b.id],
      `连接线 "${a.id}" 在端点附近与 "${b.id}" 接近`,
      { overlap_area: overlap },
      '连接器在端点节点附近的正常重叠，无需修复'
    );
  }

  return makeIssue(
    'hard_fail',
    'connector_cross_text',
    [a.id, b.id],
    `连接线 "${a.id}" 与文本 "${b.id}" 发生重叠`,
    { overlap_area: overlap, bounds_a: boundsA, bounds_b: boundsB },
    '调整连接线路径，使其不穿过文本区域'
  );
}

/**
 * 修复 2：step label 与 component node 重叠 — 增加小重叠容忍
 * 如果重叠面积很小（< 20% 的较小元素面积），降级为 warning。
 */
function check_label_overlap_node(a, b, boundsA, boundsB) {
  const label = _isLabel(a.kind) ? a : (_isLabel(b.kind) ? b : null);
  if (!label) return null;
  const node = label === a ? b : a;
  if (!_isContainerKind(node.kind)) return null;
  const bLabel = label === a ? boundsA : boundsB;
  const bNode = label === a ? boundsB : boundsA;
  if (!bLabel || !bNode) return null;

  const overlap = geo.rectOverlapArea(bLabel, bNode);
  if (overlap <= DEFAULTS.OVERLAP_TOLERANCE * DEFAULTS.OVERLAP_TOLERANCE) return null;

  // 小重叠容差：如果重叠面积 < 20% 的较小元素面积，降级为 warning
  const smallerArea = Math.min(_rectArea(bLabel), _rectArea(bNode));
  const ratio = smallerArea > 0 ? overlap / smallerArea : 0;
  if (ratio < DEFAULTS.CONTAINER_SMALL_OVERLAP_RATIO) {
    return makeIssue(
      'warning',
      'label_near_node',
      [label.id, node.id],
      `步骤标记 "${label.id}" 靠近组件节点 "${node.id}"（重叠 ${Math.round(ratio * 100)}%）`,
      { overlap_area: overlap, overlap_ratio: ratio },
      '步骤标记与节点边缘轻微重叠，建议调整位置'
    );
  }

  return makeIssue(
    'hard_fail',
    'label_overlap_node',
    [label.id, node.id],
    `步骤标记 "${label.id}" 与组件节点 "${node.id}" 重叠`,
    { overlap_area: overlap, bounds_label: bLabel, bounds_node: bNode },
    '调整步骤标记位置，使其不压住组件节点'
  );
}

/**
 * 修复 2：容器包含内部文本 — 增加小重叠容忍
 */
function check_container_contains_text(a, b, boundsA, boundsB) {
  if (!_isContainerKind(a.kind) || !_isTextKind(b.kind)) return null;
  if (!boundsA || !boundsB) return null;

  const overlap = geo.rectOverlapArea(boundsA, boundsB);
  if (overlap <= DEFAULTS.OVERLAP_TOLERANCE * DEFAULTS.OVERLAP_TOLERANCE) return null;

  // 检查是否允许有意包含
  const aAllow = a.constraints && a.constraints.allow_intentional_containment;
  const bAllow = b.constraints && b.constraints.allow_intentional_containment;
  if (aAllow || bAllow) {
    return makeIssue(
      'acceptable_intentional',
      'container_contains_text',
      [a.id, b.id],
      `元素 "${a.id}" 包含 "${b.id}"（有意包含）`,
      { overlap_area: overlap },
      '无需修复，有意包含'
    );
  }

  // component_node 内包含 label 文本通常是正常的
  if (b.semantic_role === 'system_component' || b.semantic_role === 'process_step') {
    return makeIssue(
      'acceptable_intentional',
      'container_contains_text',
      [a.id, b.id],
      `组件 "${a.id}" 包含标签文本 "${b.id}"`,
      { overlap_area: overlap },
      '组件节点包含其标签文本，通常可接受'
    );
  }

  // 小重叠容差：重叠面积 < 20% 的较小元素面积，视为装饰性重叠
  const smallerArea = Math.min(_rectArea(boundsA), _rectArea(boundsB));
  const ratio = smallerArea > 0 ? overlap / smallerArea : 0;
  if (ratio < DEFAULTS.CONTAINER_SMALL_OVERLAP_RATIO) {
    return makeIssue(
      'acceptable_intentional',
      'container_small_overlap',
      [a.id, b.id],
      `元素 "${a.id}" 与 "${b.id}" 边缘重叠（重叠 ${Math.round(ratio * 100)}%，< ${Math.round(DEFAULTS.CONTAINER_SMALL_OVERLAP_RATIO * 100)}% 阈值）`,
      { overlap_area: overlap, overlap_ratio: ratio },
      '小面积边缘重叠，视为有意装饰，无需修复'
    );
  }

  // 其他情况：意外重叠
  return makeIssue(
    'warning',
    'container_overlap_text',
    [a.id, b.id],
    `元素 "${a.id}" 与 "${b.id}" 发生重叠`,
    { overlap_area: overlap },
    '检查是否为有意包含，否则调整位置'
  );
}

function check_footer_collision(a, b, boundsA, boundsB) {
  const aFooter = _isFooter(a.kind);
  const bFooter = _isFooter(b.kind);
  if (!aFooter && !bFooter) return null;
  if (!boundsA || !boundsB) return null;

  const overlap = geo.rectOverlapArea(boundsA, boundsB);
  if (overlap <= DEFAULTS.OVERLAP_TOLERANCE * DEFAULTS.OVERLAP_TOLERANCE) return null;

  return makeIssue(
    'hard_fail',
    'footer_collision',
    [a.id, b.id],
    `脚注 "${aFooter ? a.id : b.id}" 与 "${aFooter ? b.id : a.id}" 发生碰撞`,
    { overlap_area: overlap },
    '调整脚注位置或压缩上方内容，确保脚注不压住主体'
  );
}

function check_text_overlap(a, b, boundsA, boundsB) {
  if (!_isTextKind(a.kind) || !_isTextKind(b.kind)) return null;
  if (!boundsA || !boundsB) return null;
  const overlap = geo.rectOverlapArea(boundsA, boundsB);
  if (overlap <= DEFAULTS.OVERLAP_TOLERANCE * DEFAULTS.OVERLAP_TOLERANCE) return null;
  return makeIssue(
    'hard_fail',
    'text_overlap',
    [a.id, b.id],
    `文本元素 "${a.id}" 与 "${b.id}" 发生重叠`,
    { overlap_area: overlap, bounds_a: boundsA, bounds_b: boundsB },
    '切换组件尺寸或布局；禁止通过缩小字号解决'
  );
}

function check_low_font(element) {
  const style = element.style;
  if (!style || typeof style.font_size_pt !== 'number') return null;

  const minFont = minFontForElement(element);
  if (style.font_size_pt >= minFont) return null;

  return makeIssue(
    'hard_fail',
    'low_font',
    [element.id],
    `元素 "${element.id}" 字号 ${style.font_size_pt}pt 低于下限 ${minFont}pt`,
    { font_size: style.font_size_pt, min_font: minFont, role: element.semantic_role },
    '压缩文本内容或增加区域空间，字号不得低于下限'
  );
}

function check_out_of_bounds(element, elemBounds, safeBounds, region) {
  // 检查 canvas safe bounds
  if (!geo.rectWithinBounds(elemBounds, safeBounds, DEFAULTS.OVERLAP_TOLERANCE)) {
    return makeIssue(
      'hard_fail',
      'out_of_bounds',
      [element.id],
      `元素 "${element.id}" 超出 canvas safe bounds`,
      { elem_bounds: elemBounds, safe_bounds: safeBounds },
      '调整元素位置，确保在页面安全区域内'
    );
  }

  // 检查 region bounds
  const mustStay = element.constraints && element.constraints.must_stay_within_region;
  if (mustStay && region) {
    const rBounds = region.bounds;
    if (!geo.rectWithinBounds(elemBounds, rBounds, DEFAULTS.OVERLAP_TOLERANCE)) {
      return makeIssue(
        'hard_fail',
        'out_of_region',
        [element.id],
        `元素 "${element.id}" 超出所属 region "${region.id}" 的边界`,
        { elem_bounds: elemBounds, region_bounds: rBounds },
        '调整元素位置，确保在所属区域内'
      );
    }
  }

  return null;
}

function check_too_close(a, b, boundsA, boundsB, minGap) {
  const gap = minGap || DEFAULTS.MIN_GAP;
  if (!boundsA || !boundsB) return null;

  // connector 不参与间距检查
  if (_isConnector(a.kind) || _isConnector(b.kind)) return null;

  const dist = geo.gapBetweenRects(boundsA, boundsB);
  if (dist >= gap) return null;
  if (dist === 0) return null;

  // 同 region 内元素可以较近
  if (a.region_id === b.region_id) return null;

  return makeIssue(
    'warning',
    'too_close',
    [a.id, b.id],
    `元素 "${a.id}" 与 "${b.id}" 间距过小 (${dist.toFixed(3)} inch)`,
    { gap: dist, min_gap: gap },
    '适当增加元素间距，避免视觉拥挤'
  );
}

/**
 * 修复 3：文本高度估算
 * 基于内容长度和字号，估算文本需要的渲染高度。
 * 如果估算高度 > 给定 bounds 高度的 1.2 倍，发出 warning。
 * @param {Object} element
 * @param {Rect} bounds
 * @returns {Object|null}
 */
function check_text_overflow(element, bounds) {
  if (!bounds || bounds.w <= 0 || bounds.h <= 0) return null;

  const requiredHeight = estimateTextRequiredHeight(element, bounds);
  if (requiredHeight === null) return null;

  const availableHeight = bounds.h;
  if (requiredHeight <= availableHeight * 1.2) return null; // 20% 容差

  const ratio = requiredHeight / availableHeight;
  return makeIssue(
    'warning',
    'text_may_overflow',
    [element.id],
    `元素 "${element.id}" 文本可能超出区域（估算需要 ${requiredHeight.toFixed(2)} inch，可用 ${availableHeight.toFixed(2)} inch）`,
    { estimated_height: requiredHeight, available_height: availableHeight, ratio },
    '压缩文本内容或增加区域高度，避免渲染时截断'
  );
}

module.exports = {
  DEFAULTS,
  check_connector_cross_text,
  check_label_overlap_node,
  check_container_contains_text,
  check_footer_collision,
  check_text_overlap,
  check_low_font,
  check_out_of_bounds,
  check_too_close,
  check_text_overflow,
  minFontForElement,
  estimateTextRequiredHeight
};
