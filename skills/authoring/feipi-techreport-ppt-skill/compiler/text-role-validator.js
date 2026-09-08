'use strict';

const { TokenStore } = require('./token-store');

const TEXT_KINDS = new Set(['text', 'component_node', 'note', 'footer_note', 'matrix', 'table', 'kpi_card', 'step_marker', 'legend']);

function validateResolvedTextRoles(renderPlan, options = {}) {
  const tokens = options.tokens || TokenStore.loadDefault();
  const errors = [];
  for (const element of renderPlan.elements || []) {
    if (!TEXT_KINDS.has(element.kind)) continue;
    const styles = [];
    if (element.resolved_style?.font_size_pt !== undefined) {
      styles.push({
        role: element.text_role,
        size: element.resolved_style.font_size_pt,
        token: element.resolved_style.font_size_token,
      });
    }
    for (const [slot, style] of Object.entries(element.resolved_style?.slot_styles || {})) {
      styles.push({ role: style.text_role, size: style.font_size_pt, token: style.font_size_token, slot });
    }
    if (styles.length === 0) {
      errors.push(`文本元素 ${element.id} 缺少 resolved text style`);
      continue;
    }
    for (const style of styles) {
      if (!style.role) {
        errors.push(`文本元素 ${element.id}${style.slot ? ` slot=${style.slot}` : ''} 缺少 text_role`);
        continue;
      }
      try {
        const expected = tokens.typographyRole(style.role);
        if (style.size !== expected.font_size_pt) {
          errors.push(`${element.id}/${style.role} 使用 ${style.size}pt，必须引用 token ${expected.font_size_pt}pt`);
        }
        tokens.assertRegisteredFontSize(style.size, `${element.id}/${style.role}`);
        tokens.assertRoleMinimum(style.role, style.size);
      } catch (error) {
        errors.push(error.message);
      }
    }
  }
  return { valid: errors.length === 0, errors };
}

module.exports = { validateResolvedTextRoles, TEXT_KINDS };
