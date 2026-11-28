/**
 * Capability Map Builder
 * 构建能力域分组图：Header + 能力域网格 + 域间关系 + Takeaway + Footer
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

  // 2. Main: capability map nodes
  const mainElements = groups['region_main'] || [];
  const connectors = mainElements.filter(e => e.kind === 'connector');
  const nodes = mainElements.filter(e => e.kind === 'component_node');
  const notes = mainElements.filter(e => e.kind === 'note');

  for (const conn of connectors) prim.addConnector(slide, conn, thm);
  for (const node of nodes) prim.addComponentNode(slide, node, thm);
  for (const note of notes) prim.addNote(slide, note, thm);

  // 3. Side panel / insight panel
  for (const elem of (groups['region_side'] || []).concat(groups['region_insight_panel'] || [])) {
    prim.addTextBox(slide, elem, thm);
  }

  // 4. Takeaway
  for (const elem of groups['region_takeaway'] || []) {
    prim.addTextBox(slide, elem, thm);
  }

  // 5. Footer
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
