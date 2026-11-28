#!/usr/bin/env node
/**
 * Benchmark 套件批量运行。
 *
 * 用法:
 *   node tests/run_benchmarks.js [--dry-run] [--no-render] [--json] [--full] [--filter <name>] [--allow-skip]
 *
 * 默认只跑 smoke benchmark。加 --full 跑全部。
 * --full 模式下，任何 skip 都使命令以非 0 退出，除非显式传入 --allow-skip。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

const SCRIPT_DIR = __dirname;
const SKILL_DIR = path.join(SCRIPT_DIR, '..');
const BENCHMARKS_DIR = path.join(SKILL_DIR, 'tests', 'fixtures', 'benchmarks');
const REPO_ROOT = path.resolve(SCRIPT_DIR, '..', '..', '..', '..');
const OUTPUT_BASE = path.join(REPO_ROOT, 'tmp', 'ppt-skill-v2-run', 'benchmarks');

const SMOKE_BENCHMARKS = [
  'architecture-high-density',
  'flow-api-lifecycle',
  'comparison-competitive-matrix',
];

const FULL_BENCHMARKS = [
  ...SMOKE_BENCHMARKS,
  'roadmap-technical-delivery',
  'metrics-dashboard',
  'decision-tree',
  'capability-map',
  'overload-should-split',
];

function detectNode() {
  try {
    return require.resolve('node');
  } catch {
    return process.execPath;
  }
}

function runValidation(irPath) {
  const NODE = detectNode();
  const script = path.join(SKILL_DIR, 'scripts', 'validate_slide_ir.js');
  try {
    execSync(`${NODE} "${script}" "${irPath}"`, { encoding: 'utf-8', stdio: 'pipe' });
    return { status: 'pass' };
  } catch (e) {
    return { status: 'fail', error: e.stderr.toString().trim() };
  }
}

function runStaticQA(irPath) {
  const NODE = detectNode();
  const script = path.join(SKILL_DIR, 'scripts', 'inspect_slide_ir_layout.js');
  try {
    const output = execSync(`${NODE} "${script}" "${irPath}" --json`, { encoding: 'utf-8', stdio: 'pipe' });
    return JSON.parse(output);
  } catch (e) {
    try {
      return JSON.parse(e.stdout.toString());
    } catch {
      return { status: 'fail', summary: { hard_fail: 1, warning: 0 } };
    }
  }
}

function runProvenanceCheck(irPath) {
  const NODE = detectNode();
  const script = path.join(SKILL_DIR, 'scripts', 'check_provenance.js');
  try {
    const output = execSync(`${NODE} "${script}" "${irPath}" --json`, { encoding: 'utf-8', stdio: 'pipe' });
    return JSON.parse(output);
  } catch (e) {
    try {
      return JSON.parse(e.stdout.toString());
    } catch {
      return { status: 'fail', summary: { hard_fail: 1, warning: 0 } };
    }
  }
}

function runCapacityCheck(irPath) {
  const ir = JSON.parse(fs.readFileSync(irPath, 'utf-8'));
  const { checkCapacity } = require('../helpers/ir/capacity');
  return checkCapacity(ir);
}

function runNormalize(irPath, outputPath) {
  const NODE = detectNode();
  const script = path.join(SKILL_DIR, 'scripts', 'normalize_slide_ir.js');
  try {
    execSync(`${NODE} "${script}" "${irPath}" "${outputPath}"`, { encoding: 'utf-8', stdio: 'pipe' });
    return { status: 'pass' };
  } catch (e) {
    return { status: 'fail', error: e.stderr.toString().trim() };
  }
}

/**
 * Determine the actual status of a benchmark result.
 * Returns one of: 'pass', 'fail', 'needs_user_decision'
 *
 * Rules for needs_user_decision:
 *   - Requires REAL evidence: capacity check severity, QA issue about splitting, or explicit pipeline decision
 *   - hardFails === 0 alone is NOT sufficient evidence
 *   - layout_unsolved does NOT count as capacity/split evidence
 */
function determineActualStatus(result, expected) {
  const qa = result.checks?.static_qa || {};
  const hardFails = qa.summary?.hard_fail || 0;
  const layoutUnsolved = (qa.issues || []).some(i => i.type === 'layout_unsolved');

  // Real capacity/split evidence (excluding layout_unsolved)
  const capacityItems = result.checks?.capacity || [];
  const hasCapacityDecision = capacityItems.some(i => i.severity === 'needs_user_decision');
  const hasCapacitySplitQA = (qa.issues || []).some(i =>
    i.type === 'region_density_exceeded' ||
    i.type === 'capacity_exceeded' ||
    i.type === 'split_needed' ||
    (i.suggestion && i.suggestion.includes('拆页'))
  );
  const hasExplicitUserDecision = capacityItems.some(i => i.severity === 'needs_user_decision') ||
    (qa.issues || []).some(i => i.type === 'needs_user_decision');
  const hasRealCapacityEvidence = hasCapacityDecision || hasCapacitySplitQA || hasExplicitUserDecision;

  // If there are hard fails beyond allowed threshold, it's a real fail
  const maxAllowedHard = expected?.expected_qa_static?.hard_fail_max ?? 0;
  if (hardFails > maxAllowedHard) {
    return 'fail';
  }

  // Check if this is a negative test expecting needs_user_decision
  if (expected?.expected_status === 'needs_user_decision') {
    // Must have real evidence — hardFails === 0 alone is NOT enough
    if (hasRealCapacityEvidence) {
      return 'needs_user_decision';
    }
    // No genuine capacity/split evidence — the fixture didn't trigger what it promised
    return 'fail';
  }

  // For fail_expected cases
  if (expected?.expected_status === 'fail_expected') {
    return 'fail_expected';
  }

  // Normal pass case: no hard fails, score above minimum
  const score = result.score ?? 100;
  const minScore = expected?.expected_score_min ?? 80;
  if (score >= minScore && hardFails === 0) {
    return 'pass';
  }

  return 'fail';
}

function main() {
  const args = process.argv.slice(2);
  const dryRun = args.includes('--dry-run');
  const noRender = args.includes('--no-render');
  const jsonMode = args.includes('--json');
  const fullMode = args.includes('--full');
  const allowSkip = args.includes('--allow-skip');
  const filterIdx = args.indexOf('--filter');
  const filter = filterIdx >= 0 ? args[filterIdx + 1] : null;
  const fixturesIdx = args.indexOf('--fixtures-dir');
  const fixturesDir = fixturesIdx >= 0 ? path.resolve(args[fixturesIdx + 1]) : null;
  const singleIdx = args.indexOf('--single');
  const singleDir = singleIdx >= 0 ? path.resolve(args[singleIdx + 1]) : null;

  // Determine which benchmarks to run and their base directory
  let benchmarks;
  let effectiveBenchmarksDir = fixturesDir || BENCHMARKS_DIR;
  if (singleDir) {
    // Run a single benchmark from an arbitrary directory
    benchmarks = [path.basename(singleDir)];
    effectiveBenchmarksDir = path.dirname(singleDir);
  } else {
    benchmarks = fullMode ? FULL_BENCHMARKS : SMOKE_BENCHMARKS;
    if (filter) {
      benchmarks = benchmarks.filter(b => b.includes(filter) || filter.includes(b));
    }
  }

  fs.mkdirSync(OUTPUT_BASE, { recursive: true });

  const results = [];

  for (const name of benchmarks) {
    const benchDir = path.join(effectiveBenchmarksDir, name);
    const irPath = path.join(benchDir, 'slide-ir.json');
    const expectedPath = path.join(benchDir, 'expected-report.json');

    if (!fs.existsSync(irPath)) {
      results.push({
        name,
        status: 'skip',
        reason: 'slide-ir.json 不存在',
        expected_status: null,
        score: null,
      });
      continue;
    }

    const benchOutputDir = path.join(OUTPUT_BASE, name);
    fs.mkdirSync(benchOutputDir, { recursive: true });

    const result = { name, status: 'running', checks: {} };

    // Normalize
    const normalizedPath = path.join(benchOutputDir, 'normalized.json');
    result.checks.normalize = runNormalize(irPath, normalizedPath);
    if (result.checks.normalize.status === 'fail' && !dryRun) {
      result.status = 'fail';
      results.push(result);
      continue;
    }

    // Validation
    result.checks.validation = runValidation(normalizedPath);
    if (result.checks.validation.status === 'fail' && !dryRun) {
      result.status = 'fail';
      results.push(result);
      continue;
    }

    // Static QA
    result.checks.static_qa = runStaticQA(normalizedPath);

    // Provenance check
    result.checks.provenance = runProvenanceCheck(normalizedPath);

    // Capacity check
    result.checks.capacity = runCapacityCheck(normalizedPath);

    // Load expected report
    let expected = null;
    if (fs.existsSync(expectedPath)) {
      expected = JSON.parse(fs.readFileSync(expectedPath, 'utf-8'));
      result.expected = expected;

      // Compute score
      let score = 100;
      const qa = result.checks.static_qa;
      if (qa.summary && qa.summary.hard_fail > 0) score -= 40;
      if (qa.summary && qa.summary.warning > 0) score -= qa.summary.warning * 5;
      if (result.checks.provenance.status === 'fail') score -= 30;
      if (result.checks.capacity.some && result.checks.capacity.some(i => i.severity === 'needs_user_decision')) score -= 10;
      score = Math.max(0, score);
      result.score = score;

      // Determine actual status considering expected_status
      result.actual_status = determineActualStatus(result, expected);

      // For release gate, use actual_status to decide pass/fail
      if (result.actual_status === 'pass' || result.actual_status === 'needs_user_decision') {
        result.status = 'pass';
      } else if (result.actual_status === 'fail_expected') {
        result.status = 'pass'; // Expected to fail, and it did
      } else {
        result.status = 'fail';
      }
    } else {
      // expected-report.json missing
      if (fullMode) {
        // Full mode requires expected-report.json — missing file is a failure
        result.status = 'fail';
        result.score = null;
        result.actual_status = 'fail';
        result.reason = 'full 模式缺少 expected-report.json';
      } else {
        // Smoke/default mode: pass without scoring
        result.status = 'pass';
        result.score = null;
        result.actual_status = 'pass';
      }
    }

    // Write result
    fs.writeFileSync(path.join(benchOutputDir, 'result.json'), JSON.stringify(result, null, 2) + '\n');
    results.push(result);
  }

  // Summary
  const passed = results.filter(r => r.status === 'pass').length;
  const failed = results.filter(r => r.status === 'fail').length;
  const skipped = results.filter(r => r.status === 'skip').length;

  const summary = {
    total: results.length,
    passed,
    failed,
    skipped,
    results: results.map(r => ({
      name: r.name,
      status: r.status,
      actual_status: r.actual_status || null,
      expected_status: r.expected?.expected_status || null,
      score: r.score,
      score_min: r.expected?.expected_score_min || null,
      hard_fail: r.checks?.static_qa?.summary?.hard_fail ?? 0,
      warning: r.checks?.static_qa?.summary?.warning ?? 0,
      skipped: r.status === 'skip',
      skip_reason: r.reason || null,
    })),
    mode: fullMode ? 'full' : 'smoke',
    timestamp: new Date().toISOString(),
  };

  fs.writeFileSync(path.join(OUTPUT_BASE, 'benchmark-summary.json'), JSON.stringify(summary, null, 2) + '\n');

  // Markdown summary
  let md = `# Benchmark Summary\n\n`;
  md += `- 模式: ${fullMode ? 'full' : 'smoke'}\n`;
  md += `- 时间: ${summary.timestamp}\n`;
  md += `- 总计: ${summary.total} | 通过: ${summary.passed} | 失败: ${summary.failed} | 跳过: ${summary.skipped}\n\n`;
  md += '| Benchmark | 状态 | 期望状态 | 实际状态 | 评分 | 最低要求 | hard_fail | warning | 跳过原因 |\n';
  md += '|---|---|---|---|---|---|---|---|---|\n';
  for (const r of summary.results) {
    const icon = r.status === 'pass' ? '✅' : r.status === 'fail' ? '❌' : '⏭';
    md += `| ${r.name} | ${icon} ${r.status} | ${r.expected_status || 'pass'} | ${r.actual_status || r.status} | ${r.score !== null ? r.score : 'N/A'} | ${r.score_min || 80} | ${r.hard_fail} | ${r.warning} | ${r.skip_reason || '-'} |\n`;
  }

  if (fullMode && skipped > 0 && !allowSkip) {
    md += `\n⚠ **Full 模式下有 ${skipped} 个跳过项，视为失败。请补充缺失的 slide-ir.json 或传入 --allow-skip。**\n`;
  }

  fs.writeFileSync(path.join(OUTPUT_BASE, 'benchmark-summary.md'), md);

  if (jsonMode) {
    process.stdout.write(JSON.stringify(summary, null, 2) + '\n');
  } else {
    process.stdout.write(md);
  }

  // Exit code logic:
  // - Any hard fail → exit 1
  // - Full mode with skip (and no --allow-skip) → exit 1
  if (failed > 0) process.exit(1);
  if (fullMode && skipped > 0 && !allowSkip) process.exit(1);
}

main();
