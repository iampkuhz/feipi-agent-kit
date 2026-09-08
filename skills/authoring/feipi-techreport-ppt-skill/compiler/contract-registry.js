'use strict';

const fs = require('fs');
const path = require('path');
const { TokenStore, DEFAULT_SKILL_ROOT } = require('./token-store');

function readJson(filePath) {
  return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
}

function normalizeComponentId(id) {
  return String(id || '').replace(/^component\./, '');
}

class ContractRegistry {
  constructor(options = {}) {
    this.skillRoot = options.skillRoot || DEFAULT_SKILL_ROOT;
    this.tokens = options.tokens || TokenStore.loadDefault(this.skillRoot);
    this.components = new Map();
    this.layouts = new Map();
    this.load();
  }

  load() {
    const componentDir = path.join(this.skillRoot, 'design-system', 'components');
    for (const name of fs.readdirSync(componentDir).filter(name => name.endsWith('.json'))) {
      const doc = readJson(path.join(componentDir, name));
      this.components.set(normalizeComponentId(doc.id), doc);
    }
    const layoutDir = path.join(this.skillRoot, 'design-system', 'layouts');
    for (const name of fs.readdirSync(layoutDir).filter(name => name.endsWith('.json'))) {
      const doc = readJson(path.join(layoutDir, name));
      this.layouts.set(doc.id, doc);
    }
  }

  component(id, options = {}) {
    const contract = this.components.get(normalizeComponentId(id));
    if (!contract && options.required !== false) throw new Error(`未知 component_id: ${id}`);
    return contract || null;
  }

  layout(id, options = {}) {
    const contract = this.layouts.get(id);
    if (!contract && options.required !== false) throw new Error(`未知 layout_id: ${id}`);
    return contract || null;
  }

  validateElement(element, layoutId) {
    const errors = [];
    const component = this.component(element.component_id, { required: false });
    const layout = this.layout(layoutId, { required: false });
    if (!component) return [`未知 component_id: ${element.component_id}`];
    if (!component.contract) return [`组件 ${element.component_id} 尚未升级为 Component Contract v2`];
    if (!component.contract.variants.includes(element.variant)) {
      errors.push(`组件 ${element.id} 的 variant=${element.variant} 未登记`);
    }
    if (!(element.size in component.contract.sizes)) {
      errors.push(`组件 ${element.id} 的 size=${element.size} 未登记`);
    }
    if (!component.contract.allowed_regions.includes(element.region_id)) {
      errors.push(`组件 ${element.id} 不允许出现在 region=${element.region_id}`);
    }
    if (layout) {
      const region = layout.regions[element.region_id];
      if (!region) {
        errors.push(`layout ${layoutId} 不存在 region=${element.region_id}`);
      } else if (!region.allowed_components.includes(element.component_id)) {
        errors.push(`layout ${layoutId} 的 region=${element.region_id} 不允许 component=${element.component_id}`);
      }
    }
    return errors;
  }

  validateTokenReferences() {
    const errors = [];
    for (const [id, component] of this.components) {
      const contract = component.contract;
      if (!contract) continue;
      for (const [size, spec] of Object.entries(contract.sizes || {})) {
        for (const [key, value] of Object.entries(spec)) {
          if (key.endsWith('padding_token')) {
            try { this.tokens.padding(value); } catch (error) { errors.push(`${id}.${size}.${key}: ${error.message}`); }
          }
        }
      }
      for (const slot of Object.values(contract.slots || {})) {
        if (!slot.text_role && !slot.text_role_from_variant) continue;
        if (slot.text_role) {
          try { this.tokens.typographyRole(slot.text_role); } catch (error) { errors.push(`${id}: ${error.message}`); }
        }
      }
    }
    return errors;
  }
}

module.exports = { ContractRegistry, normalizeComponentId };
