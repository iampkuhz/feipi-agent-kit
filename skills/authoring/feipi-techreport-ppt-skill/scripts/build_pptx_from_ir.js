#!/usr/bin/env node
'use strict';

const fs = require('fs');
const path = require('path');
const { validateSlideIR } = require('../compiler/slide-ir-validator');
const designKitAdapter = require('../helpers/design-kit/adapters/compiler-adapter');
const compiler = require('../helpers/pptx/compiler');

const args = process.argv.slice(2);
const fileArgs = args.filter(arg => !arg.startsWith('--'));
if (fileArgs.length < 2) {
  console.error('用法: node build_pptx_from_ir.js <slide-ir.json> <output.pptx> [--allow-warnings]');
  process.exit(1);
}
const inputPath = path.resolve(fileArgs[0]);
const outputPath = path.resolve(fileArgs[1]);
let doc;
try { doc = JSON.parse(fs.readFileSync(inputPath, 'utf-8')); }
catch (error) { console.error(`错误: 无法读取或解析 Slide IR: ${error.message}`); process.exit(1); }

try {
  if (designKitAdapter.isDesignKitSpec(doc)) doc = designKitAdapter.normalizeToSlideIR(doc);
} catch (error) { console.error(`错误: ${error.message}`); process.exit(1); }

const validation = validateSlideIR(doc);
if (!validation.valid) {
  console.error('错误: Slide IR 校验失败');
  validation.errors.forEach(error => console.error(`  - ${error}`));
  process.exit(1);
}

(async () => {
  const result = await compiler.compile(doc, outputPath);
  if (!result.success) { console.error(result.error); process.exit(1); }
  console.log(`PPTX 编译成功: ${outputPath}`);
  console.log(`geometry_hash: ${result.summary.geometry_hash}`);
  console.log(`overflow: ${result.summary.overflow.status}`);
})();
