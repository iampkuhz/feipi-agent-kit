/**
 * 几何运算工具函数
 * 所有单位按 inch 处理，导出纯函数。
 */

'use strict';

/**
 * @typedef {Object} Rect
 * @property {number} x
 * @property {number} y
 * @property {number} w
 * @property {number} h
 */

/**
 * @param {Rect} rect
 */
function rectRight(rect) {
  return rect.x + rect.w;
}

/**
 * @param {Rect} rect
 */
function rectBottom(rect) {
  return rect.y + rect.h;
}

/**
 * @param {Rect} rect
 * @returns {{x: number, y: number}}
 */
function rectCenter(rect) {
  return { x: rect.x + rect.w / 2, y: rect.y + rect.h / 2 };
}

/**
 * 计算两个矩形的交集矩形，若无交集返回 null。
 * @param {Rect} a
 * @param {Rect} b
 * @returns {Rect|null}
 */
function rectIntersection(a, b) {
  const x = Math.max(a.x, b.x);
  const y = Math.max(a.y, b.y);
  const w = Math.min(rectRight(a), rectRight(b)) - x;
  const h = Math.min(rectBottom(a), rectBottom(b)) - y;
  if (w <= 0 || h <= 0) return null;
  return { x, y, w, h };
}

/**
 * 计算两个矩形的重叠面积，无重叠返回 0。
 * @param {Rect} a
 * @param {Rect} b
 * @returns {number}
 */
function rectOverlapArea(a, b) {
  const inter = rectIntersection(a, b);
  if (!inter) return 0;
  return inter.w * inter.h;
}

/**
 * 判断 container 是否包含 child（允许 tolerance 容差）。
 * @param {Rect} container
 * @param {Rect} child
 * @param {number} tolerance 容差，默认 0
 * @returns {boolean}
 */
function rectContains(container, child, tolerance) {
  const t = tolerance || 0;
  return (
    child.x >= container.x - t &&
    child.y >= container.y - t &&
    rectRight(child) <= rectRight(container) + t &&
    rectBottom(child) <= rectBottom(container) + t
  );
}

/**
 * 判断 rect 是否在 bounds 内（允许 tolerance 容差）。
 * @param {Rect} rect
 * @param {Rect} bounds
 * @param {number} tolerance
 * @returns {boolean}
 */
function rectWithinBounds(rect, bounds, tolerance) {
  return rectContains(bounds, rect, tolerance || 0);
}

/**
 * 计算两个矩形之间的最小间距（水平或垂直方向），
 * 若重叠返回 0。
 * @param {Rect} a
 * @param {Rect} b
 * @returns {number}
 */
function gapBetweenRects(a, b) {
  // 水平方向间距
  const hGap = Math.max(
    0,
    Math.max(a.x, b.x) - Math.min(rectRight(a), rectRight(b))
  );
  // 垂直方向间距
  const vGap = Math.max(
    0,
    Math.max(a.y, b.y) - Math.min(rectBottom(a), rectBottom(b))
  );
  // 若在某个方向有投影重叠，间距为另一方向的 gap
  // 若两个方向都有重叠（即真正相交），间距为 0
  const aRight = rectRight(a);
  const bRight = rectRight(b);
  const aBottom = rectBottom(a);
  const bBottom = rectBottom(b);

  const hOverlap = Math.max(0, Math.min(aRight, bRight) - Math.max(a.x, b.x));
  const vOverlap = Math.max(0, Math.min(aBottom, bBottom) - Math.max(a.y, b.y));

  if (hOverlap > 0 && vOverlap > 0) {
    return 0; // 重叠
  }
  if (hOverlap > 0) {
    return vGap;
  }
  if (vOverlap > 0) {
    return hGap;
  }
  // 完全分离，返回对角线最近距离的简化版本：取两个方向 gap 的较大值
  return Math.max(hGap, vGap);
}

/**
 * 从 element 提取 layout bounds（rect）。
 * 若 element 没有 x/y/w/h 返回 null。
 * @param {Object} element
 * @returns {Rect|null}
 */
function elementBounds(element) {
  const l = element.layout;
  if (!l || typeof l.x !== 'number' || typeof l.y !== 'number' ||
      typeof l.w !== 'number' || typeof l.h !== 'number') {
    return null;
  }
  return { x: l.x, y: l.y, w: l.w, h: l.h };
}

module.exports = {
  rectRight,
  rectBottom,
  rectCenter,
  rectIntersection,
  rectOverlapArea,
  rectContains,
  rectWithinBounds,
  gapBetweenRects,
  elementBounds
};
