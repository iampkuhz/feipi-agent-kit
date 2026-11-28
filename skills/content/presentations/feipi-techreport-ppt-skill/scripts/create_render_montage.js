#!/usr/bin/env node
/**
 * create_render_montage.js — 生成渲染结果 HTML 浏览页面。
 *
 * 用法:
 *   node scripts/create_render_montage.js <render-root-dir> <output.html> [--json]
 *
 * 如果 render 不可用，montage 仍会列出 skip 状态。
 */
'use strict';

const path = require('path');
const fs = require('fs');
const montage = require('../helpers/render/montage');
const visualScore = require('../helpers/render/visual-score');

const args = process.argv.slice(2);
const jsonFlag = args.includes('--json');
const inputDir = args.find(a => !a.startsWith('--') && !a.endsWith('.html') && !a.endsWith('.htm'));
const outputHtml = args.find(a => a.endsWith('.html') || a.endsWith('.htm'));

if (!inputDir || !outputHtml) {
  console.error('用法: node create_render_montage.js <render-root-dir> <output.html> [--json]');
  process.exit(1);
}

const resolvedInput = path.resolve(inputDir);
const resolvedOutput = path.resolve(outputHtml);

if (!fs.existsSync(resolvedInput)) {
  console.error(`错误: 目录不存在: ${resolvedInput}`);
  process.exit(1);
}

// Scan results
const results = montage.scanBenchmarkResults(resolvedInput);

// Compute scores for each benchmark
const scores = {};
for (const bm of results) {
  try {
    scores[bm.name] = visualScore.computeScore(bm.manifest);
  } catch {
    scores[bm.name] = { score: 'N/A', issues: [] };
  }
}

// Generate HTML
const html = montage.generateHtml(results, scores);
const outputPath = montage.writeHtml(html, resolvedOutput);

if (jsonFlag) {
  console.log(JSON.stringify({
    benchmarks: results.map(r => ({
      name: r.name,
      status: r.status,
      score: scores[r.name]?.score,
      slides: r.manifest?.slides?.length || 0,
      png_files: r.png_files.length
    })),
    output: outputPath
  }, null, 2));
} else {
  console.log(`Montage 已生成: ${outputPath}`);
  console.log(`Benchmark 数量: ${results.length}`);
  for (const bm of results) {
    const score = scores[bm.name]?.score ?? 'N/A';
    console.log(`  ${bm.name}: status=${bm.status}, score=${score}/100, slides=${bm.manifest?.slides?.length || 0}, png=${bm.png_files.length}`);
  }
}
