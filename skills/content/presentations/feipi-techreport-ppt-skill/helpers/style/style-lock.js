/** Style lock 是 token/profile 的派生兼容视图，不再维护视觉数值。 */
'use strict';

const fs = require('fs');
const path = require('path');
const { TokenStore } = require('../../compiler/token-store');

const STYLE_LOCKS_DIR = path.join(__dirname, '..', '..', 'templates', 'style-locks');
const DEFAULT_STYLE_LOCK = 'cto-technical-report.style-lock.json';

function materialize(profile) {
  const store = TokenStore.loadDefault();
  const { typography, colors, spacing, shape } = store.documents;
  return Object.freeze({
    ...profile,
    fonts: typography.font_families,
    font_sizes: typography.sizes_pt,
    min_font_sizes: typography.minimums_pt,
    colors: colors.tokens,
    spacing,
    shape,
    derived: true,
  });
}

function loadStyleLock(name) {
  const filePath = path.join(STYLE_LOCKS_DIR, name);
  if (!fs.existsSync(filePath)) throw new Error(`Style lock 未找到: ${name}`);
  return materialize(JSON.parse(fs.readFileSync(filePath, 'utf-8')));
}

function loadDefaultStyleLock() { return loadStyleLock(DEFAULT_STYLE_LOCK); }

function resolveStyleLock(slideIR) {
  const requested = slideIR?.backend_hints?.style_lock;
  if (requested && typeof requested !== 'string') throw new Error('style_lock 只允许引用已登记 profile，禁止内联任意样式');
  return loadStyleLock(requested || DEFAULT_STYLE_LOCK);
}

function checkDrift(elements) {
  const store = TokenStore.loadDefault();
  const issues = { hard_fail: [], warning: [] };
  for (const element of elements || []) {
    const role = element.text_role || element.role;
    const size = element.resolved_style?.font_size_pt ?? element.text_style?.font_size;
    if (role && size !== undefined) {
      try {
        store.assertRegisteredFontSize(size, element.id || 'unknown');
        store.assertRoleMinimum(role, size);
      } catch (error) {
        issues.hard_fail.push({ type: 'typography_token_drift', element_id: element.id || 'unknown', message: error.message });
      }
    }
  }
  return issues;
}

module.exports = { loadStyleLock, loadDefaultStyleLock, resolveStyleLock, checkDrift, materialize, STYLE_LOCKS_DIR, DEFAULT_STYLE_LOCK };
