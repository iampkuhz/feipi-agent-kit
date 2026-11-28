/**
 * Move Label — 标签轻微位移，避开节点。
 * 处理 Static QA 的 semantic_overlap 中 label_near_node / label_overlap_node。
 */
'use strict';

const OVERLAP_TOLERANCE = 0.08; // inch

/**
 * 检测两个矩形是否重叠。
 */
function overlaps(a, b) {
  return !(a.x + a.w <= b.x || b.x + b.w <= a.x || a.y + a.h <= b.y || b.y + b.h <= a.y);
}

/**
 * 尝试将 label 元素轻微移开，使其不与任何 target 元素重叠。
 * @param {Object} labelElem - label 元素
 * @param {Object[]} targetElems - 目标节点元素
 * @param {Object} regionBounds - region 边界
 * @returns {{success: boolean, new_layout: Object|null, moves: Array}}
 */
function moveLabel(labelElem, targetElems, regionBounds) {
  const labelLayout = labelElem.layout || {};
  let current = {
    x: labelLayout.x || 0,
    y: labelLayout.y || 0,
    w: labelLayout.w || 1,
    h: labelLayout.h || 0.3
  };

  // 检查是否与任何 target 重叠
  const conflicting = targetElems.filter(t => {
    const tLayout = t.layout || {};
    return overlaps(current, { x: tLayout.x || 0, y: tLayout.y || 0, w: tLayout.w || 1, h: tLayout.h || 0.5 });
  });

  if (conflicting.length === 0) {
    return { success: true, new_layout: null, moves: [] };
  }

  // 尝试 4 个方向的微移
  const candidates = [
    { dx: 0, dy: -OVERLAP_TOLERANCE * 2 }, // up
    { dx: 0, dy: OVERLAP_TOLERANCE * 2 },  // down
    { dx: -OVERLAP_TOLERANCE * 2, dy: 0 }, // left
    { dx: OVERLAP_TOLERANCE * 2, dy: 0 },  // right
  ];

  for (const c of candidates) {
    const proposed = {
      x: current.x + c.dx,
      y: current.y + c.dy,
      w: current.w,
      h: current.h
    };

    // 检查是否在 region 内
    if (regionBounds) {
      if (proposed.x < (regionBounds.x || 0) ||
          proposed.y < (regionBounds.y || 0) ||
          proposed.x + proposed.w > (regionBounds.x || 0) + (regionBounds.w || 10) ||
          proposed.y + proposed.h > (regionBounds.y || 0) + (regionBounds.h || 10)) {
        continue;
      }
    }

    // 检查是否仍与任何 target 重叠
    const stillConflicting = targetElems.some(t => {
      const tLayout = t.layout || {};
      return overlaps(proposed, { x: tLayout.x || 0, y: tLayout.y || 0, w: tLayout.w || 1, h: tLayout.h || 0.5 });
    });

    if (!stillConflicting) {
      return {
        success: true,
        new_layout: proposed,
        moves: [{ from: { x: current.x, y: current.y }, to: proposed }]
      };
    }
  }

  return { success: false, new_layout: null, moves: [], message: '无法通过微移解决重叠' };
}

module.exports = { moveLabel };
