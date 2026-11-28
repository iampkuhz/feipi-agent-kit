/**
 * 修复 PPTX 中重复的 cNvPr id。
 * pptxgenjs 有时会为多个元素分配相同的 id，触发 PowerPoint repair。
 * 本脚本解压 → 修复 → 重新打包。
 */

'use strict';

const fs = require('fs');
const path = require('path');
const { execSync } = require('child_process');

/**
 * 修复单个 XML 文件中的重复 cNvPr id。
 * @param {string} xmlContent - XML 字符串
 * @returns {string} 修复后的 XML
 */
function deduplicateCnvpIds(xmlContent) {
  const seen = new Set();
  let nextId = 100;

  return xmlContent.replace(/(cNvPr\s+id=")(\d+)(")/g, (match, prefix, idStr, suffix) => {
    const id = parseInt(idStr, 10);
    if (seen.has(id)) {
      nextId++;
      return `${prefix}${nextId}${suffix}`;
    }
    seen.add(id);
    return match;
  });
}

/**
 * 修复 PPTX 文件中所有 slide XML 的重复 cNvPr id。
 * @param {string} pptxPath - PPTX 文件路径
 * @returns {{ success: boolean, error: string|null }}
 */
function fixDuplicateCnvpIds(pptxPath) {
  try {
    if (!fs.existsSync(pptxPath)) {
      return { success: false, error: `PPTX 文件不存在: ${pptxPath}` };
    }

    const tmpDir = path.join(path.dirname(pptxPath), '_pptx_tmp');
    if (fs.existsSync(tmpDir)) {
      fs.rmSync(tmpDir, { recursive: true, force: true });
    }

    // Unzip
    execSync(`unzip -o "${pptxPath}" -d "${tmpDir}" 2>/dev/null`, { stdio: 'pipe' });

    // Fix all slide XML files
    const slidesDir = path.join(tmpDir, 'ppt', 'slides');
    let changed = false;
    if (fs.existsSync(slidesDir)) {
      const slideFiles = fs.readdirSync(slidesDir).filter(f => f.startsWith('slide') && f.endsWith('.xml'));
      for (const file of slideFiles) {
        const filePath = path.join(slidesDir, file);
        const xml = fs.readFileSync(filePath, 'utf-8');
        const fixed = deduplicateCnvpIds(xml);
        if (fixed !== xml) {
          fs.writeFileSync(filePath, fixed, 'utf-8');
          changed = true;
        }
      }
    }

    // Repack
    if (changed) {
      execSync(`cd "${tmpDir}" && zip -u "${pptxPath}" ppt/slides/slide*.xml 2>/dev/null`, { stdio: 'pipe' });
    }

    // Cleanup
    fs.rmSync(tmpDir, { recursive: true, force: true });

    return { success: true, error: null };
  } catch (e) {
    // Cleanup on error
    try {
      const tmpDir = path.join(path.dirname(pptxPath), '_pptx_tmp');
      if (fs.existsSync(tmpDir)) {
        fs.rmSync(tmpDir, { recursive: true, force: true });
      }
    } catch (_) {}

    return { success: false, error: `修复 cNvPr id 失败: ${e.message}` };
  }
}

module.exports = {
  deduplicateCnvpIds,
  fixDuplicateCnvpIds
};
