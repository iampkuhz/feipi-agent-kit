/**
 * Design-kit 兼容 token resolver。
 * density 只能选择离散合同，不再对字号或间距做连续缩放。
 */
'use strict';

const { TokenStore } = require('../../compiler/token-store');
const tokens = TokenStore.loadDefault();

function resolveToken(tokenPath) {
  try { return tokens.color(tokenPath); } catch { return null; }
}

function resolveVariant(componentSpec, variantName) {
  const variant = componentSpec?.variants?.[variantName] || componentSpec?.variants?.standard;
  if (!variant) throw new Error(`variant=${variantName} 未登记`);
  const resolved = {};
  for (const [key, value] of Object.entries(variant)) {
    resolved[key] = typeof value === 'string' ? (resolveToken(value) || value) : value;
  }
  return resolved;
}

function resolveSize(componentSpec, sizePreset) {
  const sizes = componentSpec?.contract?.sizes || componentSpec?.sizes || {};
  const size = sizes[sizePreset];
  if (!size) throw new Error(`size=${sizePreset} 未登记`);
  return { ...size };
}

function applyDensity(sizeConfig, densityPreset) {
  const density = typeof densityPreset === 'string' ? densityPreset : densityPreset?.id;
  if (density && !['compact', 'standard', 'spacious'].includes(density)) throw new Error(`density=${density} 未登记`);
  return { ...sizeConfig };
}

function getDensityPreset(densityName) {
  const id = densityName === 'regular' ? 'standard' : densityName;
  if (!['compact', 'standard', 'spacious'].includes(id)) throw new Error(`density=${densityName} 未登记`);
  return Object.freeze({ id });
}

module.exports = { resolveToken, resolveVariant, resolveSize, applyDensity, getDensityPreset };
