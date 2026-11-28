#!/usr/bin/env node
/**
 * 运行时环境诊断：输出中文能力矩阵、缺失依赖和启用建议。
 * 不自动安装任何依赖。
 *
 * 从与锁文件匹配的本机共享缓存只读探测；不使用全局 npm 包。
 */
const { computePipelineLevel } = require('../helpers/pipeline/level');
const { execSync } = require('child_process');
const path = require('path');
const dependency = require('../helpers/dependencies');
const fs = require('fs');

const SCRIPT_DIR = __dirname;
const SKILL_DIR = path.join(SCRIPT_DIR, '..');

function detectNode() {
  return { available: true, version: process.version.replace(/^v/, '') };
}

function detectModule(name) {
  return dependency.info(name);
}

function detectCommand(cmd) {
  try {
    const p = execSync(`command -v ${cmd}`, { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
    return { available: true, path: p };
  } catch {
    return { available: false };
  }
}

function main() {
  const jsonMode = process.argv.includes('--json');

  const node = detectNode();
  const pptxgenjs = detectModule('pptxgenjs');
  const soffice = detectCommand('soffice');
  const libreoffice = detectCommand('libreoffice');
  const renderAvailable = soffice.available || libreoffice.available;
  const renderEngine = soffice.available ? 'soffice' : (libreoffice.available ? 'libreoffice' : null);

  // Compute pipeline level using shared helper
  const capabilities = {
    pptxgenjs: { available: pptxgenjs.available },
    render: { status: renderAvailable ? 'available' : 'unavailable' },
  };
  const pipelineLevel = computePipelineLevel(capabilities);

  // Detect what tests would be skipped
  const skippedTests = [];
  if (!pptxgenjs.available) skippedTests.push('PPTX 编译测试（build_pptx_from_ir.js）');
  if (!renderAvailable) skippedTests.push('Render QA 测试（render_pptx.sh / visual_qa_report.js 渲染部分）');
  if (!renderAvailable && !pptxgenjs.available) skippedTests.push('完整 Pipeline 运行测试（仅可运行 dry-run 模式）');

  if (jsonMode) {
    const result = {
      node,
      pptxgenjs,
      soffice,
      libreoffice,
      render: { status: renderAvailable ? 'available' : 'unavailable', engine: renderEngine },
      pipeline_level: pipelineLevel,
      skipped_tests: skippedTests,
    };
    process.stdout.write(JSON.stringify(result, null, 2) + '\n');
    return;
  }

  // Human-readable output
  console.log('=== feipi-techreport-ppt-skill 运行时诊断 ===\n');

  console.log(`Node.js:     ${node.available ? '✅ v' + node.version : '❌ 未安装'}`);
  console.log(`pptxgenjs:   ${pptxgenjs.available ? '✅ v' + pptxgenjs.version + ' (' + pptxgenjs.location + ')' : '❌ 未安装  （' + pptxgenjs.install_hint + '）'}`);
  console.log(`soffice:     ${soffice.available ? '✅ ' + soffice.path : '❌ 未安装'}`);
  console.log(`libreoffice: ${libreoffice.available ? '✅ ' + libreoffice.path : '❌ 未安装'}`);
  console.log(`渲染引擎:    ${renderAvailable ? '✅ ' + renderEngine : '❌ 不可用'}`);
  console.log('');

  // Pipeline level
  console.log(`Pipeline 级别: ${pipelineLevel}`);
  console.log('');

  // Capability matrix
  console.log('--- 当前可运行能力 ---');
  console.log('  ✅ Slide IR 校验（validate_slide_ir.js）');
  console.log('  ✅ Static QA 检查（inspect_slide_ir_layout.js）');
  console.log('  ✅ Pipeline dry-run 模式');

  if (pptxgenjs.available) {
    console.log('  ✅ PPTX 编译（build_pptx_from_ir.js）');
    console.log('  ✅ Pipeline 完整运行（no-render 模式）');
  }
  if (renderAvailable) {
    console.log('  ✅ Render QA（PPTX → PNG → 视觉报告）');
    console.log('  ✅ Pipeline 完整运行（含渲染）');
  }
  console.log('');

  // Skipped tests
  if (skippedTests.length > 0) {
    console.log('--- 将被跳过的测试 ---');
    skippedTests.forEach(t => console.log('  ⏭  ' + t));
    console.log('');
  }

  // Enable full chain
  console.log('--- 三档验收说明 ---');
  console.log('');
  console.log('1. static-only（当前）:');
  console.log('   仅验证 Slide IR 结构、静态 QA、provenance、容量');
  console.log('   不需要任何 npm 依赖或外部工具');
  console.log('');
  console.log('2. pptx-build:');
  console.log('   需要 pptxgenjs: cd ' + SKILL_DIR + ' && python3 scripts/prepare_runtime.py');
  console.log('   可编译 IR → PPTX，验证布局和无重叠');
  console.log('');
  console.log('3. full visual/render:');
  console.log('   需要 pptxgenjs + LibreOffice');
  console.log('   可渲染 PPTX → PNG，进行像素级视觉对比');
  if (process.platform === 'darwin') {
    console.log('   安装 LibreOffice: brew install --cask libreoffice');
  } else if (process.platform === 'linux') {
    console.log('   安装 LibreOffice: apt-get install libreoffice');
  } else {
    console.log('   安装 LibreOffice: https://www.libreoffice.org/');
  }
  console.log('');
  console.log('注意：本脚本不会自动安装任何依赖。');
}

main();
