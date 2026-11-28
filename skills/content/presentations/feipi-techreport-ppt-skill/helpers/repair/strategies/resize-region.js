/**
 * Resize Region — 越界元素拉回 region 内，调整区域大小。
 * 处理 Static QA 的 out_of_bounds / out_of_region。
 */
'use strict';

/**
 * 将元素约束到 region 边界内。
 * @param {Object} element - 元素
 * @param {Object} regionBounds - region 边界 {x, y, w, h}
 * @returns {{success: boolean, new_layout: Object|null, action: string|null}}
 */
function clampToRegion(element, regionBounds) {
  if (!regionBounds) return { success: false, new_layout: null, action: null, message: '无 region 边界信息' };

  const layout = element.layout || {};
  const current = {
    x: layout.x || 0,
    y: layout.y || 0,
    w: layout.w || 1,
    h: layout.h || 0.3
  };

  const r = { x: regionBounds.x || 0, y: regionBounds.y || 0, w: regionBounds.w || 10, h: regionBounds.h || 7 };

  // 如果元素已经在 region 内，不需要操作
  if (current.x >= r.x && current.y >= r.y &&
      current.x + current.w <= r.x + r.w &&
      current.y + current.h <= r.y + r.h) {
    return { success: true, new_layout: null, action: 'already_in_region' };
  }

  // Clamp: 将元素移到 region 内
  const clamped = {
    x: Math.max(r.x, current.x),
    y: Math.max(r.y, current.y),
    w: Math.min(current.w, r.w - (Math.max(r.x, current.x) - r.x)),
    h: Math.min(current.h, r.h - (Math.max(r.y, current.y) - r.y))
  };

  // 如果压缩后尺寸过小，标记为不可修复
  if (clamped.w < 0.2 || clamped.h < 0.1) {
    return { success: false, new_layout: null, action: 'too_small_after_clamp', message: '元素约束后尺寸过小，需要用户决策' };
  }

  return {
    success: true,
    new_layout: clamped,
    action: 'clamped_to_region'
  };
}

/**
 * 调整 region 边界以适应元素。
 * @param {Object} region - region 定义
 * @param {Object[]} elements - 该区域内的元素
 * @returns {{success: boolean, new_bounds: Object|null}}
 */
function expandRegionForElements(region, elements) {
  const bounds = region.bounds || {};
  let maxX = (bounds.x || 0) + (bounds.w || 0);
  let maxY = (bounds.y || 0) + (bounds.h || 0);

  for (const e of elements) {
    const l = e.layout || {};
    const ex = (l.x || 0) + (l.w || 0);
    const ey = (l.y || 0) + (l.h || 0);
    if (ex > maxX) maxX = ex;
    if (ey > maxY) maxY = ey;
  }

  const newW = maxX - (bounds.x || 0);
  const newH = maxY - (bounds.y || 0);

  if (newW <= (bounds.w || 0) && newH <= (bounds.h || 0)) {
    return { success: true, new_bounds: null };
  }

  return {
    success: true,
    new_bounds: { x: bounds.x || 0, y: bounds.y || 0, w: newW, h: newH }
  };
}

module.exports = { clampToRegion, expandRegionForElements };
