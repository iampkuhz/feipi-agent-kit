#!/usr/bin/env node
/**
 * apply_repair_plan.js — 保守自动修复引擎 CLI。
 *
 * 用法:
 *   node scripts/apply_repair_plan.js <slide-ir.json> <repair-plan.json> <output.slide-ir.json> [--json]
 *
 * 输出:
 *   - 修复后的 Slide IR
 *   - 修复 diff summary
 *   - 是否需要用户决策
 */
'use strict';

const path = require('path');
const fs = require('fs');
const applyRepair = require('../helpers/repair/apply-repair');

const args = process.argv.slice(2);
const jsonFlag = args.includes('--json');
const jsonArgs = args.filter(a => !a.startsWith('--'));

if (jsonArgs.length < 3) {
  console.error('用法: node apply_repair_plan.js <slide-ir.json> <repair-plan.json> <output.slide-ir.json> [--json]');
  process.exit(1);
}

const [irPath, planPath, outputPath] = jsonArgs.map(a => path.resolve(a));

// Load slide IR
if (!fs.existsSync(irPath)) {
  console.error(`错误: Slide IR 文件不存在: ${irPath}`);
  process.exit(1);
}
const slideIR = JSON.parse(fs.readFileSync(irPath, 'utf-8'));

// Load repair plan
if (!fs.existsSync(planPath)) {
  console.error(`错误: Repair plan 文件不存在: ${planPath}`);
  process.exit(1);
}
const repairPlan = JSON.parse(fs.readFileSync(planPath, 'utf-8'));

// Apply repair
const result = applyRepair.applyRepairPlan(slideIR, repairPlan);

// Write output
const outputDir = path.dirname(outputPath);
if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}
fs.writeFileSync(outputPath, JSON.stringify(result.repaired_ir, null, 2), 'utf-8');

// Output report
if (jsonFlag) {
  console.log(JSON.stringify({
    output: outputPath,
    needs_user_decision: result.needs_user_decision,
    change_summary: result.change_summary,
    changes: result.changes,
    split_recommendation: result.split_recommendation
  }, null, 2));
} else {
  console.log('\n=== 修复报告 ===\n');
  console.log(`输出: ${outputPath}`);
  console.log(`总变更: ${result.change_summary.total_changes}`);

  if (result.change_summary.moved > 0) console.log(`  元素移动: ${result.change_summary.moved}`);
  if (result.change_summary.text_compressed > 0) console.log(`  文本压缩: ${result.change_summary.text_compressed}`);
  if (result.change_summary.clamped > 0) console.log(`  越界修正: ${result.change_summary.clamped}`);
  if (result.change_summary.font_adjusted > 0) console.log(`  字号调整: ${result.change_summary.font_adjusted}`);
  if (result.change_summary.failed > 0) console.log(`  修复失败: ${result.change_summary.failed}`);

  console.log('');
  console.log(`需要用户决策: ${result.needs_user_decision ? '是' : '否'}`);

  if (result.split_recommendation) {
    console.log(`拆页建议: ${result.split_recommendation.reason}`);
    console.log(`  ${result.split_recommendation.suggestion}`);
  }

  if (result.changes.length > 0) {
    console.log('\n变更详情:');
    for (const c of result.changes) {
      console.log(`  ${c.element_id || ''}: ${c.action}`);
    }
  }
  console.log('');
}
