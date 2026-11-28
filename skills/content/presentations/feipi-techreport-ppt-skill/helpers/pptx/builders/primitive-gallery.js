/**
 * Primitive Gallery Builder
 * 生成所有原子组件的测试页，用于回归验证。
 * 不追求业务叙事，只验证组件结构正确性。
 */

'use strict';

const prim = require('../primitives');

function build(pres, slideIR, thm) {
  const canvasSize = thm.getCanvasSize(slideIR.canvas);
  const slide = pres.addSlide();
  const elements = slideIR.elements || [];

  slide.background = { color: thm.COLORS.white };

  // 按 kind 路由调用对应 primitive
  for (const elem of elements) {
    const layout = prim.extractLayout(elem);

    // Skip elements without coords in production (let solver handle them)
    if (!layout.hasCoords) {
      continue;
    }

    switch (elem.kind) {
      case 'text':
        prim.addTextBox(slide, elem, thm);
        break;

      case 'kpi_card':
        prim.addKpiCard(slide, elem, thm);
        break;

      case 'note':
        prim.addNote(slide, elem, thm);
        break;

      case 'footer_note':
        prim.addFooterNote(slide, elem, thm);
        break;

      case 'matrix':
      case 'table':
        prim.addMatrix(slide, elem, thm);
        break;

      case 'component_node':
        prim.addComponentNode(slide, elem, thm);
        break;

      case 'badge':
      case 'label':
        prim.addNote(slide, { ...elem, kind: 'note' }, thm); // Badge uses note primitive as fallback
        break;

      case 'connector':
        prim.addConnector(slide, elem, thm);
        break;

      case 'step_marker':
        prim.addStepMarker(slide, elem, thm);
        break;

      default:
        // Unknown kind — skip silently
        break;
    }
  }

  const renderedCount = elements.filter(e => {
    const l = prim.extractLayout(e);
    return l.hasCoords && ['text', 'kpi_card', 'note', 'footer_note', 'matrix', 'table', 'component_node', 'badge', 'label', 'connector', 'step_marker'].includes(e.kind);
  }).length;

  return {
    slide_count: 1,
    elements_rendered: renderedCount,
    layout_pattern: slideIR.layout_pattern,
    errors: []
  };
}

module.exports = { build };
