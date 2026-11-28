#!/usr/bin/env node
/**
 * 质量评分报告。
 *
 * 输入 benchmark 目录中的 result.json 和 expected-report.json，
 * 输出质量分（deterministic scoring）。
 *
 * 用法:
 *   node scripts/score_quality_report.js <benchmark-dir> [--json]
 */
'use strict';

const fs = require('fs');
const path = require('path');

function score(result, expected) {
  let score = 100;
  const issues = [];

  const qa = result.checks?.static_qa || {};
  const qaHardFails = qa.summary?.hard_fail || 0;
  const qaWarnings = qa.summary?.warning || 0;

  if (qaHardFails > 0) {
    const maxAllowed = expected.expected_qa_static?.hard_fail_max || 0;
    if (qaHardFails > maxAllowed) {
      score -= 40;
      issues.push(`Static QA 硬失败 ${qaHardFails} 超过上限 ${maxAllowed}`);
    }
  }

  if (qaWarnings > 0) {
    const maxAllowed = expected.expected_qa_static?.warning_max || 0;
    if (qaWarnings > maxAllowed) {
      score -= qaWarnings * 5;
      issues.push(`Static QA 警告 ${qaWarnings} 超过上限 ${maxAllowed}`);
    }
  }

  const prov = result.checks?.provenance || {};
  if (prov.status === 'fail' || (prov.summary?.hard_fail || 0) > 0) {
    score -= 30;
    issues.push('Provenance 检查失败');
  }

  const cap = result.checks?.capacity || [];
  const decisionItems = cap.filter(i => i.severity === 'needs_user_decision');
  if (decisionItems.length > 0) {
    score -= 10 * decisionItems.length;
    issues.push(`容量检查建议拆页: ${decisionItems.length} 项`);
  }

  if (!result.checks?.render_qa && expected.expected_render) {
    score -= 5;
    issues.push('缺少 Render QA 结果');
  }

  score = Math.max(0, Math.min(100, score));

  // Determine actual status
  const expectedStatus = expected.expected_status || 'pass';
  let actualStatus;
  if (expectedStatus === 'needs_user_decision') {
    // Require real evidence — hardFails === 0 alone is NOT sufficient
    const hasCapacitySplitQA = (qa.issues || []).some(i =>
      i.type === 'region_density_exceeded' ||
      i.type === 'capacity_exceeded' ||
      i.type === 'split_needed' ||
      (i.suggestion && i.suggestion.includes('拆页'))
    );
    const hasCapacityDecision = (result.checks?.capacity || []).some(i => i.severity === 'needs_user_decision');
    if (hasCapacityDecision || hasCapacitySplitQA) {
      actualStatus = 'needs_user_decision';
    } else {
      actualStatus = 'fail';
    }
  } else if (expectedStatus === 'fail_expected') {
    actualStatus = 'fail_expected';
  } else {
    actualStatus = score >= (expected.expected_score_min || 80) ? 'pass' : 'fail';
  }

  return {
    score,
    issues,
    passed: actualStatus === 'pass' || actualStatus === 'needs_user_decision' || actualStatus === 'fail_expected',
    actual_status: actualStatus,
    expected_status: expectedStatus,
  };
}

function main() {
  const args = process.argv.slice(2);
  if (args.length < 1) {
    process.stderr.write('用法: node scripts/score_quality_report.js <benchmark-dir> [--json]\n');
    process.exit(1);
  }

  const jsonMode = args.includes('--json');
  const benchDir = path.resolve(args.filter(a => a !== '--json')[0]);

  const resultPath = path.join(benchDir, 'result.json');
  let expectedPath = path.join(benchDir, 'expected-report.json');
  if (!fs.existsSync(expectedPath)) {
    const benchName = path.basename(benchDir);
    const skillDir = path.resolve(benchDir, '..', '..', '..', '..', 'skills', 'authoring', 'feipi-techreport-ppt-skill');
    expectedPath = path.join(skillDir, 'fixtures', 'benchmarks', benchName, 'expected-report.json');
  }

  if (!fs.existsSync(resultPath)) {
    process.stderr.write(`错误: result.json 不存在: ${resultPath}\n`);
    process.exit(1);
  }
  if (!fs.existsSync(expectedPath)) {
    process.stderr.write(`错误: expected-report.json 不存在: ${expectedPath}\n`);
    process.exit(1);
  }

  const result = JSON.parse(fs.readFileSync(resultPath, 'utf-8'));
  const expected = JSON.parse(fs.readFileSync(expectedPath, 'utf-8'));

  const scoring = score(result, expected);

  if (jsonMode) {
    process.stdout.write(JSON.stringify({
      benchmark: result.name,
      score: scoring.score,
      passed: scoring.passed,
      actual_status: scoring.actual_status,
      expected_status: scoring.expected_status,
      issues: scoring.issues,
      expected_min: expected.expected_score_min || 80,
    }, null, 2) + '\n');
    if (!scoring.passed) process.exit(1);
    return;
  }

  const icon = scoring.passed ? '✅' : '❌';
  process.stdout.write(`${icon} ${result.name}: ${scoring.score}/100 [${scoring.actual_status}] (期望: ${scoring.expected_status}, 最低: ${expected.expected_score_min || 80})\n`);
  if (scoring.issues.length > 0) {
    for (const issue of scoring.issues) {
      process.stdout.write(`  - ${issue}\n`);
    }
  }
  if (!scoring.passed) process.exit(1);
}

main();
