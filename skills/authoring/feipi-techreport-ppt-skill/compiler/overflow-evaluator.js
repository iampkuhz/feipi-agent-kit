'use strict';

const ORDERED_OVERFLOW_STATES = Object.freeze([
  'compress_text',
  'change_component_size',
  'change_layout',
  'drop_secondary',
  'split_required',
]);

function extractText(content) {
  if (typeof content === 'string') return content;
  if (!content || typeof content !== 'object') return '';
  const values = [];
  for (const value of Object.values(content)) {
    if (typeof value === 'string') values.push(value);
    if (Array.isArray(value)) {
      for (const item of value.flat(2)) if (typeof item === 'string') values.push(item);
    }
  }
  return values.join('\n');
}

function evaluateOverflow(renderPlan) {
  const issues = [];
  for (const element of renderPlan.elements || []) {
    if (element.kind === 'connector') continue;
    const text = extractText(element.content);
    if (!text) continue;
    const widthIn = element.bounds_emu.w / 914400;
    const heightIn = element.bounds_emu.h / 914400;
    const fontSize = element.resolved_style?.font_size_pt;
    if (typeof fontSize !== 'number') throw new Error(`元素 ${element.id} 缺少 resolved font size`);
    const estimatedCharsPerLine = Math.max(4, Math.floor(widthIn * 72 / (fontSize * 0.95)));
    const explicitLines = text.split(/\n/).length;
    const wrappedLines = Math.ceil(text.replace(/\n/g, '').length / estimatedCharsPerLine);
    const lines = Math.max(explicitLines, wrappedLines);
    const requiredHeight = lines * (fontSize / 72) * 1.35;
    if (requiredHeight > heightIn * 1.05) {
      issues.push({
        element_id: element.id,
        type: 'text_overflow',
        estimated_height_in: Number(requiredHeight.toFixed(3)),
        available_height_in: Number(heightIn.toFixed(3)),
      });
    }
  }
  return issues.length === 0
    ? { status: 'fit', issues: [], next_actions: [] }
    : { status: 'compress_text', issues, next_actions: [...ORDERED_OVERFLOW_STATES] };
}

module.exports = { evaluateOverflow, ORDERED_OVERFLOW_STATES };
