#!/usr/bin/env node
/**
 * Provenance 完整性检查。
 *
 * 用法:
 *   node scripts/check_provenance.js <slide-ir.json> [--json]
 *
 * 检查:
 * - 每个 factual element 至少有 source_refs
 * - 每个 source_refs 都能在 provenance 中找到
 * - takeaway 必须有 provenance 追溯
 * - 不允许出现未追溯事实
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { checkProvenance } = require('../helpers/ir/provenance');

function main() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    process.stderr.write('用法: node scripts/check_provenance.js <slide-ir.json> [--json]\n');
    process.exit(1);
  }

  const jsonMode = args.includes('--json');
  const filePath = args.filter(a => a !== '--json')[0];
  if (!filePath) {
    process.stderr.write('错误: 需要提供 slide-ir.json 文件路径\n');
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

  const issues = checkProvenance(ir);

  if (jsonMode) {
    const hardFails = issues.filter(i => i.severity === 'hard_fail');
    const report = {
      file: fullPath,
      slide_id: ir.slide_id || 'unknown',
      issues,
      summary: {
        total: issues.length,
        hard_fail: hardFails.length,
        warning: issues.filter(i => i.severity === 'warning').length,
        info: issues.filter(i => i.severity === 'info').length,
      },
      status: hardFails.length > 0 ? 'fail' : 'pass',
    };
    process.stdout.write(JSON.stringify(report, null, 2) + '\n');
    if (hardFails.length > 0) process.exit(1);
    return;
  }

  if (issues.length === 0) {
    process.stdout.write(`Provenance 检查通过: ${ir.slide_id || 'unknown'}\n`);
    return;
  }

  const hardFails = issues.filter(i => i.severity === 'hard_fail');
  for (const issue of issues) {
    const prefix = issue.severity === 'hard_fail' ? '✗' : issue.severity === 'warning' ? '⚠' : 'ℹ';
    process.stdout.write(`  [${prefix}] ${issue.message}\n`);
  }

  if (hardFails.length > 0) {
    process.stdout.write(`\nProvenance 检查失败: ${ir.slide_id}（${hardFails.length} 个硬失败）\n`);
    process.exit(1);
  }

  process.stdout.write(`\nProvenance 检查通过: ${ir.slide_id}（${issues.length} 个警告）\n`);
}

main();
