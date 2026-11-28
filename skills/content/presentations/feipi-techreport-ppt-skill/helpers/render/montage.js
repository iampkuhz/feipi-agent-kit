/**
 * Montage — 基于渲染结果生成 HTML 浏览页面。
 * 每个 benchmark 展示一张缩略图 + 名称 + QA status + score + issue summary。
 */
'use strict';

const fs = require('fs');
const path = require('path');

/**
 * 扫描渲染目录，收集所有 benchmark 结果。
 * @param {string} renderRootDir - benchmark 渲染根目录
 * @returns {Array<Object>}
 */
function scanBenchmarkResults(renderRootDir) {
  const results = [];
  if (!fs.existsSync(renderRootDir)) return results;

  const entries = fs.readdirSync(renderRootDir);
  for (const name of entries.sort()) {
    const dir = path.join(renderRootDir, name);
    if (!fs.statSync(dir).isDirectory()) continue;

    // 查找 render-manifest.json
    const manifestPath = path.join(dir, 'render-manifest.json');
    if (!fs.existsSync(manifestPath)) continue;

    let manifest;
    try {
      manifest = JSON.parse(fs.readFileSync(manifestPath, 'utf-8'));
    } catch {
      continue;
    }

    // 查找 PNG 文件
    const pngFiles = fs.readdirSync(dir)
      .filter(f => f.toLowerCase().endsWith('.png'))
      .map(f => ({ filename: f, filepath: path.join(dir, f) }));

    results.push({
      name,
      manifest,
      png_files: pngFiles,
      status: manifest.status || 'unknown',
      render_dir: dir
    });
  }
  return results;
}

/**
 * 生成 HTML montage 字符串。
 * @param {Array<Object>} benchmarkResults - scanBenchmarkResults 返回值
 * @param {Object} scores - benchmark name -> score result mapping
 * @returns {string} HTML content
 */
function generateHtml(benchmarkResults, scores) {
  const htmlParts = [];
  htmlParts.push(`<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<title>Render Montage</title>
<style>
  body { font-family: -apple-system, "Segoe UI", sans-serif; margin: 20px; background: #f5f5f5; }
  h1 { color: #333; }
  .grid { display: grid; grid-template-columns: repeat(auto-fill, minmax(500px, 1fr)); gap: 20px; }
  .card { background: white; border-radius: 8px; padding: 16px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
  .card h3 { margin: 0 0 8px; font-size: 14px; color: #555; }
  .card img { width: 100%; border-radius: 4px; }
  .status { display: inline-block; padding: 2px 8px; border-radius: 4px; font-size: 12px; font-weight: bold; }
  .status-pass { background: #d4edda; color: #155724; }
  .status-fail { background: #f8d7da; color: #721c24; }
  .status-skip { background: #fff3cd; color: #856404; }
  .score { font-size: 18px; font-weight: bold; margin: 4px 0; }
  .issues { font-size: 12px; color: #888; }
  .missing { color: #999; font-style: italic; }
</style>
</head>
<body>
<h1>Render Montage</h1>
<p>总计: ${benchmarkResults.length} 个 benchmark</p>
<div class="grid">`);

  for (const bm of benchmarkResults) {
    const score = scores?.[bm.name]?.score ?? 'N/A';
    const statusClass = bm.status === 'pass' ? 'status-pass' :
                        bm.status === 'skip' ? 'status-skip' : 'status-fail';

    htmlParts.push(`<div class="card">`);
    htmlParts.push(`<h3>${bm.name}</h3>`);
    htmlParts.push(`<div><span class="status ${statusClass}">${bm.status}</span> <span class="score">${score}/100</span></div>`);

    if (bm.png_files.length > 0) {
      for (const png of bm.png_files) {
        htmlParts.push(`<img src="${png.filepath}" alt="${bm.name} - ${png.filename}">`);
      }
    } else {
      htmlParts.push(`<p class="missing">无渲染图片</p>`);
    }

    // Issue summary
    const issueCount = bm.manifest?.slides?.length || 0;
    htmlParts.push(`<div class="issues">${issueCount} slide(s) in manifest</div>`);

    htmlParts.push(`</div>`);
  }

  htmlParts.push(`</div></body></html>`);
  return htmlParts.join('\n');
}

/**
 * 将 montage 写入文件。
 * @param {string} html - HTML content
 * @param {string} outputPath - output path (.html)
 * @returns {string} resolved output path
 */
function writeHtml(html, outputPath) {
  const dir = path.dirname(outputPath);
  if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
  fs.writeFileSync(outputPath, html, 'utf-8');
  return path.resolve(outputPath);
}

module.exports = { scanBenchmarkResults, generateHtml, writeHtml };
