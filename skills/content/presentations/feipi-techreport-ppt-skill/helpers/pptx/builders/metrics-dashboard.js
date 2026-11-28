/**
 * Metrics Dashboard Builder
 * 构建指标仪表板：Header + KPI 卡片行 + 主图区域 + Takeaway + Footer
 */
'use strict';

const prim = require('../primitives');

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

  // 2. KPI cards row
  for (const elem of groups['region_kpi_row'] || []) {
    if (elem.kind === 'kpi_card') {
      prim.addKpiCard(slide, elem, thm);
    } else {
      prim.addTextBox(slide, elem, thm);
    }
  }

  // 3. Main visual (chart/summary area)
  const mainElements = groups['region_main'] || [];
  const notes = mainElements.filter(e => e.kind === 'note');
  const nodes = mainElements.filter(e => e.kind === 'component_node');
  for (const node of nodes) prim.addComponentNode(slide, node, thm);
  for (const note of notes) prim.addNote(slide, note, thm);

  // Also handle KPI cards in main region if not in kpi_row
  const kpisInMain = mainElements.filter(e => e.kind === 'kpi_card');
  for (const kpi of kpisInMain) prim.addKpiCard(slide, kpi, thm);

  // 4. Evidence zone
  for (const elem of groups['region_evidence_zone'] || []) {
    prim.addTextBox(slide, elem, thm);
  }

  // 5. Takeaway
  for (const elem of groups['region_takeaway'] || []) {
    prim.addTextBox(slide, elem, thm);
  }

  // 6. Footer
  for (const elem of groups['region_footer'] || []) {
    prim.addFooterNote(slide, elem, thm);
  }

  return {
    slide_id: slideIR.slide_id,
    layout_pattern: slideIR.layout_pattern,
    elements_rendered: elements.length,
    canvas: canvasSize,
  };
}

module.exports = { build };
