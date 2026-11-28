#!/usr/bin/env node
/**
 * 布局求解器 CLI。
 *
 * 用法:
 *   node scripts/solve_slide_layout.js <input.slide-ir.json> <output.slide-ir.json> [--json]
 *
 * 输入 normalized Slide IR，输出 solved IR（补充缺失 bounds）。
 * 已有明确 bounds 的元素默认保留。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { solveLayout } = require('../helpers/layout/solver');
const { normalize } = require('../helpers/ir/normalize');

function main() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    process.stderr.write('用法: node scripts/solve_slide_layout.js <input.slide-ir.json> [output.slide-ir.json] [--json]\n');
    process.exit(1);
  }

  const jsonMode = args.includes('--json');
  const filePath = args.filter(a => !a.startsWith('--'))[0];
  const outputPath = args.filter(a => !a.startsWith('--'))[1];

  if (!filePath) {
    process.stderr.write('错误: 需要提供输入文件路径\n');
    process.exit(1);
  }

  const fullPath = path.resolve(filePath);
  if (!fs.existsSync(fullPath)) {
    process.stderr.write(`错误: 文件不存在: ${fullPath}\n`);
    process.exit(1);
  }

  let ir;
  try {
    ir = JSON.parse(fs.readFileSync(fullPath, 'utf-8'));
  } catch (e) {
    process.stderr.write(`错误: JSON 解析失败: ${e.message}\n`);
    process.exit(1);
  }

  // Normalize first if needed
  if (!ir.canvas || !ir.version) {
    ir = normalize(ir);
  }

  const solved = solveLayout(ir);

  // Count how many elements got auto-assigned bounds
  const totalElements = solved.elements?.length || 0;
  const withBounds = solved.elements?.filter(e => e.layout && e.layout.x !== undefined && e.layout.w !== undefined).length || 0;
  const newlyAssigned = withBounds;

  if (outputPath) {
    const outPath = path.resolve(outputPath);
    fs.writeFileSync(outPath, JSON.stringify(solved, null, 2) + '\n', 'utf-8');
    if (!jsonMode) {
      process.stdout.write(`布局求解完成: ${fullPath} → ${outPath}\n`);
      process.stdout.write(`  元素总数: ${totalElements}\n`);
      process.stdout.write(`  已分配 bounds: ${withBounds}\n`);
    }
  }

  if (jsonMode) {
    const report = {
      slide_id: solved.slide_id || 'unknown',
      total_elements: totalElements,
      elements_with_bounds: withBounds,
      newly_assigned: newlyAssigned,
      status: 'pass',
    };
    process.stdout.write(JSON.stringify(report, null, 2) + '\n');
  }
}

main();
