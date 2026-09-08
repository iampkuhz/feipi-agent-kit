/**
 * PptxGenJS 兼容主题视图。
 * 所有数值均从 design-system/tokens 读取；本文件不再维护视觉值。
 */
'use strict';

const { TokenStore } = require('../../compiler/token-store');
const { loadDefaultStyleLock, resolveStyleLock } = require('../style/style-lock');

const tokens = TokenStore.loadDefault();
const typography = tokens.documents.typography;

const COLORS = Object.freeze({
  navy: tokens.color('text.primary'),
  blue: tokens.color('brand.secondary'),
  green: tokens.color('semantic.success'),
  orange: tokens.color('semantic.warning'),
  red: tokens.color('semantic.danger'),
  gray: tokens.color('text.secondary'),
  border: tokens.color('border.default'),
  pale: tokens.color('surface.panel'),
  paleBlue: tokens.color('surface.panel_blue'),
  paleOrange: tokens.color('surface.panel_orange'),
  paleRed: tokens.color('surface.panel_red'),
  paleGreen: tokens.color('surface.panel_green'),
  white: tokens.color('surface.page'),
  black: tokens.color('text.primary'),
});

const FONT_SIZES = Object.freeze({
  title: typography.sizes_pt.title,
  subtitle: typography.sizes_pt.subtitle,
  regionTitle: typography.sizes_pt.section_title,
  body: typography.sizes_pt.body,
  label: typography.sizes_pt.label,
  caption: typography.sizes_pt.caption,
  takeaway: typography.sizes_pt.section_title,
  footer: typography.sizes_pt.footer,
  kpiValue: typography.sizes_pt.kpi_value,
  kpiLabel: typography.sizes_pt.kpi_label,
  tableHeader: typography.sizes_pt.table_header,
  tableCell: typography.sizes_pt.table_cell,
  stepMarker: typography.sizes_pt.diagram_badge,
});

const FONT_FACES = Object.freeze(typography.font_families);
const CANVAS_PRESETS = Object.freeze({ wide_16_9: Object.freeze({ ...tokens.documents.spacing.canvas }) });

function resolveFontFace(family = 'default') { return tokens.fontFace(family); }

function getCanvasSize(canvas) {
  if (canvas?.width_in && canvas?.height_in) return { width_in: canvas.width_in, height_in: canvas.height_in };
  return { width_in: tokens.documents.spacing.canvas.width_in, height_in: tokens.documents.spacing.canvas.height_in };
}

function textColorForRole(role, isHighlighted) {
  if (isHighlighted) return COLORS.blue;
  if (role === 'risk') return COLORS.red;
  if (role === 'takeaway') return COLORS.blue;
  if (role === 'source_note') return COLORS.gray;
  return COLORS.navy;
}

function bgColorForRole(role) {
  if (role === 'risk') return COLORS.paleRed;
  if (role === 'evidence') return COLORS.paleBlue;
  if (role === 'explanation') return COLORS.pale;
  return COLORS.paleBlue;
}

module.exports = {
  COLORS, FONT_SIZES, FONT_FACES, CANVAS_PRESETS,
  resolveFontFace, getCanvasSize, textColorForRole, bgColorForRole,
  loadDefaultStyleLock, resolveStyleLock, tokens,
};
