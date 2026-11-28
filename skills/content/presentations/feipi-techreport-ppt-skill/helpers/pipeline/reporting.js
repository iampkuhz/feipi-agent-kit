/**
 * Pipeline Reporting — 构建带 timing、cache、artifact 信息的报告。
 */
'use strict';

/**
 * 构建完整的 pipeline report。
 * @param {Object} options
 * @param {Object} options.slideIR - Slide IR
 * @param {Object} options.staticQA - Static QA report
 * @param {Object} options.renderQA - Render QA report
 * @param {Object} options.buildResult - PPTX build result
 * @param {Object} options.qualityScore - quality score result
 * @param {Object} options.cacheInfo - {hit: boolean, key: string|null}
 * @param {Array} options.timingSteps - timing summary
 * @param {string} options.outputDir - output directory
 * @param {Object} options.capabilities - dependency capabilities
 * @param {Object} options.repairHistory - repair attempts
 * @returns {Object}
 */
function buildReport(options) {
  const {
    slideIR,
    staticQA,
    renderQA,
    buildResult,
    qualityScore,
    cacheInfo,
    timingSteps,
    outputDir,
    capabilities,
    repairHistory
  } = options;

  const hardFailCount = (staticQA?.summary?.hard_fail || 0) +
                        (renderQA?.summary?.hard_fail || 0);
  const warningCount = (staticQA?.summary?.warning || 0) +
                       (renderQA?.summary?.warning || 0);

  const status = hardFailCount > 0 ? 'fail' :
                 qualityScore?.score < 60 ? 'fail' :
                 'pass';

  return {
    slide_id: slideIR?.slide_id || 'unknown',
    layout_pattern: slideIR?.layout_pattern || 'unknown',
    status,
    quality_score: qualityScore?.score ?? null,
    summary: {
      hard_fail: hardFailCount,
      warning: warningCount,
      total_elements: slideIR?.elements?.length || 0
    },
    cache: {
      hit: cacheInfo?.hit || false,
      key: cacheInfo?.key || null
    },
    capabilities: capabilities || {},
    timing: timingSteps || [],
    artifacts: {
      output_dir: outputDir || null,
      pptx_path: buildResult?.pptx_path || null,
      render_manifest: renderQA ? 'render-manifest.json' : null
    },
    repair_history: repairHistory || [],
    static_qa: staticQA || null,
    render_qa: renderQA || null
  };
}

/**
 * 格式化 report 为可读中文输出。
 * @param {Object} report
 * @returns {string}
 */
function formatReportText(report) {
  const lines = [];
  lines.push(`=== Pipeline Report ===`);
  lines.push(`Slide: ${report.slide_id}`);
  lines.push(`Layout: ${report.layout_pattern}`);
  lines.push(`Status: ${report.status}`);

  if (report.quality_score !== null) {
    lines.push(`Quality: ${report.quality_score}/100`);
  }

  lines.push(`Hard Fail: ${report.summary.hard_fail}`);
  lines.push(`Warnings: ${report.summary.warning}`);
  lines.push('');

  // Cache
  if (report.cache.hit) {
    lines.push(`Cache: HIT (${report.cache.key})`);
  } else {
    lines.push(`Cache: MISS${report.cache.key ? ` (key: ${report.cache.key})` : ''}`);
  }

  // Capabilities
  if (Object.keys(report.capabilities || {}).length > 0) {
    lines.push('');
    lines.push('Capabilities:');
    for (const [k, v] of Object.entries(report.capabilities)) {
      lines.push(`  ${k}: ${JSON.stringify(v)}`);
    }
  }

  // Timing
  if (report.timing?.length > 0) {
    lines.push('');
    lines.push('Timing:');
    for (const t of report.timing) {
      const ms = t.duration_ms ? `${t.duration_ms}ms` : 'N/A';
      const skip = t.skipped_reason ? ` (skipped: ${t.skipped_reason})` : '';
      lines.push(`  ${t.name}: ${ms} [${t.status}]${skip}`);
    }
  }

  return lines.join('\n');
}

module.exports = { buildReport, formatReportText };
