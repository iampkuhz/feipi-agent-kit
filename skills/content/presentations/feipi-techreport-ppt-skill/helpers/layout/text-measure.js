/**
 * 保守文本测量。
 * 不依赖 canvas / native fonts，基于字符宽度估算。
 */
'use strict';
const { TokenStore } = require('../../compiler/token-store');
const tokens = TokenStore.loadDefault();

// 中文字符宽度约等于字号（全角），英文字符约 0.55 倍字号（等宽近似）
// 以下为保守估算值，实际渲染可能略有差异

function charWidthForLang(ch, fontSizePt) {
  // CJK 字符
  if (/[一-鿿㐀-䶿\u{20000}-\u{2a6df}\u{2a700}-\u{2ebef}　-〿＀-￯]/u.test(ch)) {
    return fontSizePt * 1.0;
  }
  // Latin alphanumeric, common punctuation
  if (/[a-zA-Z0-9 .,;:!?'"()\-+/\\@#$%^&*<>_~`[\]{}|]/.test(ch)) {
    return fontSizePt * 0.55;
  }
  // Default: assume half-width
  return fontSizePt * 0.6;
}

function estimateLineWidth(text, fontSizePt) {
  if (!text || !fontSizePt) return 0;
  let maxW = 0;
  for (const line of text.split('\n')) {
    let w = 0;
    for (const ch of line) {
      w += charWidthForLang(ch, fontSizePt);
    }
    if (w > maxW) maxW = w;
  }
  return maxW;
}

/**
 * 估算给定文本在指定宽度下需要的行数和高度。
 * 返回 { lines, totalHeight, fitStatus, lineCount }
 */
function estimateTextFit(text, fontSizePt, containerWidthIn, lineHeight = 1.2, minFontPt = null) {
  if (!text) return { lines: 0, totalHeight: 0, fitStatus: 'fit', lineCount: 0 };

  const ptPerIn = 72;
  const containerWidthPt = containerWidthIn * ptPerIn;

  const lines = [];
  for (const rawLine of text.split('\n')) {
    // If a single line fits, keep it
    if (estimateLineWidth(rawLine, fontSizePt) <= containerWidthPt) {
      lines.push(rawLine);
      continue;
    }
    // Break long lines into words/chunks
    const words = rawLine.split(/(\s+)/).filter(Boolean);
    let currentLine = '';
    for (const word of words) {
      const testLine = currentLine ? currentLine + word : word;
      if (estimateLineWidth(testLine, fontSizePt) <= containerWidthPt) {
        currentLine = testLine;
      } else {
        if (currentLine) lines.push(currentLine);
        currentLine = word;
      }
    }
    if (currentLine) lines.push(currentLine);
  }

  const lineCount = lines.length;
  const totalHeight = lineCount * fontSizePt * lineHeight;
  const totalWidth = Math.max(...lines.map(l => estimateLineWidth(l, fontSizePt)));

  let fitStatus = 'fit';
  if (totalWidth > containerWidthPt * 1.3 || lineCount > 8) {
    fitStatus = 'overflow';
  } else if (totalWidth > containerWidthPt || lineCount > 5) {
    fitStatus = 'shrink_needed';
  }

  return {
    lines,
    lineCount,
    totalHeight,
    totalWidth: totalWidth / ptPerIn,
    fitStatus,
  };
}

/**
 * 检查元素文本是否适配其布局边界。
 */
function checkElementFit(element) {
  const layout = element.layout || {};
  if (!layout.w || !layout.h) return { fitStatus: 'unknown', reason: '缺少布局尺寸' };

  const role = element.text_role || 'body';
  const fontSizePt = element.style?.font_size_pt ?? tokens.typographyRole(role).font_size_pt;
  const text = typeof element.content === 'string'
    ? element.content
    : (element.content?.label || element.content?.text || '');

  const result = estimateTextFit(text, fontSizePt, layout.w, 1.2);
  result.element_id = element.id;
  result.overflows_height = result.totalHeight / 72 > layout.h;

  return result;
}

module.exports = {
  estimateLineWidth,
  estimateTextFit,
  checkElementFit,
  charWidthForLang,
};
