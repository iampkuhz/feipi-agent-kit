#!/usr/bin/env node
'use strict';

// 仓库开发入口，不进入安装副本；复用当前 Render Plan 和原生 PPTX 后端。
// node tests/generate_demo_deck.js [--output <dir>] [--no-render]
const fs = require('fs');
const os = require('os');
const path = require('path');
const { spawnSync } = require('child_process');
const { compileRenderPlan } = require('../compiler/render-plan-compiler');
const { PptxGenJSBackend } = require('../adapters/pptxgenjs/backend');

const SKILL_DIR = path.resolve(__dirname, '..');
const BENCHMARKS = [
  { name: 'architecture-high-density', scenario: 'architecture' },
  { name: 'flow-api-lifecycle', scenario: 'flow' },
  { name: 'comparison-competitive-matrix', scenario: 'comparison' },
];
const args = process.argv.slice(2);
const index = args.indexOf('--output');
if (index >= 0 && (!args[index + 1] || args[index + 1].startsWith('--'))) {
  console.error('--output 必须提供目录');
  process.exit(1);
}
const outputDir = index >= 0 ? path.resolve(args[index + 1]) : fs.mkdtempSync(path.join(os.tmpdir(), 'feipi-ppt-demo-'));
const manifest = { status: 'fail', visual_review: 'pending', output_dir: outputDir, benchmarks: [], total_slides: 0,
  individual_decks: [], scenarios_covered: [], render: { status: 'not_requested' } };
fs.mkdirSync(outputDir, { recursive: true });
const manifestPath = path.join(outputDir, 'demo-manifest.json');

async function main() {
  const backend = new PptxGenJSBackend();
  const plans = [];
  for (const benchmark of BENCHMARKS) {
    const input = path.join(__dirname, 'fixtures', 'benchmarks', benchmark.name, 'slide-ir.json');
    const plan = compileRenderPlan(JSON.parse(fs.readFileSync(input, 'utf8')));
    const output = path.join(outputDir, `demo-${benchmark.name}.pptx`);
    await backend.write(plan, output);
    plans.push(plan);
    manifest.benchmarks.push({ ...benchmark, status: 'ok', elements: plan.elements.length });
    manifest.individual_decks.push({ ...benchmark, path: output });
  }
  manifest.demo_deck = path.join(outputDir, 'demo-deck.pptx');
  await backend.write(plans, manifest.demo_deck);
  manifest.total_slides = plans.length;
  manifest.scenarios_covered = BENCHMARKS.map(item => item.scenario);
  if (!args.includes('--no-render')) {
    const pngDir = path.join(outputDir, 'png');
    const rendered = spawnSync('bash', [path.join(SKILL_DIR, 'scripts', 'render_pptx.sh'),
      manifest.demo_deck, pngDir, '--json'], { encoding: 'utf8' });
    if (rendered.error || rendered.status !== 0) throw new Error(rendered.error?.message || rendered.stderr || '演示渲染失败');
    manifest.render = JSON.parse(rendered.stdout);
    if (manifest.render.slides?.length !== plans.length) throw new Error('实际 PNG 数量与演示页数不符');
    if (manifest.render.status !== 'pass' && manifest.render.status !== 'ok') {
      throw new Error(`演示渲染未完成: ${manifest.render.status}`);
    }
  }
  manifest.status = 'ok';
}

main().catch(error => {
  manifest.error = error.message;
  console.error(error.message);
  process.exitCode = 1;
}).finally(() => {
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2) + '\n');
  console.log(`Demo manifest: ${manifestPath}`);
  console.log(`Slides: ${manifest.total_slides}/${BENCHMARKS.length}`);
});
