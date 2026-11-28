/**
 * Pipeline Timing — 记录每个 pipeline step 的耗时。
 */
'use strict';

/**
 * 创建一个新的 timer tracker。
 * @returns {Object}
 */
function createTimer() {
  return { steps: [], startTime: Date.now() };
}

/**
 * 开始一个 step。
 * @param {Object} timer - createTimer 返回值
 * @param {string} name - step name
 * @returns {Object} step record
 */
function startStep(timer, name) {
  const step = {
    name,
    start_time: new Date().toISOString(),
    end_time: null,
    duration_ms: null,
    status: 'running'
  };
  timer.steps.push(step);
  return step;
}

/**
 * 结束一个 step。
 * @param {Object} timer
 * @param {string} name
 * @param {string} status - 'success' | 'fail' | 'skip'
 * @param {string} skipReason - optional skip reason
 */
function endStep(timer, name, status, skipReason) {
  const step = timer.steps.find(s => s.name === name && s.status === 'running');
  if (!step) return;

  step.end_time = new Date().toISOString();
  step.duration_ms = Date.now() - new Date(step.start_time).getTime();
  step.status = status;
  if (skipReason) step.skipped_reason = skipReason;
}

/**
 * 标记 step 为 skip。
 */
function skipStep(timer, name, reason) {
  endStep(timer, name, 'skip', reason);
}

/**
 * 获取所有 step 的 summary。
 * @param {Object} timer
 * @returns {Array}
 */
function getSummary(timer) {
  const totalMs = timer.steps.reduce((sum, s) => sum + (s.duration_ms || 0), 0);
  return timer.steps.map(s => ({
    name: s.name,
    start_time: s.start_time,
    end_time: s.end_time,
    duration_ms: s.duration_ms,
    status: s.status,
    skipped_reason: s.skipped_reason || null
  })).concat({
    name: '_total',
    duration_ms: totalMs,
    status: 'complete'
  });
}

/**
 * 格式化耗时为可读字符串。
 * @param {number} ms
 * @returns {string}
 */
function formatDuration(ms) {
  if (ms === null || ms === undefined) return 'N/A';
  if (ms < 1000) return `${ms}ms`;
  if (ms < 60000) return `${(ms / 1000).toFixed(1)}s`;
  const mins = Math.floor(ms / 60000);
  const secs = Math.floor((ms % 60000) / 1000);
  return `${mins}m ${secs}s`;
}

module.exports = { createTimer, startStep, endStep, skipStep, getSummary, formatDuration };
