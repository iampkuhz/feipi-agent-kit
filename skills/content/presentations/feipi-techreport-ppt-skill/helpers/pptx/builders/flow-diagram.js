/**
 * Flow Diagram Builder
 * 构建流程图页面：Header + 流程图 + 证据区 + Takeaway + Footer
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

  // 2. 主视觉区：流程节点 + 连接线 + 步骤标记
  const mainElements = groups['region_main'] || [];
  const connectors = mainElements.filter(e => e.kind === 'connector');
  const steps = mainElements.filter(e => e.kind === 'component_node');
  const markers = mainElements.filter(e => e.kind === 'step_marker');
  const others = mainElements.filter(e => !['connector', 'component_node', 'step_marker'].includes(e.kind));

  // 连接线（底层）
  for (const conn of sortByPriority(connectors)) {
    prim.addConnector(slide, conn, thm);
  }

  // 流程节点
  for (const step of sortByPriority(steps)) {
    prim.addComponentNode(slide, step, thm);
  }

  // 步骤标记
  for (const marker of sortByPriority(markers)) {
    prim.addStepMarker(slide, marker, thm);
  }

  // 其他
  for (const elem of sortByPriority(others)) {
    prim.addTextBox(slide, elem, thm);
  }

  // 3. 证据区（输入输出说明）
  for (const elem of sortByPriority(groups['region_evidence'] || [])) {
    prim.addNote(slide, elem, thm);
  }

  // 4. KPI 行（如果有）
  for (const elem of sortByPriority(groups['region_kpi'] || [])) {
    if (elem.kind === 'kpi_card') {
      prim.addKpiCard(slide, elem, thm);
    } else {
      prim.addTextBox(slide, elem, thm);
    }
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
    canvas: canvasSize
  };
}

module.exports = { build };
