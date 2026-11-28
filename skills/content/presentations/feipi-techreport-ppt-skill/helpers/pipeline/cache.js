/**
 * Pipeline Cache — 基于输入 hash 的结果缓存。
 * 避免重复 Static QA、PPTX 编译、Render QA。
 *
 * 缓存键由以下输入计算：
 *   - Slide IR (JSON string)
 *   - Style lock (JSON string)
 *   - Backend version
 *   - Script version
 *
 * 默认写入 tmp/ppt-skill-cache/
 */
'use strict';

const fs = require('fs');
const path = require('path');
const crypto = require('crypto');

const CACHE_DIR = path.resolve(process.cwd(), 'tmp', 'ppt-skill-cache');

/**
 * 计算缓存键。
 * @param {Object} slideIR - Slide IR
 * @param {Object} styleLock - Optional style lock
 * @param {Object} versions - {backend: string, scripts: string}
 * @returns {string} hash
 */
function computeCacheKey(slideIR, styleLock, versions) {
  const input = JSON.stringify({
    slide_ir: {
      slide_id: slideIR.slide_id,
      layout_pattern: slideIR.layout_pattern,
      elements: slideIR.elements,
      regions: slideIR.regions,
      canvas: slideIR.canvas
    },
    style_lock: styleLock || null,
    backend_version: versions?.backend || 'unknown',
    scripts_version: versions?.scripts || 'unknown'
  });

  return crypto.createHash('sha256').update(input).digest('hex').slice(0, 16);
}

/**
 * 获取缓存目录。
 * @param {string} cacheKey
 * @returns {string}
 */
function getCacheDir(cacheKey) {
  return path.join(CACHE_DIR, cacheKey);
}

/**
 * 检查缓存是否存在。
 * @param {string} cacheKey
 * @returns {{hit: boolean, dir: string|null}}
 */
function check(cacheKey) {
  const dir = getCacheDir(cacheKey);
  if (fs.existsSync(dir)) {
    const metaPath = path.join(dir, 'cache-meta.json');
    if (fs.existsSync(metaPath)) {
      const meta = JSON.parse(fs.readFileSync(metaPath, 'utf-8'));
      return { hit: true, dir, meta };
    }
  }
  return { hit: false, dir, meta: null };
}

/**
 * 读取缓存结果。
 * @param {string} cacheKey
 * @returns {Object|null} cached result or null
 */
function read(cacheKey) {
  const { hit, dir } = check(cacheKey);
  if (!hit || !dir) return null;

  const result = {};
  const files = fs.readdirSync(dir);
  for (const f of files) {
    if (f.endsWith('.json')) {
      const name = f.replace('.json', '');
      try {
        result[name] = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf-8'));
      } catch { /* skip invalid */ }
    }
  }
  return result;
}

/**
 * 写入缓存。
 * @param {string} cacheKey
 * @param {Object} results - {qa_static, solved_ir, build_result, render_manifest, quality_score}
 * @param {Object} meta - optional metadata
 * @returns {string} cache dir
 */
function write(cacheKey, results, meta) {
  const dir = getCacheDir(cacheKey);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }

  for (const [name, data] of Object.entries(results)) {
    if (data !== undefined && data !== null) {
      fs.writeFileSync(path.join(dir, `${name}.json`), JSON.stringify(data, null, 2), 'utf-8');
    }
  }

  const cacheMeta = {
    cache_key: cacheKey,
    created_at: new Date().toISOString(),
    ...meta
  };
  fs.writeFileSync(path.join(dir, 'cache-meta.json'), JSON.stringify(cacheMeta, null, 2), 'utf-8');

  return dir;
}

/**
 * 清理缓存。
 * @param {Object} options - {all: boolean, olderThanDays: number}
 * @returns {number} number of entries removed
 */
function clean(options = {}) {
  if (!fs.existsSync(CACHE_DIR)) return 0;

  const entries = fs.readdirSync(CACHE_DIR);
  let removed = 0;

  for (const entry of entries) {
    const dir = path.join(CACHE_DIR, entry);
    if (!fs.statSync(dir).isDirectory()) continue;

    if (options.all) {
      fs.rmSync(dir, { recursive: true, force: true });
      removed++;
      continue;
    }

    if (options.olderThanDays) {
      const metaPath = path.join(dir, 'cache-meta.json');
      if (fs.existsSync(metaPath)) {
        const meta = JSON.parse(fs.readFileSync(metaPath, 'utf-8'));
        const created = new Date(meta.created_at);
        const ageDays = (Date.now() - created.getTime()) / (1000 * 60 * 60 * 24);
        if (ageDays > options.olderThanDays) {
          fs.rmSync(dir, { recursive: true, force: true });
          removed++;
        }
      }
    }
  }

  return removed;
}

/**
 * 获取缓存统计。
 * @returns {Object}
 */
function stats() {
  if (!fs.existsSync(CACHE_DIR)) return { total_entries: 0, total_size_bytes: 0 };

  const entries = fs.readdirSync(CACHE_DIR);
  let totalSize = 0;
  let validEntries = 0;

  for (const entry of entries) {
    const dir = path.join(CACHE_DIR, entry);
    if (!fs.statSync(dir).isDirectory()) continue;
    validEntries++;

    // Sum file sizes
    const files = fs.readdirSync(dir);
    for (const f of files) {
      const fp = path.join(dir, f);
      if (fs.statSync(fp).isFile()) {
        totalSize += fs.statSync(fp).size;
      }
    }
  }

  return { total_entries: validEntries, total_size_bytes: totalSize };
}

module.exports = { computeCacheKey, check, read, write, clean, stats, CACHE_DIR };
