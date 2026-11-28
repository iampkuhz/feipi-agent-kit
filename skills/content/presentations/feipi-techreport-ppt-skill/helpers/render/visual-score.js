/**
 * Visual Score — 基于 render manifest + static QA + post-check 的 proxy score。
 * 不是完整的审美判断，是工程质量代理分。
 */
'use strict';

const TARGET_RATIO = 16 / 9;
const RATIO_TOLERANCE = 0.10;
const SMALL_FILE_THRESHOLD = 1024; // bytes

/**
 * 计算视觉 proxy score (0-100)。
 *
 * @param {Object} renderManifest - render manifest JSON
 * @param {Object} staticQaReport - optional static QA report
 * @param {Object} postcheckResult - optional postcheck result
 * @returns {{score: number, breakdown: Object, issues: Array}}
 */
function computeScore(renderManifest, staticQaReport, postcheckResult) {
  let score = 100;
  const breakdown = {};
  const issues = [];

  // 1. Render availability
  if (!renderManifest || renderManifest.status === 'skip') {
    score -= 30; // 工程分：无法渲染
    issues.push({ type: 'render_unavailable', deduction: 30, message: '渲染引擎不可用，-30 工程分' });
  }

  // 2. Image checks
  const slides = renderManifest?.slides || [];
  let imageIssues = 0;
  for (const slide of slides) {
    const imgPath = slide.image_path;

    if (!imgPath) {
      issues.push({ type: 'no_image_path', deduction: 40, message: `Slide ${slide.index}: 无图片路径` });
      score -= 40;
      continue;
    }

    if (slide.file_size_bytes === 0 || slide.file_size_bytes === undefined) {
      issues.push({ type: 'image_missing', deduction: 40, message: `Slide ${slide.index}: 图片缺失` });
      score -= 40;
      continue;
    }

    // Small image
    if (slide.file_size_bytes < SMALL_FILE_THRESHOLD) {
      score -= 10;
      issues.push({ type: 'image_too_small', deduction: 10, message: `Slide ${slide.index}: 图片异常小 (${slide.file_size_bytes} bytes)` });
    }

    // Aspect ratio
    if (slide.width_px && slide.height_px) {
      const actualRatio = slide.width_px / slide.height_px;
      const ratioDeviation = Math.abs(actualRatio - TARGET_RATIO) / TARGET_RATIO;
      if (ratioDeviation > RATIO_TOLERANCE) {
        score -= 5;
        issues.push({ type: 'aspect_ratio_mismatch', deduction: 5, message: `Slide ${slide.index}: 宽高比偏离 16:9` });
      }
    }
  }
  breakdown.image_checks = imageIssues;

  // 3. Static QA hard_fail
  const hardFails = staticQaReport?.summary?.hard_fail || 0;
  const warnings = staticQaReport?.summary?.warning || 0;
  if (hardFails > 0) {
    score -= Math.min(40, hardFails * 10);
    issues.push({ type: 'static_qa_hard_fail', deduction: Math.min(40, hardFails * 10), message: `Static QA hard_fail: ${hardFails} 项` });
  }
  if (warnings > 0) {
    score -= Math.min(15, warnings * 2);
    issues.push({ type: 'static_qa_warning', deduction: Math.min(15, warnings * 2), message: `Static QA warning: ${warnings} 项` });
  }
  breakdown.static_qa = { hard_fail: hardFails, warnings };

  // 4. Post-check issues
  const pcIssues = postcheckResult?.issues || [];
  for (const pcIssue of pcIssues) {
    if (pcIssue.severity === 'hard_fail') {
      score -= 15;
      issues.push({ type: 'postcheck_fail', deduction: 15, message: pcIssue.message });
    }
  }
  breakdown.postcheck = pcIssues.length;

  // 5. Editable score from postcheck (if available)
  // Future: postcheck could report editability score

  // Clamp
  score = Math.max(0, Math.min(100, score));

  return { score, breakdown, issues };
}

/**
 * 格式化分数报告。
 * @param {Object} scoreResult - computeScore 返回值
 * @param {string} format - 'text' | 'json'
 * @returns {string|Object}
 */
function formatReport(scoreResult, format) {
  if (format === 'json') return scoreResult;

  const lines = [
    '=== 质量 Proxy Score 报告 ===',
    '',
    `分数: ${scoreResult.score}/100`,
    `Static QA: hard_fail=${scoreResult.breakdown.static_qa?.hard_fail || 0}, warnings=${scoreResult.breakdown.static_qa?.warnings || 0}`,
  ];

  if (scoreResult.issues.length > 0) {
    lines.push('');
    lines.push('扣分项:');
    for (const issue of scoreResult.issues) {
      lines.push(`  [-${issue.deduction}] ${issue.message}`);
    }
  } else {
    lines.push('');
    lines.push('无扣分项。');
  }
  lines.push('');

  return lines.join('\n');
}

module.exports = { computeScore, formatReport };
