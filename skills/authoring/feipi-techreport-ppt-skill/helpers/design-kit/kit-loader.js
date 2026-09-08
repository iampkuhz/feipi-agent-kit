/**
 * 仓内 Design System 兼容读取器。
 */
'use strict';

const path = require('path');
const { TokenStore, DEFAULT_SKILL_ROOT } = require('../../compiler/token-store');
const { ContractRegistry } = require('../../compiler/contract-registry');

const DESIGN_KIT_ROOT = path.join(DEFAULT_SKILL_ROOT, 'design-system');
let cached = null;

function loadDesignKit() {
  if (cached) return cached;
  const tokens = TokenStore.loadDefault();
  const registry = new ContractRegistry({ tokens });
  cached = {
    manifest: { id: 'feipi-in-repo-design-system', page: tokens.documents.spacing.canvas },
    theme: tokens.documents.colors,
    typography: tokens.documents.typography,
    spacing: tokens.documents.spacing,
    shape: tokens.documents.shape,
    components: Object.fromEntries(registry.components),
    layouts: Object.fromEntries(registry.layouts),
    rootDir: DESIGN_KIT_ROOT,
  };
  return cached;
}

function clearCache() { cached = null; }

module.exports = { loadDesignKit, clearCache, DESIGN_KIT_ROOT };
