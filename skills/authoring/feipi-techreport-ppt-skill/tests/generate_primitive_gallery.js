#!/usr/bin/env node
/**
 * generate_primitive_gallery.js — 生成 Primitive Gallery 回归测试 PPTX。
 *
 * 用法:
 *   node tests/generate_primitive_gallery.js [--output <dir>]
 *
 * 从 tests/fixtures/primitive-gallery.slide-ir.json 生成单页 PPTX，
 * 覆盖所有原子组件类型的正常样例和压力样例。
 */
'use strict';

const path = require('path');
const fs = require('fs');

const SCRIPT_DIR = __dirname;
const SKILL_DIR = path.join(SCRIPT_DIR, '..');
const FIXTURE_PATH = path.join(SKILL_DIR, 'tests', 'fixtures', 'primitive-gallery.slide-ir.json');
const DEFAULT_OUTPUT = path.join(SKILL_DIR, 'tmp', 'primitive-gallery');

const args = process.argv.slice(2);
const outputIdx = args.indexOf('--output');
const outputDir = outputIdx >= 0 ? path.resolve(args[outputIdx + 1]) : DEFAULT_OUTPUT;

// 检查依赖
function detectModule(name) {
  try {
    const pkgJson = require.resolve(name + '/package.json');
    const pkg = JSON.parse(fs.readFileSync(pkgJson, 'utf-8'));
    return { available: true, version: pkg.version };
  } catch {
    return { available: false };
  }
}

const pptxgenjs = detectModule('pptxgenjs');

if (!fs.existsSync(outputDir)) {
  fs.mkdirSync(outputDir, { recursive: true });
}

console.log(`Primitive Gallery 输出目录: ${outputDir}`);
console.log(`pptxgenjs: ${pptxgenjs.available ? 'v' + pptxgenjs.version : '不可用'}`);
console.log('');

if (!pptxgenjs.available) {
  console.log('pptxgenjs 未安装，无法生成 PPTX。');
  console.log(`安装: cd ${SKILL_DIR} && npm install`);
  process.exit(1);
}

if (!fs.existsSync(FIXTURE_PATH)) {
  console.log(`Fixture 不存在: ${FIXTURE_PATH}`);
  process.exit(1);
}

const PptxGenJS = require('pptxgenjs');
const theme = require(path.join(SKILL_DIR, 'helpers', 'pptx', 'theme.js'));
const compiler = require(path.join(SKILL_DIR, 'helpers', 'pptx', 'compiler.js'));

async function main() {
  const ir = JSON.parse(fs.readFileSync(FIXTURE_PATH, 'utf-8'));

  const builder = compiler.BUILDERS[ir.layout_pattern];
  if (!builder) {
    console.log(`不支持的 layout_pattern: "${ir.layout_pattern}"`);
    process.exit(1);
  }

  const pres = new PptxGenJS();
  const canvasSize = theme.getCanvasSize(ir.canvas);
  pres.defineLayout({ name: 'Custom', width: canvasSize.width_in, height: canvasSize.height_in });

  try {
    const summary = builder.build(pres, ir, theme);

    const outputPath = path.join(outputDir, 'primitive-gallery.pptx');
    await pres.writeFile({ outputType: 'nodefs', fileName: outputPath });

    if (!fs.existsSync(outputPath) || fs.statSync(outputPath).size === 0) {
      console.log('PPTX 未生成或文件大小为 0');
      process.exit(1);
    }

    // 生成 manifest
    const manifest = {
      status: 'ok',
      output_path: outputPath,
      layout_pattern: ir.layout_pattern,
      elements_rendered: summary.elements_rendered,
      element_kinds: [...new Set(ir.elements.map(e => e.kind))],
      region_count: ir.regions.length,
      qa_baseline_layers: [
        'Token Gate',
        'Text Box Gate',
        'Primitive Gate',
        'Composition Gate',
        'Page Gate'
      ],
      coverage: {
        primitives_tested: summary.elements_rendered,
        primitives_total: ir.elements.length,
        kinds: [...new Set(ir.elements.map(e => e.kind))]
      }
    };

    const manifestPath = path.join(outputDir, 'primitive-gallery-manifest.json');
    fs.writeFileSync(manifestPath, JSON.stringify(manifest, null, 2), 'utf-8');

    console.log(`PPTX: ${outputPath}`);
    console.log(`Manifest: ${manifestPath}`);
    console.log(`Elements: ${summary.elements_rendered}/${ir.elements.length}`);
    console.log(`Kinds: ${manifest.element_kinds.join(', ')}`);
    console.log('');
    console.log('状态: OK');
  } catch (e) {
    console.log(`构建失败: ${e.message}`);
    process.exit(1);
  }
}

main();
