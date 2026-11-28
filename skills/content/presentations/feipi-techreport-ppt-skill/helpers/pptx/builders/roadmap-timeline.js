/**
 * Roadmap Timeline Builder
 * 构建技术交付路线图：Header + 时间轴/阶段 + 里程碑 + Takeaway + Footer
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

  // 2. Main: roadmap steps
  const mainElements = groups['region_main'] || [];
  const steps = mainElements.filter(e => e.kind === 'step_marker');
  const connectors = mainElements.filter(e => e.kind === 'connector');
  const nodes = mainElements.filter(e => e.kind === 'component_node');
  const notes = mainElements.filter(e => e.kind === 'note');

  // Draw timeline line (horizontal connector between first and last step)
  if (steps.length >= 2 && thm) {
    const first = steps[0];
    const last = steps[steps.length - 1];
    const firstLayout = first.layout || {};
    const lastLayout = last.layout || {};
    const midY = ((firstLayout.y || 0) + (firstLayout.h || 0) / 2);
    try {
      slide.addShape('line', {
        x: firstLayout.x || 0,
        y: midY,
        w: (lastLayout.x || 0) - (firstLayout.x || 0),
        h: 0,
        line: { color: thm.COLORS.border, width: 1.5 },
      });
    } catch {
      // Graceful fallback
    }
  }

  for (const conn of connectors) prim.addConnector(slide, conn, thm);
  for (const step of steps) prim.addStepMarker(slide, step, thm);
  for (const node of nodes) prim.addComponentNode(slide, node, thm);
  for (const note of notes) prim.addNote(slide, note, thm);

  // 3. Side panel
  for (const elem of groups['region_side'] || []) {
    prim.addTextBox(slide, elem, thm);
  }

  // 4. KPI row
  for (const elem of groups['region_kpi_row'] || []) {
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
