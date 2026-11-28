/**
 * Architecture Map Builder
 * 构建架构图页面：Header + 主架构图 + 侧栏说明 + Takeaway + Footer
 */

'use strict';

const prim = require('../primitives');

/**
 * 按优先级对元素排序。
 */
function sortByPriority(elements) {
  return [...elements].sort((a, b) => {
    const pA = (a.constraints && a.constraints.priority) || 'medium';
    const pB = (b.constraints && b.constraints.priority) || 'medium';
    const order = { critical: 0, high: 1, medium: 2, low: 3 };
    return (order[pA] || 2) - (order[pB] || 2);
  });
}

/**
 * 将元素按 region 分组。
 */
function groupByRegion(elements) {
  const groups = {};
  for (const e of elements) {
    const rid = e.region_id || 'unknown';
    if (!groups[rid]) groups[rid] = [];
    groups[rid].push(e);
  }
  return groups;
}

/**
 * 渲染架构图页面。
 * @param {Object} pres - PptxGenJS presentation
 * @param {Object} slideIR - Slide IR 对象
 * @param {Object} thm - 主题
 */
function build(pres, slideIR, thm) {
  const canvasSize = thm.getCanvasSize(slideIR.canvas);
  const slide = pres.addSlide();
  const elements = slideIR.elements || [];
  const groups = groupByRegion(elements);

  // 设置背景
  slide.background = { color: thm.COLORS.white };

  // 1. Header 区
  const headerElements = groups['region_header'] || [];
  for (const elem of headerElements) {
    prim.addTextBox(slide, elem, thm);
  }

  // 2. 主视觉区：先连接器（底层），后节点（上层）
  const mainElements = groups['region_main'] || [];
  const connectors = mainElements.filter(e => e.kind === 'connector');
  const stepMarkers = mainElements.filter(e => e.kind === 'step_marker');
  const nodes = mainElements.filter(e => e.kind === 'component_node');
  const textNotes = mainElements.filter(e => e.kind === 'note');
  const others = mainElements.filter(e => !['connector', 'step_marker', 'component_node', 'note'].includes(e.kind));

  // 连接线（底层）
  for (const conn of sortByPriority(connectors)) {
    prim.addConnector(slide, conn, thm);
  }

  // 组件节点
  for (const node of sortByPriority(nodes)) {
    prim.addComponentNode(slide, node, thm);
  }

  // 步骤标记（在节点上层）
  for (const marker of sortByPriority(stepMarkers)) {
    prim.addStepMarker(slide, marker, thm);
  }

  // 说明文字/注释
  for (const note of sortByPriority(textNotes)) {
    prim.addNote(slide, note, thm);
  }

  // 其他元素
  for (const elem of sortByPriority(others)) {
    prim.addTextBox(slide, elem, thm);
  }

  // 3. 侧栏
  const sideElements = groups['region_side'] || [];
  for (const elem of sortByPriority(sideElements)) {
    if (elem.kind === 'note') {
      prim.addNote(slide, elem, thm);
    } else {
      prim.addTextBox(slide, elem, thm);
    }
  }

  // 4. Takeaway
  const takeawayElements = groups['region_takeaway'] || [];
  for (const elem of takeawayElements) {
    prim.addTextBox(slide, elem, thm);
  }

  // 5. Footer
  const footerElements = groups['region_footer'] || [];
  for (const elem of footerElements) {
    prim.addFooterNote(slide, elem, thm);
  }

  return {
    slide_id: slideIR.slide_id,
    layout_pattern: slideIR.layout_pattern,
    elements_rendered: elements.length,
    canvas: canvasSize
  };
}

module.exports = { build };
