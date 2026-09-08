/**
 * Design Kit Basic Validation — within-bounds, min-font, native-table 检查。
 */

'use strict';
const { TokenStore } = require('../../compiler/token-store');
const tokens = TokenStore.loadDefault();

/**
 * 对渲染后的元素执行 basic 级验证。
 * @param {Object} spec - slide spec (含 components)
 * @param {Array<Object>} renderedElements - 渲染记录 [{ type, x, y, w, h, fontSizes, isNativeTable }]
 * @param {Object} designKit - kit-loader 返回
 * @returns {{ passed: boolean, failures: string[], warnings: string[] }}
 */
function validateSlide(spec, renderedElements, designKit) {
  const pageW = spec._pageWidth || tokens.resolve('spacing.canvas.width_in');
  const pageH = spec._pageHeight || tokens.resolve('spacing.canvas.height_in');
  const safeMargin = tokens.resolve('spacing.page.margin_in');

  const failures = [];
  const warnings = [];

  for (const el of renderedElements) {
    // --- within-bounds ---
    if (el.x !== undefined) {
      if (el.x < -0.001) {
        failures.push(`within-bounds: ${el.type} x=${el.x} < 0`);
      }
      if (el.x + el.w > pageW + 0.001) {
        failures.push(`within-bounds: ${el.type} x+w=${(el.x + el.w).toFixed(2)} > ${pageW}`);
      }
      if (el.y < -0.001) {
        failures.push(`within-bounds: ${el.type} y=${el.y} < 0`);
      }
      if (el.y + el.h > pageH + 0.001) {
        failures.push(`within-bounds: ${el.type} y+h=${(el.y + el.h).toFixed(2)} > ${pageH}`);
      }
    }

    // --- min-font ---
    if (el.fontSizes && el.fontSizes.length > 0) {
      for (const fs of el.fontSizes) {
        try {
          const role = el.text_role || 'body';
          tokens.assertRegisteredFontSize(fs, `${el.type}/${role}`);
          tokens.assertRoleMinimum(role, fs);
        } catch (error) { failures.push(error.message); }
      }
    }

    // --- native-table ---
    if (el.type === 'native-table' && !el.isNativeTable) {
      failures.push('native-table: 表格未使用原生 table（可能被渲染为图片）');
    }

    // --- safe-margin ---
    if (el.x !== undefined) {
      if (el.x < safeMargin - 0.001) {
        warnings.push(`safe-margin: ${el.type} 左边界 ${el.x.toFixed(2)} < ${safeMargin}`);
      }
      if (el.x + el.w > pageW - safeMargin + 0.001) {
        warnings.push(`safe-margin: ${el.type} 右边界 ${(el.x + el.w).toFixed(2)} > ${pageW - safeMargin}`);
      }
    }
  }

  return {
    passed: failures.length === 0,
    failures,
    warnings
  };
}

/**
 * 收集渲染元素记录的 helper。
 */
function createRenderTracker() {
  const elements = [];
  return {
    record(entry) {
      elements.push(entry);
    },
    getAll() {
      return [...elements];
    }
  };
}

module.exports = {
  validateSlide,
  createRenderTracker
};
