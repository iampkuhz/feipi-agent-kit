#!/usr/bin/env node
/**
 * Slide IR 保守规范化工具。
 *
 * 用法:
 *   node scripts/normalize_slide_ir.js <input.slide-ir.json> <output.slide-ir.json>
 *
 * 规范化动作：
 * - 补默认 canvas
 * - 规范 region id
 * - 补默认 priority
 * - 排序 elements
 * - 补默认 constraints
 * - 不新增事实内容
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { normalize } = require('../helpers/ir/normalize');

function main() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    process.stderr.write('用法: node scripts/normalize_slide_ir.js <input.slide-ir.json> [output.slide-ir.json]\n');
    process.exit(1);
  }

  const inputPath = path.resolve(args[0]);
  if (!fs.existsSync(inputPath)) {
    process.stderr.write(`错误: 文件不存在: ${inputPath}\n`);
    process.exit(1);
  }

  let ir;
  try {
    ir = JSON.parse(fs.readFileSync(inputPath, 'utf-8'));
  } catch (e) {
    process.stderr.write(`错误: JSON 解析失败: ${e.message}\n`);
    process.exit(1);
  }

  const normalized = normalize(ir);

  if (args.length >= 2) {
    const outputPath = path.resolve(args[1]);
    fs.writeFileSync(outputPath, JSON.stringify(normalized, null, 2) + '\n', 'utf-8');
    process.stdout.write(`规范化完成: ${inputPath} → ${outputPath}\n`);
  } else {
    process.stdout.write(JSON.stringify(normalized, null, 2) + '\n');
  }
}

main();
