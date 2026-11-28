/**
 * 保守网格布局工具。
 * 为 KPI cards、bullets、flow steps 等生成等距排列坐标。
 */
'use strict';

/**
 * 在给定区域内生成等间距的垂直布局。
 * 返回每个元素的 { x, y, w, h }。
 */
function verticalStack(region, items, options = {}) {
  const {
    padding = 0.1,
    gap = 0.08,
    itemHeight = null,
    itemWidth = null,
    minHeight = 0.3,
  } = options;

  const bounds = region.bounds || { x: 0, y: 0, w: 4, h: 4 };
  const count = items.length;
  if (count === 0) return [];

  const usableW = bounds.w - 2 * padding;
  const usableH = bounds.h - 2 * padding;
  const startX = bounds.x + padding;
  const startY = bounds.y + padding;

  const actualW = itemWidth || usableW;
  let actualH;
  if (itemHeight) {
    actualH = itemHeight;
  } else {
    actualH = (usableH - (count - 1) * gap) / count;
    if (actualH < minHeight) actualH = minHeight;
  }

  return items.map((item, i) => ({
    element_id: item.id,
    x: startX,
    y: startY + i * (actualH + gap),
    w: actualW,
    h: actualH,
  }));
}

/**
 * 在给定区域内生成网格布局（如 KPI cards）。
 */
function grid(region, items, options = {}) {
  const {
    padding = 0.1,
    colGap = 0.1,
    rowGap = 0.1,
    cols = null,
    minCardWidth = 1.0,
    minCardHeight = 0.4,
  } = options;

  const bounds = region.bounds || { x: 0, y: 0, w: 8, h: 4 };
  const count = items.length;
  if (count === 0) return [];

  const usableW = bounds.w - 2 * padding;
  const usableH = bounds.h - 2 * padding;

  // Determine columns
  let actualCols = cols || Math.floor(usableW / (minCardWidth + colGap));
  if (actualCols < 1) actualCols = 1;
  if (actualCols > count) actualCols = count;

  const rows = Math.ceil(count / actualCols);
  const cardW = (usableW - (actualCols - 1) * colGap) / actualCols;
  const cardH = (usableH - (rows - 1) * rowGap) / rows;

  return items.map((item, i) => {
    const col = i % actualCols;
    const row = Math.floor(i / actualCols);
    return {
      element_id: item.id,
      x: bounds.x + padding + col * (cardW + colGap),
      y: bounds.y + padding + row * (cardH + rowGap),
      w: cardW,
      h: cardH,
    };
  });
}

/**
 * 水平等距排列（如流程步骤）。
 */
function horizontalFlow(region, items, options = {}) {
  const {
    padding = 0.1,
    gap = 0.15,
    itemWidth = null,
    itemHeight = null,
  } = options;

  const bounds = region.bounds || { x: 0, y: 0, w: 8, h: 2 };
  const count = items.length;
  if (count === 0) return [];

  const usableW = bounds.w - 2 * padding;
  let actualW;
  if (itemWidth) {
    actualW = itemWidth;
  } else {
    actualW = (usableW - (count - 1) * gap) / count;
  }
  const actualH = itemHeight || (bounds.h - 2 * padding);
  const startX = bounds.x + padding;
  const startY = bounds.y + padding;

  return items.map((item, i) => ({
    element_id: item.id,
    x: startX + i * (actualW + gap),
    y: startY,
    w: actualW,
    h: actualH,
  }));
}

module.exports = { verticalStack, grid, horizontalFlow };
