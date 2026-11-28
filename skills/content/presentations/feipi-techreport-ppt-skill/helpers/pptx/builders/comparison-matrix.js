/**
 * Comparison Matrix Builder
 * 构建对比矩阵页面：Header + KPI cards + 矩阵 + 洞察面板 + Takeaway + Footer
 */

'use strict';

const prim = require('../primitives');

function sortByPriority(elements) {
  return [...elements].sort((a, b) => {
    const pA = (a.constraints && a.constraints.priority) || 'medium';
    const pB = (b.constraints && b.constraints.priority) || 'medium';
    const order = { critical: 0, high: 1, medium: 2, low: 3 };
    return (order[pA] || 2) - (order[pB] || 2);
  });
}

function groupByRegion(elements) {
  const groups = {};
  for (const e of elements) {
    const rid = e.region_id || 'unknown';
    if (!groups[rid]) groups[rid] = [];
    groups[rid].push(e);
  }
  return groups;
}

function build(pres, slideIR, thm) {
  const canvasSize = thm.getCanvasSize(slideIR.canvas);
  const slide = pres.addSlide();
  const elements = slideIR.elements || [];
  const groups = groupByRegion(elements);

  slide.background = { color: thm.COLORS.white };

  // 1. Header
  for (const elem of groups['region_header'] || []) {
    prim.addTextBox(slide, elem, thm);
  }

  // 2. KPI cards 行
  for (const elem of sortByPriority(groups['region_kpi'] || [])) {
    if (elem.kind === 'kpi_card') {
      prim.addKpiCard(slide, elem, thm);
    } else {
      prim.addTextBox(slide, elem, thm);
    }
  }

  // 3. 矩阵（主内容）
  const matrixElements = groups['region_matrix'] || [];
  for (const elem of sortByPriority(matrixElements)) {
    if (elem.kind === 'matrix' || elem.kind === 'table') {
      prim.addMatrix(slide, elem, thm);
    } else {
      prim.addTextBox(slide, elem, thm);
    }
  }

  // 4. 洞察面板
  for (const elem of sortByPriority(groups['region_insight'] || [])) {
    if (elem.kind === 'note') {
      prim.addNote(slide, elem, thm);
    } else {
      prim.addTextBox(slide, elem, thm);
    }
  }

  // 5. 证据区（通用）
  for (const elem of sortByPriority(groups['region_evidence'] || [])) {
    if (elem.kind === 'matrix') {
      prim.addMatrix(slide, elem, thm);
    } else {
      prim.addNote(slide, elem, thm);
    }
  }

  // 6. Takeaway
  for (const elem of groups['region_takeaway'] || []) {
    prim.addTextBox(slide, elem, thm);
  }

  // 7. Footer
  for (const elem of groups['region_footer'] || []) {
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
