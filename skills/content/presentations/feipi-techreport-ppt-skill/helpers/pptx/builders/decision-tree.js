/**
 * Decision Tree Builder
 * 构建树/判断分支：Header + 决策节点 + 分支连接 + Takeaway + Footer
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

  // 2. Main: decision tree nodes and connectors
  const mainElements = groups['region_main'] || [];
  const connectors = mainElements.filter(e => e.kind === 'connector');
  const nodes = mainElements.filter(e => e.kind === 'component_node');
  const steps = mainElements.filter(e => e.kind === 'step_marker');
  const notes = mainElements.filter(e => e.kind === 'note');

  // Connectors first (behind nodes)
  for (const conn of connectors) prim.addConnector(slide, conn, thm);
  for (const node of nodes) prim.addComponentNode(slide, node, thm);
  for (const step of steps) prim.addStepMarker(slide, step, thm);
  for (const note of notes) prim.addNote(slide, note, thm);

  // 3. Side panel
  for (const elem of groups['region_side'] || []) {
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
