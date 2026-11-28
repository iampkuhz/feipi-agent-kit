/**
 * Render Manifest 工具集
 * 解析 PPTX→PNG 渲染结果，生成 manifest JSON。
 */

'use strict';

const fs = require('fs');
const path = require('path');

/**
 * 解析 PNG 文件头获取宽高（无需外部依赖）。
 * PNG IHDR chunk 位于 byte 16-23，4 byte width + 4 byte height (big-endian).
 */
function parsePngHeader(filePath) {
  const buf = fs.readFileSync(filePath);
  if (buf.length < 24) return null;
  // PNG signature: 89 50 4E 47 0D 0A 1A 0A
  if (buf[0] !== 0x89 || buf[1] !== 0x50 || buf[2] !== 0x4E || buf[3] !== 0x47) {
    return null;
  }
  const width = buf.readUInt32BE(16);
  const height = buf.readUInt32BE(20);
  return { width, height };
}

/**
 * 扫描输出目录，为每个 PNG 生成 slide 条目。
 * 假设 LibreOffice 输出文件名形如: <basename>-1.png, <basename>-2.png, ...
 * 或者 slide1.png, slide2.png, ...
 * 按文件名排序后分配 index。
 */
function scanPngSlides(outputDir, inputPptx, selectedFiles) {
  const files = (selectedFiles || fs.readdirSync(outputDir))
    .filter(f => f.toLowerCase().endsWith('.png'))
    .sort();
  if (files.some(file => path.basename(file) !== file) || new Set(files).size !== files.length) {
    throw new Error('PNG 清单必须为无重复的本目录文件名');
  }

  const slides = [];
  for (const file of files) {
    const filePath = path.join(outputDir, file);
    const stat = fs.statSync(filePath);
    const dims = parsePngHeader(filePath);
    slides.push({
      index: slides.length + 1,
      image_path: filePath,
      width_px: dims ? dims.width : null,
      height_px: dims ? dims.height : null,
      file_size_bytes: stat.size,
      source_file: file
    });
  }
  return slides;
}

/**
 * 构建完整 manifest 对象。
 */
function buildManifest(inputPptx, outputDir, slides, renderer) {
  const status = slides.length > 0 && slides.every(s => s.file_size_bytes > 0)
    ? 'pass'
    : 'fail';

  return {
    input_pptx: path.resolve(inputPptx),
    output_dir: path.resolve(outputDir),
    slides,
    renderer,
    status
  };
}

/**
 * 将 manifest 写入文件。
 */
function writeManifest(manifest, outputPath) {
  const dir = path.dirname(outputPath);
  if (!fs.existsSync(dir)) {
    fs.mkdirSync(dir, { recursive: true });
  }
  fs.writeFileSync(outputPath, JSON.stringify(manifest, null, 2), 'utf-8');
  return outputPath;
}

module.exports = {
  parsePngHeader,
  scanPngSlides,
  buildManifest,
  writeManifest
};
