#!/usr/bin/env node
'use strict';

/**
 * render_pptx.js — PPTX 渲染 manifest 生成器
 *
 * 正常模式（由 render_pptx.sh 调用）:
 *   node render_pptx.js <input.pptx> <output_dir> <renderer>
 *
 * Skip 模式（LibreOffice 不可用时）:
 *   node render_pptx.js --skip <input.pptx> <output_dir>
 *
 * 输出 JSON manifest 到 stdout，同时写入 <output_dir>/render-manifest.json。
 */

const path = require('path');
const fs = require('fs');

// 加载 manifest helper
const SKILL_DIR = path.join(__dirname, '..');
const manifest = require(path.join(SKILL_DIR, 'helpers', 'render', 'manifest'));

const args = process.argv.slice(2);

// --- Skip 模式 ---
if (args[0] === '--skip') {
  const inputPptx = args[1] || '';
  const outputDir = args[2] || '';
  if (outputDir) {
    fs.mkdirSync(outputDir, { recursive: true });
  }
  const result = {
    input_pptx: inputPptx ? path.resolve(inputPptx) : null,
    output_dir: outputDir ? path.resolve(outputDir) : null,
    slides: [],
    renderer: 'none',
    status: 'skip',
    skip_reason: 'LibreOffice/soffice 未安装，无法渲染 PPTX 为 PNG。',
    skip_install_hint: {
      macos: 'brew install --cask libreoffice',
      linux_apt: 'sudo apt-get install libreoffice',
      linux_dnf: 'sudo dnf install libreoffice'
    }
  };
  const manifestPath = path.join(outputDir || '.', 'render-manifest.json');
  manifest.writeManifest(result, manifestPath);
  console.log(JSON.stringify(result, null, 2));
  process.exit(0);
}

// --- 正常模式 ---
if (args.length < 3) {
  console.error('用法: node render_pptx.js <input.pptx> <output_dir> <renderer>');
  console.error('  或: node render_pptx.js --skip <input.pptx> <output_dir>');
  process.exit(1);
}

const inputPptx = path.resolve(args[0]);
const outputDir = path.resolve(args[1]);
const renderer = args[2];

// 扫描 PNG 输出
const slides = manifest.scanPngSlides(outputDir, inputPptx, args.length > 3 ? args.slice(3) : undefined);

// 构建 manifest
const result = manifest.buildManifest(inputPptx, outputDir, slides, renderer);

// 写入文件 + stdout
const manifestPath = path.join(outputDir, 'render-manifest.json');
manifest.writeManifest(result, manifestPath);
console.log(JSON.stringify(result, null, 2));
