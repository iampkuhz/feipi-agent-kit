/**
 * 保守布局求解器。
 * 输入 normalized Slide IR，输出 solved Slide IR。
 * 不会破坏已有明确 bounds 的元素。
 */
'use strict';

const { verticalStack, grid, horizontalFlow } = require('./grid');
const { estimateTextFit } = require('./text-measure');
const { normalize } = require('../ir/normalize');

/**
 * 对缺少 bounds 的元素自动分配坐标。
 */
function solveLayout(ir) {
  // First normalize if not already normalized
  const solved = { ...ir };
  if (!solved.canvas) {
    Object.assign(solved, normalize(ir));
  }

  const canvasW = solved.canvas?.width_in || 13.33;
  const canvasH = solved.canvas?.height_in || 7.5;

  solved.elements = solved.elements.map(el => {
    const ne = { ...el };

    // If element already has full bounds, keep it
    if (ne.layout && ne.layout.x !== undefined && ne.layout.y !== undefined &&
        ne.layout.w !== undefined && ne.layout.h !== undefined) {
      // Check if within canvas
      if (ne.layout.x + ne.layout.w <= canvasW + 0.1 &&
          ne.layout.y + ne.layout.h <= canvasH + 0.1) {
        return ne;
      }
    }

    // Find the region
    const region = (solved.regions || []).find(r => r.id === ne.region_id);
    if (!region) return ne;

    // Auto-generate bounds based on element kind
    const bounds = generateBounds(ne, region, solved);
    ne.layout = { ...(ne.layout || {}), ...bounds };
    return ne;
  });

  return solved;
}

/**
 * 根据元素类型和所属区域生成 bounds。
 */
function generateBounds(element, region, ir) {
  const rb = region.bounds || { x: 0, y: 0, w: 4, h: 4 };

  switch (element.kind) {
    case 'text':
      if (element.semantic_role === 'title') {
        return {
          x: rb.x + 0.1,
          y: rb.y + 0.1,
          w: rb.w - 0.2,
          h: 0.4,
          position_hint: element.layout?.position_hint || 'header-top',
        };
      }
      if (element.semantic_role === 'subtitle') {
        return {
          x: rb.x + 0.1,
          y: rb.y + 0.5,
          w: rb.w - 0.2,
          h: 0.3,
          position_hint: element.layout?.position_hint || 'header-bottom',
        };
      }
      if (element.semantic_role === 'takeaway') {
        return {
          x: rb.x + 0.1,
          y: rb.y + 0.05,
          w: rb.w - 0.2,
          h: 0.3,
          alignment: 'center',
        };
      }
      // Default text
      return {
        x: rb.x + 0.1,
        y: rb.y + 0.1,
        w: rb.w - 0.2,
        h: 0.5,
      };

    case 'component_node': {
      // Find position among siblings in same region
      const regionEls = ir.elements.filter(e => e.region_id === element.region_id && e.kind === 'component_node');
      const idx = regionEls.findIndex(e => e.id === element.id);
      const count = regionEls.length;
      if (count <= 0) return {};

      const margin = 0.15;
      const usableW = rb.w - 2 * margin;
      const nodeW = Math.min(usableW / count, 2.5);
      const gap = (usableW - nodeW * count) / Math.max(count - 1, 1);

      return {
        x: rb.x + margin + idx * (nodeW + gap),
        y: rb.y + 0.2,
        w: nodeW,
        h: 0.8,
      };
    }

    case 'step_marker': {
      const steps = ir.elements.filter(e => e.region_id === element.region_id && e.kind === 'step_marker');
      const idx = steps.findIndex(e => e.id === element.id);
      const count = steps.length;
      if (count <= 0) return {};

      const margin = 0.15;
      const usableW = rb.w - 2 * margin;
      const stepW = Math.min(usableW / count, 2.0);
      const gap = (usableW - stepW * count) / Math.max(count - 1, 1);

      return {
        x: rb.x + margin + idx * (stepW + gap),
        y: rb.y + 0.2,
        w: stepW,
        h: 0.8,
      };
    }

    case 'connector':
      // Connectors don't need explicit bounds
      return {};

    case 'kpi_card': {
      const kpis = ir.elements.filter(e => e.region_id === element.region_id && e.kind === 'kpi_card');
      const idx = kpis.findIndex(e => e.id === element.id);
      const count = kpis.length;
      if (count <= 0) return {};

      const margin = 0.1;
      const usableW = rb.w - 2 * margin;
      const cardW = Math.min(usableW / count, 2.0);
      const gap = (usableW - cardW * count) / Math.max(count - 1, 1);

      return {
        x: rb.x + margin + idx * (cardW + gap),
        y: rb.y + 0.1,
        w: cardW,
        h: 0.5,
      };
    }

    case 'note':
    case 'footer_note': {
      const notes = ir.elements.filter(e =>
        e.region_id === element.region_id &&
        (e.kind === 'note' || e.kind === 'footer_note')
      );
      const idx = notes.findIndex(e => e.id === element.id);
      const count = notes.length;
      if (count <= 0) return {};

      const margin = 0.1;
      const usableH = rb.h - 2 * margin;
      const noteH = Math.min(usableH / count, 1.0);
      const gap = (usableH - noteH * count) / Math.max(count - 1, 1);

      return {
        x: rb.x + margin,
        y: rb.y + margin + idx * (noteH + gap),
        w: rb.w - 2 * margin,
        h: noteH,
      };
    }

    case 'matrix':
    case 'table':
      return {
        x: rb.x + 0.1,
        y: rb.y + 0.1,
        w: rb.w - 0.2,
        h: rb.h - 0.2,
      };

    default:
      return {
        x: rb.x + 0.1,
        y: rb.y + 0.1,
        w: rb.w - 0.2,
        h: 0.5,
      };
  }
}

module.exports = { solveLayout, generateBounds };
