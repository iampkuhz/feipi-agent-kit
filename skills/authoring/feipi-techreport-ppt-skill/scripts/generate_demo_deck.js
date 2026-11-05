#!/usr/bin/env node
/**
 * generate_demo_deck.js — 生成 Demo deck。
 *
 * 用法:
 *   node scripts/generate_demo_deck.js [--output <dir>] [--no-render]
 *   node scripts/generate_demo_deck.js  # 默认输出到 tmp/ppt-skill-v2-run/full-release/demo/
 *
 * 从 benchmark 中选择多页生成 demo PPTX。
 * 优先覆盖：架构图、流程图、对比矩阵。
 */
'use strict';

const path = require('path');
const dependency = require('../helpers/dependencies');
const fs = require('fs');
const { execSync } = require('child_process');

const SCRIPT_DIR = __dirname;
const SKILL_DIR = path.join(SCRIPT_DIR, '..');
const BENCHMARK_DIR = path.join(SKILL_DIR, 'fixtures', 'benchmarks');
const REPO_ROOT = path.resolve(SCRIPT_DIR, '..', '..', '..', '..');
const DEFAULT_OUTPUT = path.join(REPO_ROOT, 'tmp', 'ppt-skill-v2-run', 'full-release', 'demo');

const args = process.argv.slice(2);
const noRender = args.includes('--no-render');
const outputIdx = args.indexOf('--output');
const outputDir = outputIdx >= 0 ? path.resolve(args[outputIdx + 1]) : DEFAULT_OUTPUT;

if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

// 选择要包含的 benchmark — 必须覆盖 architecture、flow、comparison 三个核心场景
const DEMO_BENCHMARKS = [
  { name: 'architecture-high-density', desc: '架构图（高密度）', scenario: 'architecture' },
  { name: 'flow-api-lifecycle', desc: 'API 生命周期流程图', scenario: 'flow' },
  { name: 'comparison-competitive-matrix', desc: '竞品对比矩阵', scenario: 'comparison' },
];

// 检查依赖
function detectModule(name) {
  try { dependency(name); return dependency.info(name); }
  catch { return { available: false }; }
}

function detectCommand(cmd) {
  try {
    execSync(`command -v ${cmd}`, { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] });
    return true;
  } catch {
    return false;
  }
}

const pptxgenjs = detectModule('pptxgenjs');
const renderAvailable = detectCommand('soffice') || detectCommand('libreoffice');
const renderEngine = detectCommand('soffice') ? 'soffice' : (detectCommand('libreoffice') ? 'libreoffice' : null);

const results = [];

console.log(`Demo deck 输出目录: ${outputDir}`);
console.log(`pptxgenjs: ${pptxgenjs.available ? '✅ v' + pptxgenjs.version : '❌ 不可用'}`);
console.log(`渲染引擎: ${renderAvailable ? '✅ ' + renderEngine : '❌ 不可用'}`);
console.log('');

if (!pptxgenjs.available) {
  console.log('⚠ pptxgenjs 未安装，无法生成 PPTX demo deck。');
  console.log('');
  console.log('安装方法:');
  console.log(`  cd ${SKILL_DIR} && python3 scripts/prepare_runtime.py`);
  console.log('');
  console.log('Demo 覆盖场景:');

  const manifest = {
    status: 'skip',
    reason: 'pptxgenjs 未安装',
    output_dir: outputDir,
    scenarios: DEMO_BENCHMARKS.map(b => ({
      name: b.name,
      desc: b.desc,
      scenario: b.scenario,
      ir_exists: fs.existsSync(path.join(BENCHMARK_DIR, b.name, 'slide-ir.json'))
    })),
    instruction: '安装 pptxgenjs 后重新运行: python3 scripts/prepare_runtime.py && node scripts/generate_demo_deck.js'
  };

  for (const b of DEMO_BENCHMARKS) {
    const irPath = path.join(BENCHMARK_DIR, b.name, 'slide-ir.json');
    const exists = fs.existsSync(irPath);
    console.log(`  ${exists ? '✅' : '❌'} ${b.scenario} — ${b.desc} (IR: ${exists ? '存在' : '缺失'})`);
    results.push({ name: b.name, scenario: b.scenario, status: exists ? 'ir_exists' : 'ir_missing' });
  }

  console.log('');
  const manifestPath = path.join(outputDir, 'demo-manifest.json');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf-8');
  console.log(`Demo manifest: ${manifestPath}`);
  console.log('');
  console.log('状态: SKIP（pptxgenjs 未安装）');
  process.exit(0);
}

// pptxgenjs 可用，生成 demo deck
const PptxGenJS = dependency('pptxgenjs');
const theme = require(path.join(SKILL_DIR, 'helpers', 'pptx', 'theme.js'));
const compiler = require(path.join(SKILL_DIR, 'helpers', 'pptx', 'compiler.js'));

async function main() {
  // 生成合并的 demo deck
  const pres = new PptxGenJS();

  for (const bm of DEMO_BENCHMARKS) {
    const irPath = path.join(BENCHMARK_DIR, bm.name, 'slide-ir.json');
    if (!fs.existsSync(irPath)) {
      console.log(`  [SKIP] ${bm.scenario} — ${bm.desc}: IR 不存在`);
      results.push({ name: bm.name, scenario: bm.scenario, status: 'ir_missing' });
      continue;
    }

    const ir = JSON.parse(fs.readFileSync(irPath, 'utf-8'));

    const builder = compiler.BUILDERS[ir.layout_pattern];
    if (!builder) {
      console.log(`  [SKIP] ${bm.scenario} — ${bm.desc}: 不支持的 layout_pattern "${ir.layout_pattern}"`);
      results.push({ name: bm.name, scenario: bm.scenario, status: 'unsupported_pattern' });
      continue;
    }

    try {
      builder.build(pres, ir, theme);
      console.log(`  [OK] ${bm.scenario} — ${bm.desc}: ${ir.elements?.length || 0} 个元素`);
      results.push({ name: bm.name, scenario: bm.scenario, status: 'ok', elements: ir.elements?.length || 0 });
    } catch (e) {
      console.log(`  [FAIL] ${bm.scenario} — ${bm.desc}: ${e.message}`);
      results.push({ name: bm.name, scenario: bm.scenario, status: 'fail', error: e.message });
    }
  }

  // 写入合并的 demo deck
  const mergedPath = path.join(outputDir, 'demo-deck.pptx');
  await pres.writeFile({ outputType: 'nodefs', fileName: mergedPath });

  // 验证合并 deck 存在且非空
  if (!fs.existsSync(mergedPath) || fs.statSync(mergedPath).size === 0) {
    console.error('\n错误: demo deck 未生成或文件大小为 0');
    process.exit(1);
  }

  // 也生成单独的单页 PPTX
  for (const bm of DEMO_BENCHMARKS) {
    const irPath = path.join(BENCHMARK_DIR, bm.name, 'slide-ir.json');
    if (!fs.existsSync(irPath)) continue;

    const ir = JSON.parse(fs.readFileSync(irPath, 'utf-8'));
    const builder = compiler.BUILDERS[ir.layout_pattern];
    if (!builder) continue;

    const singlePres = new PptxGenJS();
    try {
      builder.build(singlePres, ir, theme);
      const singlePath = path.join(outputDir, `demo-${bm.name}.pptx`);
      await singlePres.writeFile({ outputType: 'nodefs', fileName: singlePath });
    } catch { /* skip */ }
  }

  // 生成 demo manifest
  const anyFail = results.some(r => r.status === 'fail');
  const manifest = {
    status: anyFail ? 'partial' : 'ok',
    output_dir: outputDir,
    demo_deck: mergedPath,
    individual_decks: DEMO_BENCHMARKS.map(b => ({
      name: b.name,
      scenario: b.scenario,
      path: path.join(outputDir, `demo-${b.name}.pptx`)
    })),
    benchmarks: results,
    total_slides: results.filter(r => r.status === 'ok').length,
    scenarios_covered: [...new Set(results.filter(r => r.status === 'ok').map(r => r.scenario))],
    render: {
      available: renderAvailable,
      engine: renderEngine,
      status: renderAvailable ? 'available' : 'unavailable'
    }
  };

  const manifestPath = path.join(outputDir, 'demo-manifest.json');
  fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf-8');

  // 如果渲染工具可用，生成 PNG 和 montage
  let renderResult = null;
  if (renderAvailable && !noRender) {
    console.log('');
    console.log('渲染工具可用，生成 PNG...');
    try {
      const renderScript = path.join(SCRIPT_DIR, 'render_pptx.sh');
      if (fs.existsSync(renderScript)) {
        const pngDir = path.join(outputDir, 'png');
        fs.mkdirSync(pngDir, { recursive: true });
        execSync(`bash "${renderScript}" "${mergedPath}" "${pngDir}"`, { encoding: 'utf-8', stdio: 'pipe' });
        console.log(`  PNG 输出: ${pngDir}`);
        renderResult = { status: 'ok', png_dir: pngDir };
      }
    } catch (e) {
      console.log(`  渲染失败: ${e.message}`);
      renderResult = { status: 'fail', error: e.message };
    }
  }

  console.log('');
  console.log(`Demo deck: ${mergedPath}`);
  console.log(`Demo manifest: ${manifestPath}`);
  console.log(`Slides: ${results.filter(r => r.status === 'ok').length}/${DEMO_BENCHMARKS.length}`);
  console.log(`Scenarios: ${manifest.scenarios_covered.join(', ')}`);

  if (renderResult?.status === 'ok') {
    console.log(`Render: ${renderResult.png_dir}`);
  }
}

main();
