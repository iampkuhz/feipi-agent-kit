/**
 * P0 Pipeline：Validate -> Render Plan -> Static QA -> Build -> Package QA -> Render evidence。
 * 同一 IR hash 不重复执行所谓“修复轮次”。
 */
'use strict';

const crypto = require('crypto');
const fs = require('fs');
const os = require('os');
const path = require('path');
const { execFileSync } = require('child_process');
const staticQA = require('../static-qa');
const classifyIssues = require('../repair/classify-issues');
const repairPlan = require('../repair/repair-plan');
const compiler = require('../pptx/compiler');
const postcheck = require('../pptx/postcheck');
const renderManifest = require('../render/manifest');
const designKitAdapter = require('../design-kit/adapters/compiler-adapter');
const { validateSlideIR } = require('../../compiler/slide-ir-validator');
const { compileRenderPlan, toLegacyQAIR } = require('../../compiler/render-plan-compiler');

function normalizeMode(mode) {
  if (mode === 'draft') return 'fast';
  if (mode === 'production') return 'strict';
  return mode || 'strict';
}

function deriveQAStrategy(mode) {
  const normalized = normalizeMode(mode);
  if (normalized === 'fast') return { allowWarnings: true, renderRequired: false, visualApprovalRequired: false, label: 'fast' };
  if (normalized === 'review') return { allowWarnings: true, renderRequired: true, visualApprovalRequired: false, label: 'review' };
  if (normalized === 'strict') return { allowWarnings: false, renderRequired: true, visualApprovalRequired: true, label: 'strict' };
  throw new Error(`不支持的 mode=${mode}`);
}

function hashIR(value) {
  return crypto.createHash('sha256').update(JSON.stringify(value)).digest('hex');
}

async function runPipeline(input, outputDir, options = {}) {
  const requestedMode = options.mode || 'review';
  const strategy = deriveQAStrategy(requestedMode);
  const render = options.render !== false;
  const dryRun = Boolean(options.dryRun);
  fs.mkdirSync(outputDir, { recursive: true });

  let slideIR = input;
  let sourceFormat = input.version || 'design-kit';
  if (designKitAdapter.isDesignKitSpec(input)) slideIR = designKitAdapter.normalizeToSlideIR(input);
  const report = {
    slide_id: slideIR.slide_id || null,
    layout_pattern: slideIR.layout_id || slideIR.layout_pattern || null,
    mode: strategy.label,
    requested_mode: requestedMode,
    max_rounds: options.maxRounds || 3,
    dry_run: dryRun,
    source_format: sourceFormat,
    input_hash: hashIR(slideIR),
    rounds: [],
    final_status: 'pending',
    final_message: '',
  };

  const validation = validateSlideIR(slideIR);
  if (!validation.valid) {
    report.rounds.push({ round: 1, round_status: 'fail', validation, input_hash: report.input_hash });
    report.final_status = 'fail';
    report.final_message = `Slide IR 校验失败: ${validation.errors.join('; ')}`;
    writeJson(path.join(outputDir, 'pipeline-report.json'), report);
    return report;
  }

  let renderPlan;
  try { renderPlan = compileRenderPlan(slideIR, { sourceVersion: sourceFormat === 'design-kit' ? 'design-kit' : slideIR.version }); }
  catch (error) {
    report.rounds.push({ round: 1, round_status: 'fail', validation, message: error.message, input_hash: report.input_hash });
    report.final_status = 'fail';
    report.final_message = error.message;
    writeJson(path.join(outputDir, 'pipeline-report.json'), report);
    return report;
  }
  writeJson(path.join(outputDir, 'render-plan.json'), renderPlan);
  writeJson(path.join(outputDir, 'geometry-snapshot.json'), {
    slide_id: renderPlan.slide_id,
    geometry_hash: renderPlan.geometry_hash,
    elements: renderPlan.elements.map(element => ({ id: element.id, object_name: element.object_name, bounds_emu: element.bounds_emu })),
  });

  const qaIR = toLegacyQAIR(renderPlan);
  const staticReport = staticQA.runStaticQA(qaIR);
  writeJson(path.join(outputDir, 'qa-static.json'), staticReport);
  const round = {
    round: 1,
    input_hash: report.input_hash,
    render_plan_hash: renderPlan.geometry_hash,
    validation,
    overflow: renderPlan.overflow,
    static_qa: staticReport,
    build_result: null,
    postcheck: null,
    render_qa: null,
    repair_plan: null,
    round_status: 'pending',
  };
  report.rounds.push(round);

  if (staticReport.summary.hard_fail > 0) {
    const classified = classifyIssues.classifyAllIssues(staticReport, null);
    round.repair_plan = repairPlan.generateRepairPlan(classified, qaIR, 1);
    round.round_status = round.repair_plan.requires_user_decision ? 'needs_user_decision' : 'fail';
    report.final_status = round.round_status;
    report.final_message = 'Static QA 未通过；同一 IR hash 不会被无效重跑。';
    writeJson(path.join(outputDir, 'repair-plan.json'), round.repair_plan);
    writeJson(path.join(outputDir, 'pipeline-report.json'), report);
    return report;
  }

  if (renderPlan.overflow.status !== 'fit') {
    round.round_status = renderPlan.overflow.status === 'split_required' ? 'needs_user_decision' : 'fail';
    report.final_status = round.round_status;
    report.final_message = `内容未适配：${renderPlan.overflow.status}；禁止通过生成新字号修复。`;
    writeJson(path.join(outputDir, 'pipeline-report.json'), report);
    return report;
  }

  if (dryRun) {
    round.round_status = 'pass';
    report.final_status = 'pass';
    report.final_message = 'Validate、Render Plan 与 Static QA 通过。';
    writeJson(path.join(outputDir, 'pipeline-report.json'), report);
    return report;
  }

  const pptxPath = path.join(outputDir, 'output.pptx');
  round.build_result = await compiler.compile(slideIR, pptxPath);
  if (!round.build_result.success) {
    round.round_status = 'fail';
    report.final_status = 'fail';
    report.final_message = round.build_result.error;
    writeJson(path.join(outputDir, 'pipeline-report.json'), report);
    return report;
  }

  round.postcheck = await postcheck.postcheck(pptxPath, { expectedSlides: 1, releaseMode: strategy.label === 'strict' });
  writeJson(path.join(outputDir, 'postcheck.json'), round.postcheck);
  if (!round.postcheck.success) {
    round.round_status = 'fail';
    report.final_status = 'fail';
    report.final_message = 'PPTX package/editability QA 未通过。';
    writeJson(path.join(outputDir, 'pipeline-report.json'), report);
    return report;
  }

  if (render) {
    round.render_qa = renderPptxEvidence(pptxPath, path.join(outputDir, 'render'));
    writeJson(path.join(outputDir, 'qa-render.json'), round.render_qa);
    if (round.render_qa.status === 'fail') {
      round.round_status = 'fail';
      report.final_status = 'fail';
      report.final_message = '渲染证据生成失败。';
      writeJson(path.join(outputDir, 'pipeline-report.json'), report);
      return report;
    }
  }

  if (strategy.renderRequired && (!round.render_qa || round.render_qa.status === 'skip')) {
    round.round_status = 'incomplete';
    report.final_status = 'incomplete';
    report.final_message = '当前模式要求渲染证据，但渲染不可用。';
  } else {
    round.round_status = 'pass';
    report.final_status = 'pass';
    report.final_message = strategy.visualApprovalRequired
      ? '自动门禁通过；strict 交付仍须完成全尺寸人工/模型视觉检查。'
      : '自动门禁通过。';
  }
  writeJson(path.join(outputDir, 'pipeline-report.json'), report);
  return report;
}

function commandExists(command) {
  try { execFileSync('/usr/bin/which', [command], { stdio: 'ignore' }); return true; }
  catch { return false; }
}

function renderPptxEvidence(pptxPath, outputDir) {
  fs.mkdirSync(outputDir, { recursive: true });
  let renderer = 'none';
  const issues = [];
  try {
    if (os.platform() === 'darwin' && commandExists('qlmanage')) {
      renderer = 'quicklook-coretext';
      execFileSync('/usr/bin/qlmanage', ['-t', '-s', '1800', '-o', outputDir, pptxPath], { stdio: 'pipe', timeout: 60000 });
    } else if (commandExists('soffice')) {
      renderer = 'libreoffice-compatibility';
      execFileSync('soffice', ['--headless', '--convert-to', 'png', '--outdir', outputDir, pptxPath], { stdio: 'pipe', timeout: 60000 });
    }
  } catch (error) {
    issues.push({ severity: 'hard_fail', type: 'render_failed', message: error.message });
  }
  const slides = renderManifest.scanPngSlides(outputDir, pptxPath);
  const manifest = renderManifest.buildManifest(pptxPath, outputDir, slides, renderer);
  manifest.status = renderer === 'none' ? 'skip' : slides.length > 0 ? 'pass' : 'fail';
  renderManifest.writeManifest(manifest, path.join(outputDir, 'render-manifest.json'));
  if (renderer === 'libreoffice-compatibility') {
    issues.push({ severity: 'warning', type: 'non_authoritative_font_renderer', message: 'LibreOffice 不作为 Kaiti SC 字体权威渲染器' });
  }
  return {
    status: issues.some(issue => issue.severity === 'hard_fail') || manifest.status === 'fail' ? 'fail' : manifest.status,
    renderer,
    summary: { slides_checked: slides.length, hard_fail: issues.filter(issue => issue.severity === 'hard_fail').length, warning: issues.filter(issue => issue.severity === 'warning').length },
    slides,
    issues,
    visual_review_required: slides.length > 0,
    manual_checklist: ['全尺寸检查文字重叠与裁剪', '检查元素越界', '检查连接线端点', '检查 Kaiti SC 中文显示', '检查原生表格可读性'],
  };
}

function writeJson(filePath, data) {
  fs.mkdirSync(path.dirname(filePath), { recursive: true });
  fs.writeFileSync(filePath, JSON.stringify(data, null, 2) + '\n', 'utf-8');
}

module.exports = { runPipeline, writeJson, deriveQAStrategy, normalizeMode, renderPptxEvidence, hashIR };
