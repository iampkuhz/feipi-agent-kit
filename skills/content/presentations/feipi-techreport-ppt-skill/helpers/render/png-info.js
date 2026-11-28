/**
 * PNG Info — 轻量 PNG header 解析。
 * 读取 width, height, bit depth, color type，不引入外部依赖。
 */
'use strict';

const fs = require('fs');

/**
 * 解析 PNG 文件头。
 * @param {string} filePath
 * @returns {{width: number, height: number, bit_depth: number|null, color_type: number|null, file_size_bytes: number}|null}
 */
function pngInfo(filePath) {
  if (!fs.existsSync(filePath)) return null;
  const buf = fs.readFileSync(filePath);
  if (buf.length < 29) return null; // PNG header 最小长度

  // PNG signature: 89 50 4E 47 0D 0A 1A 0A
  if (buf[0] !== 0x89 || buf[1] !== 0x50 || buf[2] !== 0x4E || buf[3] !== 0x47) {
    return null;
  }

  // IHDR chunk: width (4 bytes BE) + height (4 bytes BE) at offset 16
  const width = buf.readUInt32BE(16);
  const height = buf.readUInt32BE(20);

  // bit depth + color type at offset 24, 25
  const bitDepth = buf.length > 24 ? buf[24] : null;
  const colorType = buf.length > 25 ? buf[25] : null;

  return {
    width,
    height,
    bit_depth: bitDepth,
    color_type: colorType,
    file_size_bytes: buf.length
  };
}

/**
 * 批量解析多个 PNG 文件。
 * @param {string[]} filePaths
 * @returns {Object<string, object|null>} keyed by path
 */
function pngInfoBatch(filePaths) {
  const results = {};
  for (const fp of filePaths) {
    results[fp] = pngInfo(fp);
  }
  return results;
}

module.exports = { pngInfo, pngInfoBatch };
