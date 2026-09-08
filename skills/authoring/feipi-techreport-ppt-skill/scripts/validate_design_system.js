#!/usr/bin/env node
/**
 * Validate modular design-system files.
 *
 * This is intentionally lightweight: it checks JSON validity, required ids,
 * and profile references. Deeper schema validation can be added later when
 * the design system begins driving builders directly.
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { ContractRegistry } = require('../compiler/contract-registry');

const SKILL_DIR = path.resolve(__dirname, '..');
const DESIGN_DIR = path.join(SKILL_DIR, 'design-system');

function readJson(filePath) {
  try {
    return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
  } catch (e) {
    throw new Error(`${filePath}: JSON 解析失败: ${e.message}`);
  }
}

function listJsonFiles(dir) {
  if (!fs.existsSync(dir)) return [];
  return fs.readdirSync(dir)
    .filter(name => name.endsWith('.json'))
    .map(name => path.join(dir, name))
    .sort();
}

function requireId(doc, filePath) {
  if (!doc.id || typeof doc.id !== 'string') {
    throw new Error(`${filePath}: 缺少字符串 id`);
  }
}

function main() {
  const tokensDir = path.join(DESIGN_DIR, 'tokens');
  const componentsDir = path.join(DESIGN_DIR, 'components');
  const profilesDir = path.join(DESIGN_DIR, 'profiles');
  const layoutsDir = path.join(DESIGN_DIR, 'layouts');

  const tokenFiles = listJsonFiles(tokensDir);
  const componentFiles = listJsonFiles(componentsDir);
  const profileFiles = listJsonFiles(profilesDir);
  const layoutFiles = listJsonFiles(layoutsDir);

  const tokenIds = new Set();
  const componentIds = new Set();
  const issues = [];

  for (const file of tokenFiles) {
    try {
      const doc = readJson(file);
      requireId(doc, file);
      tokenIds.add(doc.id);
    } catch (e) {
      issues.push(e.message);
    }
  }

  for (const file of componentFiles) {
    try {
      const doc = readJson(file);
      requireId(doc, file);
      componentIds.add(doc.id);
      if (!Array.isArray(doc.depends_on) || doc.depends_on.length === 0) {
        issues.push(`${file}: component 必须声明 depends_on`);
      } else {
        for (const dep of doc.depends_on) {
          if (!tokenIds.has(dep)) {
            issues.push(`${file}: depends_on 引用了不存在的 token "${dep}"`);
          }
        }
      }
    } catch (e) {
      issues.push(e.message);
    }
  }

  for (const file of layoutFiles) {
    try {
      const doc = readJson(file);
      requireId(doc, file);
      if (!doc.regions || Object.keys(doc.regions).length === 0) issues.push(`${file}: Layout Contract 缺少 regions`);
      for (const [regionId, region] of Object.entries(doc.regions || {})) {
        if (!region.bounds_in) issues.push(`${file}: region ${regionId} 缺少 bounds_in`);
        if (!Array.isArray(region.allowed_components)) issues.push(`${file}: region ${regionId} 缺少 allowed_components`);
      }
    } catch (e) {
      issues.push(e.message);
    }
  }

  try {
    const registry = new ContractRegistry();
    issues.push(...registry.validateTokenReferences());
  } catch (e) {
    issues.push(e.message);
  }

  for (const file of profileFiles) {
    try {
      const doc = readJson(file);
      requireId(doc, file);
      for (const tokenId of doc.tokens || []) {
        if (!tokenIds.has(tokenId)) {
          issues.push(`${file}: profile 引用了不存在的 token "${tokenId}"`);
        }
      }
      for (const componentId of doc.components || []) {
        if (!componentIds.has(componentId)) {
          issues.push(`${file}: profile 引用了不存在的 component "${componentId}"`);
        }
      }
      if (!doc.style_lock_target) {
        issues.push(`${file}: profile 缺少 style_lock_target`);
      }
    } catch (e) {
      issues.push(e.message);
    }
  }

  const summary = {
    design_system_dir: DESIGN_DIR,
    tokens: tokenFiles.length,
    components: componentFiles.length,
    layouts: layoutFiles.length,
    profiles: profileFiles.length,
    issues,
    status: issues.length === 0 ? 'pass' : 'fail',
  };

  if (process.argv.includes('--json')) {
    process.stdout.write(JSON.stringify(summary, null, 2) + '\n');
  } else {
    console.log('Design System Validation');
    console.log(`  tokens: ${summary.tokens}`);
    console.log(`  components: ${summary.components}`);
    console.log(`  layouts: ${summary.layouts}`);
    console.log(`  profiles: ${summary.profiles}`);
    if (issues.length > 0) {
      console.log('  issues:');
      for (const issue of issues) console.log(`    - ${issue}`);
    }
    console.log(`  status: ${summary.status}`);
  }

  if (issues.length > 0) process.exit(1);
}

main();
