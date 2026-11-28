#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const configPath = path.join(__dirname, '..', 'config', 'workflow-modes.json');
const config = JSON.parse(fs.readFileSync(configPath, 'utf-8'));
const issues = [];
for (const name of ['fast', 'review', 'strict']) {
  const mode = config.modes?.[name];
  if (!mode) { issues.push(`缺少 ${name} 模式`); continue; }
  for (const field of ['requires_page_contract_confirmation', 'requires_source_provenance', 'qa_strategy', 'decision_policy']) {
    if (!(field in mode)) issues.push(`${name}: 缺少 ${field}`);
  }
  for (const field of ['allow_warnings', 'render_required', 'visual_approval_required']) {
    if (typeof mode.qa_strategy?.[field] !== 'boolean') issues.push(`${name}.qa_strategy.${field} 必须为 boolean`);
  }
}
if (config.aliases?.draft !== 'fast') issues.push('draft 必须 alias 到 fast');
if (config.aliases?.production !== 'strict') issues.push('production 必须 alias 到 strict');
const result = { config_path: configPath, modes: Object.keys(config.modes || {}), aliases: config.aliases, issues, status: issues.length ? 'fail' : 'pass' };
if (process.argv.includes('--json')) process.stdout.write(JSON.stringify(result, null, 2) + '\n');
else {
  console.log(`Workflow Modes: ${result.status}`);
  if (issues.length) issues.forEach(issue => console.log(`  - ${issue}`));
}
process.exit(issues.length ? 1 : 0);
