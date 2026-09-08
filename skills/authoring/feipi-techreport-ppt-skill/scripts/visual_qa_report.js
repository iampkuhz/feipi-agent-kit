#!/usr/bin/env node
'use strict';

/**
 * visual_qa_report.js — 渲染后视觉 QA 报告
 *
 * 用法:
 *   node visual_qa_report.js <render-manifest.json> [--json]
 *
 * 检查项（轻量级，不引入重依赖）:
 *   1. slide image 是否存在。
 *   2. 文件是否非空 (>0 byte)。
 *   3. 宽高比例是否接近 16:9（误差 10% 内）。
 *   4. 是否存在 0 byte 或异常小图片 (<1KB)。
 *   5. 生成人工/模型检查 checklist。
 *
 * 注意：这些自动检查只能证明渲染证据可用，不能证明页面没有重叠、
 * 裁剪、缺字或视觉层级问题。没有显式视觉复核时不得输出 pass。
 *
 * 输出:
 *   --json 模式: JSON 结构化报告
 *   默认:       中文可读摘要
 */

const path = require('path');
const fs = require('fs');

// 加载 manifest helper 用于 PNG header 解析
const SKILL_DIR = path.join(__dirname, '..');
const manifest = require(path.join(SKILL_DIR, 'helpers', 'render', 'manifest'));

const args = process.argv.slice(2);
const jsonMode = args.includes('--json');
const manifestPath = args.find(a => !a.startsWith('--'));

if (!manifestPath) {
  console.error('用法: node visual_qa_report.js <render-manifest.json> [--json]');
  process.exit(1);
}

if (!fs.existsSync(manifestPath)) {
  console.error(`错误: Manifest 文件不存在: ${manifestPath}`);
  process.exit(1);
}

const manifestData = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));

// --- 如果渲染被 skip，直接报告 ---
if (manifestData.status === 'skip') {
  const report = {
    status: 'skip',
    summary: {
      slides_checked: 0,
      hard_fail: 0,
      warning: 0
    },
    issues: [
      {
        severity: 'warning',
        type: 'render_unavailable',
        message: manifestData.skip_reason || '无法进行完整视觉 QA',
        detail: manifestData.skip_install_hint || null
      }
    ],
    manual_checklist: [
      '在 PowerPoint/LibreOffice 中打开 PPTX，手动检查以下项目',
      '检查文本是否被裁剪',
      '检查箭头是否穿过文字',
      '检查主视觉是否清晰',
      '检查元素是否有重叠或遮挡',
      '检查表格是否可读',
      '检查脚注是否在页面底部且不与主体重叠'
    ],
    note: 'Render QA 无法自动执行，因为缺少渲染引擎（LibreOffice/soffice）。' +
      '请安装 LibreOffice 后重新运行 render_pptx.sh 以启用自动化 Render QA。'
  };

  if (jsonMode) {
    console.log(JSON.stringify(report, null, 2));
  } else {
    printReport(report);
  }
  process.exit(0);
}

// --- 执行检查 ---
const issues = [];
const slides = manifestData.slides || [];
let slidesChecked = 0;

// 16:9 目标比例
const TARGET_RATIO = 16 / 9;
const RATIO_TOLERANCE = 0.10; // 10%

for (const slide of slides) {
  slidesChecked++;
  const imgPath = slide.image_path;

  // 检查 1: 文件是否存在
  if (!imgPath || !fs.existsSync(imgPath)) {
    issues.push({
      severity: 'hard_fail',
      type: 'slide_image_missing',
      slide_index: slide.index,
      message: `Slide ${slide.index}: 图片文件不存在 (${imgPath || '无路径'})`
    });
    continue;
  }

  // 检查 2: 文件是否非空
  const stat = fs.statSync(imgPath);
  if (stat.size === 0) {
    issues.push({
      severity: 'hard_fail',
      type: 'slide_image_empty',
      slide_index: slide.index,
      message: `Slide ${slide.index}: 图片文件大小为 0 byte`
    });
    continue;
  }

  // 检查 3: 文件是否异常小
  if (stat.size < 1024) {
    issues.push({
      severity: 'warning',
      type: 'slide_image_too_small',
      slide_index: slide.index,
      message: `Slide ${slide.index}: 图片文件异常小 (${stat.size} bytes)，可能渲染不完整`,
      detail: { file_size_bytes: stat.size }
    });
  }

  // 检查 4: 解析 PNG header 获取实际宽高
  const dims = manifest.parsePngHeader(imgPath);
  if (dims) {
    // 更新 manifest 中的宽高（如果之前未提供）
    slide.width_px = dims.width;
    slide.height_px = dims.height;

    // 检查 5: 宽高比例是否接近 16:9
    const actualRatio = dims.width / dims.height;
    const ratioDeviation = Math.abs(actualRatio - TARGET_RATIO) / TARGET_RATIO;

    if (ratioDeviation > RATIO_TOLERANCE) {
      issues.push({
        severity: 'warning',
        type: 'aspect_ratio_mismatch',
        slide_index: slide.index,
        message: `Slide ${slide.index}: 宽高比 ${dims.width}×${dims.height} (${actualRatio.toFixed(2)}:1) 偏离 16:9 超过 ${RATIO_TOLERANCE * 100}%`,
        detail: {
          width: dims.width,
          height: dims.height,
          actual_ratio: parseFloat(actualRatio.toFixed(4)),
          expected_ratio: 1.7778,
          deviation: parseFloat((ratioDeviation * 100).toFixed(1)) + '%'
        }
      });
    }
  } else {
    issues.push({
      severity: 'warning',
      type: 'png_header_invalid',
      slide_index: slide.index,
      message: `Slide ${slide.index}: 无法解析 PNG 文件头，可能不是有效的 PNG 图片`,
      detail: { file_path: imgPath, file_size_bytes: stat.size }
    });
  }
}

// 计算 summary
const hardFail = issues.filter(i => i.severity === 'hard_fail').length;
const warnings = issues.filter(i => i.severity === 'warning').length;

const report = {
  status: hardFail > 0 ? 'fail' : 'needs_visual_review',
  automatic_status: hardFail > 0 ? 'fail' : 'pass',
  visual_review_required: hardFail === 0,
  summary: {
    slides_checked: slidesChecked,
    hard_fail: hardFail,
    warning: warnings
  },
  issues,
  manual_checklist: [
    '检查文本是否被裁剪',
    '检查箭头是否穿过文字',
    '检查主视觉是否清晰',
    '检查元素是否有重叠或遮挡',
    '检查表格是否可读',
    '检查 bullet 间距是否足够',
    '检查字号是否过小（正文 < 10pt）',
    '检查脚注是否在页面底部且不与主体重叠',
    '检查颜色对比度是否足够',
    '检查是否有 placeholder 残留文本',
    '检查页面是否有明确的 takeaway 结论',
    '检查 CTO 是否能在 30 秒内理解主结论'
  ]
};

// --- 输出 ---
if (jsonMode) {
  console.log(JSON.stringify(report, null, 2));
} else {
  printReport(report);
}

function printReport(report) {
  const statusIcon = report.status === 'fail' ? '[FAIL]' : report.status === 'skip' ? '[SKIP]' : '[REVIEW]';
  console.log(`\n=== 视觉 QA 报告 ${statusIcon} ===\n`);
  console.log(`渲染引擎: ${manifestData.renderer || '未知'}`);
  console.log(`检查页数: ${report.summary.slides_checked}`);
  console.log();

  if (report.issues.length === 0) {
    console.log('自动渲染证据检查通过；尚未完成全尺寸视觉复核。');
  } else {
    for (const issue of report.issues) {
      const icon = issue.severity === 'hard_fail' ? '[✗]' : '[!]';
      console.log(`  ${icon} ${issue.message}`);
    }
    console.log();
  }

  console.log(`\n手动检查清单 (请在 PowerPoint/LibreOffice 中打开 PPTX 后逐一确认):\n`);
  for (let i = 0; i < report.manual_checklist.length; i++) {
    console.log(`  ${i + 1}. ${report.manual_checklist[i]}`);
  }
  console.log();

  if (report.summary.hard_fail > 0) {
    console.log('存在硬失败，需要修复后重新渲染。');
    console.log('修复后可重新运行: bash scripts/render_pptx.sh <pptx> <output_dir>');
  }
  if (report.status === 'needs_visual_review') {
    console.log('当前结果不是视觉通过；完成全尺寸人工/模型检查后方可签署视觉验收。');
  }
  console.log('================================\n');
}
