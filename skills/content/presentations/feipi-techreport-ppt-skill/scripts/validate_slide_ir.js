#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { validateSlideIR } = require('../compiler/slide-ir-validator');
const designKitAdapter = require('../helpers/design-kit/adapters/compiler-adapter');

const args = process.argv.slice(2);
const jsonMode = args.includes('--json');
const filePath = args.find(arg => !arg.startsWith('--'));
if (!filePath) {
  console.error('用法: node validate_slide_ir.js <slide-ir.json> [--json]');
  process.exit(1);
}

const resolvedPath = path.resolve(filePath);
let doc;
try { doc = JSON.parse(fs.readFileSync(resolvedPath, 'utf-8')); }
catch (error) {
  console.error(`错误: 无法读取或解析 ${resolvedPath}: ${error.message}`);
  process.exit(1);
}

let sourceFormat = doc.version || 'design-kit';
try {
  if (designKitAdapter.isDesignKitSpec(doc)) doc = designKitAdapter.normalizeToSlideIR(doc);
} catch (error) {
  console.error(`校验结果: 失败\n  [错误] ${error.message}`);
  process.exit(1);
}

const result = validateSlideIR(doc);
const output = {
  file: resolvedPath,
  source_format: sourceFormat,
  normalized_version: result.normalized?.version || null,
  slide_id: result.normalized?.slide_id || doc.slide_id || null,
  layout_id: result.normalized?.layout_id || doc.layout_pattern || null,
  elements: result.normalized?.elements?.length || 0,
  valid: result.valid,
  errors: result.errors,
  warnings: result.warnings,
};

if (jsonMode) process.stdout.write(JSON.stringify(output, null, 2) + '\n');
else {
  console.log(`\n文件: ${resolvedPath}`);
  console.log(`slide_id: ${output.slide_id}`);
  console.log(`layout_id: ${output.layout_id}`);
  console.log(`elements: ${output.elements} 个`);
  console.log(`\n校验结果: ${result.valid ? '通过' : '失败'}`);
  for (const error of result.errors) console.log(`  [错误] ${error}`);
  for (const warning of result.warnings) console.log(`  [警告] ${warning}`);
}
process.exit(result.valid ? 0 : 1);
