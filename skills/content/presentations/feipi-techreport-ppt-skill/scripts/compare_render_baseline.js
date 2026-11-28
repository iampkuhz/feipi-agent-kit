#!/usr/bin/env node
/**
 * compare_render_baseline.js — 渲染结果与基线比较。
 *
 * 用法:
 *   node scripts/compare_render_baseline.js <current-summary.json> <baseline-summary.json> [--json]
 *   node scripts/compare_render_baseline.js --diff <current-dir> <baseline-dir> [--json]
 *
 * 比较规则:
 *   - 当前分数低于 baseline 超过阈值 → 失败
 *   - hard_fail 增加 → 失败
 *   - render skip 从无到有 → warning 或失败
 */
'use strict';

const path = require('path');
const fs = require('fs');

// 配置
const SCORE_THRESHOLD = 5; // 低于基线超过 5 分则失败
const args = process.argv.slice(2);
const jsonFlag = args.includes('--json');

function loadJSON(filePath) {
  if (!fs.existsSync(filePath)) {
    console.error(`错误: 文件不存在: ${filePath}`);
    process.exit(1);
  }
  return JSON.parse(fs.readFileSync(filePath, 'utf-8'));
}

function compareSummaries(current, baseline) {
  const result = { pass: true, comparisons: [], verdict: [] };

  // 1. 分数比较
  if (current.score !== undefined && baseline.score !== undefined) {
    const diff = current.score - baseline.score;
    const entry = { type: 'score', current: current.score, baseline: baseline.score, diff };
    if (diff < -SCORE_THRESHOLD) {
      entry.status = 'fail';
      entry.message = `分数从 ${baseline.score} 降至 ${current.score} (差值 ${diff})，超过阈值 ${SCORE_THRESHOLD}`;
      result.pass = false;
      result.verdict.push(`FAIL: ${entry.message}`);
    } else if (diff < 0) {
      entry.status = 'warning';
      entry.message = `分数微降: ${baseline.score} → ${current.score} (差值 ${diff})`;
      result.verdict.push(`WARNING: ${entry.message}`);
    } else {
      entry.status = 'pass';
      entry.message = `分数提升: ${baseline.score} → ${current.score}`;
    }
    result.comparisons.push(entry);
  }

  // 2. Hard fail 数量
  const cHardFail = current.hard_fail_count ?? current.summary?.hard_fail ?? 0;
  const bHardFail = baseline.hard_fail_count ?? baseline.summary?.hard_fail ?? 0;
  if (cHardFail > bHardFail) {
    result.comparisons.push({
      type: 'hard_fail',
      current: cHardFail,
      baseline: bHardFail,
      status: 'fail',
      message: `hard_fail 增加: ${bHardFail} → ${cHardFail}`
    });
    result.pass = false;
    result.verdict.push(`FAIL: hard_fail 增加: ${bHardFail} → ${cHardFail}`);
  } else if (cHardFail < bHardFail) {
    result.comparisons.push({
      type: 'hard_fail',
      current: cHardFail,
      baseline: bHardFail,
      status: 'pass',
      message: `hard_fail 减少: ${bHardFail} → ${cHardFail}`
    });
  }

  // 3. Render skip 检查
  const cRenderStatus = current.render_status ?? current.status ?? '';
  const bRenderStatus = baseline.render_status ?? baseline.status ?? '';
  if (bRenderStatus !== 'skip' && cRenderStatus === 'skip') {
    result.comparisons.push({
      type: 'render_skip',
      current: cRenderStatus,
      baseline: bRenderStatus,
      status: 'warning',
      message: '渲染从可用变为 skip'
    });
    result.verdict.push(`WARNING: 渲染从可用变为 skip`);
  }

  // 4. 新增/减少的 benchmark
  const cBenchmarks = current.benchmarks ? Object.keys(current.benchmarks) : [];
  const bBenchmarks = baseline.benchmarks ? Object.keys(baseline.benchmarks) : [];
  const newBenchmarks = cBenchmarks.filter(b => !bBenchmarks.includes(b));
  const removedBenchmarks = bBenchmarks.filter(b => !cBenchmarks.includes(b));

  if (newBenchmarks.length > 0) {
    result.comparisons.push({
      type: 'new_benchmarks',
      current: newBenchmarks,
      baseline: [],
      status: 'pass',
      message: `新增 benchmark: ${newBenchmarks.join(', ')}`
    });
  }
  if (removedBenchmarks.length > 0) {
    result.comparisons.push({
      type: 'removed_benchmarks',
      current: [],
      baseline: removedBenchmarks,
      status: 'warning',
      message: `移除 benchmark: ${removedBenchmarks.join(', ')}`
    });
    result.verdict.push(`WARNING: 移除了 benchmark: ${removedBenchmarks.join(', ')}`);
  }

  // 逐 benchmark 比较（如果双方都有）
  if (current.benchmarks && baseline.benchmarks) {
    for (const name of bBenchmarks) {
      if (!current.benchmarks[name]) continue;
      const cScore = current.benchmarks[name].score;
      const bScore = baseline.benchmarks[name].score;
      if (cScore === undefined || bScore === undefined) continue;
      const diff = cScore - bScore;
      if (diff < -SCORE_THRESHOLD) {
        result.verdict.push(`FAIL: "${name}" 分数从 ${bScore} 降至 ${cScore}`);
        result.pass = false;
      }
    }
  }

  return result;
}

function main() {
  const currentPath = args.find(a => !a.startsWith('--') && a.endsWith('.json'));
  const baselinePath = args.filter(a => !a.startsWith('--') && a.endsWith('.json'))[1];

  if (!currentPath || !baselinePath) {
    console.error('用法: node compare_render_baseline.js <current-summary.json> <baseline-summary.json> [--json]');
    process.exit(1);
  }

  const current = loadJSON(path.resolve(currentPath));
  const baseline = loadJSON(path.resolve(baselinePath));

  const result = compareSummaries(current, baseline);

  if (jsonFlag) {
    console.log(JSON.stringify(result, null, 2));
  } else {
    console.log('\n=== 基线比较报告 ===\n');
    for (const c of result.comparisons) {
      const icon = c.status === 'pass' ? '✓' : c.status === 'fail' ? '✗' : '!';
      console.log(`  [${icon}] ${c.message}`);
    }
    console.log('');
    console.log(`结论: ${result.pass ? '通过' : '失败'}`);
    console.log('');
  }

  process.exit(result.pass ? 0 : 1);
}

main();
