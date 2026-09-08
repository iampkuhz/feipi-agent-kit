'use strict';

const fs = require('fs');
const path = require('path');

const DEFAULT_SKILL_ROOT = path.resolve(__dirname, '..');

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
}

function deepFreeze(value) {
  if (!value || typeof value !== 'object' || Object.isFrozen(value)) return value;
  Object.freeze(value);
  for (const child of Object.values(value)) deepFreeze(child);
  return value;
}

class TokenStore {
  constructor(documents, options = {}) {
    this.documents = deepFreeze(structuredClone(documents));
    this.rootDir = options.rootDir || null;
  }

  static loadDefault(skillRoot = DEFAULT_SKILL_ROOT) {
    const tokenDir = path.join(skillRoot, 'design-system', 'tokens');
    return new TokenStore({
      typography: readJson(path.join(tokenDir, 'typography.core.json')),
      colors: readJson(path.join(tokenDir, 'colors.core.json')),
      spacing: readJson(path.join(tokenDir, 'spacing.core.json')),
      shape: readJson(path.join(tokenDir, 'shape.core.json')),
    }, { rootDir: tokenDir });
  }

  resolve(tokenPath, stack = []) {
    if (typeof tokenPath !== 'string' || tokenPath.length === 0) {
      throw new Error('token path 必须是非空字符串');
    }
    if (stack.includes(tokenPath)) {
      throw new Error(`检测到 token 循环引用: ${[...stack, tokenPath].join(' -> ')}`);
    }
    const parts = tokenPath.split('.');
    let value = this.documents;
    for (const part of parts) {
      if (!value || typeof value !== 'object' || !(part in value)) {
        throw new Error(`未知 token: ${tokenPath}`);
      }
      value = value[part];
    }
    if (value && typeof value === 'object' && typeof value.$ref === 'string') {
      return this.resolve(value.$ref, [...stack, tokenPath]);
    }
    return value;
  }

  typographyRole(role) {
    const size = this.resolve(`typography.sizes_pt.${role}`);
    const minimum = this.resolve(`typography.minimums_pt.${role}`);
    return deepFreeze({
      role,
      font_size_pt: size,
      minimum_pt: minimum,
      font_family: role === 'title' ? 'title' : 'default',
      bold: Boolean(this.documents.typography.weights[role] ?? false),
    });
  }

  fontFace(family = 'default') {
    const chain = this.resolve(`typography.font_families.${family}`);
    if (!Array.isArray(chain) || chain.length === 0) {
      throw new Error(`字体 token ${family} 没有可用字体`);
    }
    return chain[0];
  }

  color(tokenPath) {
    const normalized = tokenPath.startsWith('colors.') ? tokenPath : `colors.tokens.${tokenPath}`;
    return this.resolve(normalized);
  }

  padding(tokenName) {
    return this.resolve(`spacing.padding_in.${tokenName}`);
  }

  lineWidth(tokenName) {
    return this.resolve(`shape.line_width_pt.${tokenName}`);
  }

  cornerRadius(tokenName) {
    return this.resolve(`shape.corner_radius_in.${tokenName}`);
  }

  allowedFontSizes(options = {}) {
    const values = Object.values(this.documents.typography.sizes_pt);
    if (options.includeLegacy !== false) {
      values.push(...(this.documents.typography.legacy_sizes_pt || []));
    }
    return new Set(values.map(Number));
  }

  assertRegisteredFontSize(value, context = 'font size') {
    if (typeof value !== 'number' || !this.allowedFontSizes().has(value)) {
      throw new Error(`${context}=${value}pt 未登记到 typography token`);
    }
  }

  assertRoleMinimum(role, value) {
    const minimum = this.typographyRole(role).minimum_pt;
    if (value < minimum) {
      throw new Error(`${role} 字号 ${value}pt 低于 token 下限 ${minimum}pt`);
    }
  }
}

module.exports = { TokenStore, DEFAULT_SKILL_ROOT };
