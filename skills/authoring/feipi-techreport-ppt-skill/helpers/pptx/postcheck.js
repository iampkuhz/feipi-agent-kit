/**
 * PPTX Post-check
 * 生成 PPTX 后的产物验证：文件存在性、结构完整性、placeholder 残留、路径泄漏、母版残留、
 * 重复 cNvPr id、默认 fallback 坐标聚集、表格 geometry 风险。
 * 使用 JSZip 解析 PPTX（ZIP 格式），精确统计 slide 数量和提取可见文本。
 */
'use strict';

const fs = require('fs');
const path = require('path');
const JSZip = require('jszip');
const { TokenStore } = require('../../compiler/token-store');
const tokenStore = TokenStore.loadDefault();

// Placeholder 关键词
const PLACEHOLDER_PATTERNS = [
  /\bxxxx\b/i,
  /\blorem\b/i,
  /\bipsum\b/i,
  /\bplaceholder\b/i,
  /\bTBD\b/,
  /\bTODO\b/i,
  /\[insert\s/i,
  /\[待定\]/,
  /\[待补充\]/,
];

// 绝对路径泄漏模式
const PATH_LEAK_PATTERNS = [
  /\/Users\/\w+\/[^\s]{5,}/,
  /\/home\/\w+\/[^\s]{5,}/,
  /C:\\Users\\[^\s]{5,}/i,
];

// 默认母版/模板残留模式
const MASTER_RESIDUAL_PATTERNS = [
  'Click to edit Master text styles',
  'Second level',
  'Third level',
  'Fourth level',
  'Fifth level',
  '‹#›',
  '7/23/19',
];

// 默认 fallback 坐标（extractLayout 的旧默认值）
const FALLBACK_COORD = { x: 0, y: 0, w: 2, h: 0.5 };
const FALLBACK_TOLERANCE = 0.01;
const FALLBACK_CLUSTER_THRESHOLD = 2; // 2+ 元素同时落在 fallback 坐标视为问题

/**
 * 检查文件存在性和基本属性。
 */
function checkFileExists(outputPath) {
  const issues = [];
  if (!fs.existsSync(outputPath)) {
    issues.push({ severity: 'hard_fail', type: 'file_missing', message: `PPTX 文件不存在: ${outputPath}` });
    return { success: false, issues, stats: null };
  }
  const stat = fs.statSync(outputPath);
  if (stat.size === 0) {
    issues.push({ severity: 'hard_fail', type: 'file_empty', message: 'PPTX 文件大小为 0 byte' });
    return { success: false, issues, stats: null };
  }
  return { success: true, issues, stats: { size_bytes: stat.size } };
}

/**
 * 扫描文本中是否残留 placeholder。
 */
function scanPlaceholder(texts) {
  const issues = [];
  for (const t of texts) {
    for (const pat of PLACEHOLDER_PATTERNS) {
      if (pat.test(t)) {
        issues.push({ severity: 'hard_fail', type: 'placeholder_residual', message: `检测到 placeholder 残留: "${t.slice(0, 60)}"` });
        break;
      }
    }
  }
  return issues;
}

/**
 * 扫描文本中是否包含绝对路径泄漏。
 */
function scanPathLeaks(texts) {
  const issues = [];
  for (const t of texts) {
    for (const pat of PATH_LEAK_PATTERNS) {
      const m = t.match(pat);
      if (m) {
        issues.push({ severity: 'hard_fail', type: 'path_leak', message: `检测到绝对路径泄漏: "${m[0].slice(0, 60)}"` });
        break;
      }
    }
  }
  return issues;
}

/**
 * 扫描默认母版/模板残留文本。
 * @param {string[]} texts - 提取的文本数组
 * @param {boolean} releaseMode - release 模式下视为 hard_fail，否则 warning
 * @returns {Array} issues
 */
function scanMasterResidual(texts, releaseMode) {
  const issues = [];
  const severity = releaseMode ? 'hard_fail' : 'warning';
  const seen = new Set();

  for (const t of texts) {
    for (const pattern of MASTER_RESIDUAL_PATTERNS) {
      if (t.includes(pattern) && !seen.has(pattern)) {
        seen.add(pattern);
        issues.push({
          severity,
          type: 'template_master_residual',
          message: `检测到默认母版残留: "${pattern}"`
        });
      }
    }
  }
  return issues;
}

/**
 * 检查同一 slide 内是否有重复的 cNvPr id。
 * OpenXML 要求同一张 slide 内 cNvPr id 唯一。
 * @param {string} slideXml - slide XML 内容
 * @returns {Array} issues
 */
function checkDuplicateCnvrId(slideXml) {
  const issues = [];
  const seenIds = new Map();

  // Match <p:cNvPr id="N" .../> patterns
  const idRegex = /cNvPr\s+id="(\d+)"/g;
  let match;
  while ((match = idRegex.exec(slideXml)) !== null) {
    const id = match[1];
    if (seenIds.has(id)) {
      issues.push({
        severity: 'hard_fail',
        type: 'duplicate_cnvp_id',
        message: `同一 slide 内存在重复 cNvPr id="${id}"，会触发 PowerPoint repair`
      });
      break; // One hard_fail is enough
    }
    seenIds.set(id, true);
  }

  return issues;
}

/**
 * 检测元素是否落在默认 fallback 坐标附近。
 * @param {Object} bounds - { x, y, w, h }
 * @returns {boolean}
 */
function isFallbackCoord(bounds) {
  return Math.abs(bounds.x - FALLBACK_COORD.x) < FALLBACK_TOLERANCE &&
         Math.abs(bounds.y - FALLBACK_COORD.y) < FALLBACK_TOLERANCE &&
         Math.abs(bounds.w - FALLBACK_COORD.w) < FALLBACK_TOLERANCE &&
         Math.abs(bounds.h - FALLBACK_COORD.h) < FALLBACK_TOLERANCE;
}

/**
 * 从 slide XML 中提取所有 shape/text 的坐标信息。
 * @param {string} slideXml - slide XML 内容
 * @returns {Array<{x: number, y: number, w: number, h: number, tag: string}>}
 */
function extractShapeCoords(slideXml) {
  const coords = [];
  // Match <p:sp> blocks with <a:off> and <a:ext> children
  // <a:off x="..." y="..."/> and <a:ext cx="..." cy="..."/>
  // EMU to inches: 1 inch = 914400 EMU
  const EMU_TO_INCH = 1 / 914400;

  // Find all transform blocks within shape contexts
  const xfrmRegex = /<a:off\s+x="(\d+)"\s+y="(\d+)"[^>]*>\s*<\/a:off>\s*<a:ext\s+cx="(\d+)"\s+cy="(\d+)"/g;
  let match;
  while ((match = xfrmRegex.exec(slideXml)) !== null) {
    const x = parseInt(match[1], 10) * EMU_TO_INCH;
    const y = parseInt(match[2], 10) * EMU_TO_INCH;
    const w = parseInt(match[3], 10) * EMU_TO_INCH;
    const h = parseInt(match[4], 10) * EMU_TO_INCH;
    coords.push({ x: parseFloat(x.toFixed(4)), y: parseFloat(y.toFixed(4)), w: parseFloat(w.toFixed(4)), h: parseFloat(h.toFixed(4)) });
  }

  return coords;
}

/**
 * 检查是否有多个元素落在默认 fallback 坐标。
 * @param {Array} shapeCoords - 从 extractShapeCoords 获取的坐标列表
 * @returns {Array} issues
 */
function checkFallbackClustering(shapeCoords) {
  const issues = [];
  const fallbackCount = shapeCoords.filter(c => isFallbackCoord(c)).length;
  if (fallbackCount >= FALLBACK_CLUSTER_THRESHOLD) {
    issues.push({
      severity: 'hard_fail',
      type: 'fallback_coordinate_cluster',
      message: `${fallbackCount} 个元素落在默认 fallback 坐标 (0,0,2,0.5) 附近，可能存在缺失 layout 的元素堆叠在左上角`
    });
  }
  return issues;
}

/**
 * 检查表格 frame 高度与行高一致性。
 * 从 slide XML 中解析 table 结构。
 * @param {string} slideXml - slide XML 内容
 * @returns {Array} issues
 */
function checkTableGeometry(slideXml) {
  const issues = [];
  const EMU_TO_INCH = 1 / 914400;

  // Find table blocks: <a:tbl> with <a:tblPr> (containing tblH) and <a:tr> elements
  // Match table frame height from <a:ext> within the table's parent <a:graphicData>
  // Then match row heights from <a:tr h="...">

  // Extract table regions
  const tableRegex = /<a:graphicData[^>]*>.*?<a:tbl\b[\s\S]*?<\/a:tbl>/g;
  let tableMatch;
  while ((tableMatch = tableRegex.exec(slideXml)) !== null) {
    const tableXml = tableMatch[0];

    // Find table frame height from <a:ext cx="..." cy="..."> before the table
    // Look backward from the table start for the ext
    const beforeTable = slideXml.substring(0, tableMatch.index);
    const extRegex = /<a:ext\s+cx="(\d+)"\s+cy="(\d+)"[^>]*>\s*<\/a:ext>\s*$/;
    const extMatch = extRegex.exec(beforeTable);

    if (extMatch) {
      const frameH = parseInt(extMatch[2], 10) * EMU_TO_INCH;

      // Count rows and sum their heights
      const rowRegex = /<a:tr\s+h="(\d+)"/g;
      let rowMatch;
      let totalRowH = 0;
      let rowCount = 0;
      while ((rowMatch = rowRegex.exec(tableXml)) !== null) {
        totalRowH += parseInt(rowMatch[1], 10) * EMU_TO_INCH;
        rowCount++;
      }

      if (rowCount > 0 && totalRowH > frameH * 1.05) { // Allow 5% tolerance
        issues.push({
          severity: 'warning',
          type: 'table_geometry_mismatch',
          message: `表格 frame 高度 (${frameH.toFixed(2)} inch) 小于行高总和 (${totalRowH.toFixed(2)} inch, ${rowCount} 行)，可能触发 PowerPoint repair`
        });
      }
    }
  }

  return issues;
}

function checkDeterministicText(slideXml) {
  const issues = [];
  if (/<a:(?:spAutoFit|normAutofit)\b/.test(slideXml)) {
    issues.push({ severity: 'hard_fail', type: 'automatic_font_fit', message: '检测到 DrawingML 自动字号，输出不再确定' });
  }
  const allowedSizes = tokenStore.allowedFontSizes({ includeLegacy: false });
  const sizeRegex = /\bsz="(\d+)"/g;
  let match;
  const seen = new Set();
  while ((match = sizeRegex.exec(slideXml)) !== null) {
    const size = Number(match[1]) / 100;
    seen.add(size);
    if (!allowedSizes.has(size)) {
      issues.push({ severity: 'hard_fail', type: 'unregistered_font_size', message: `PPTX 使用未登记字号 ${size}pt` });
    }
  }
  return { issues, fontSizes: [...seen].sort((a, b) => a - b) };
}

function checkSemanticObjectNames(slideXml) {
  const issues = [];
  const names = [];
  const regex = /<p:cNvPr\s+id="(\d+)"\s+name="([^"]*)"/g;
  let match;
  while ((match = regex.exec(slideXml)) !== null) {
    const id = Number(match[1]);
    const name = match[2];
    if (id === 1) continue;
    names.push(name);
    if (!name.startsWith('feipi__')) {
      issues.push({ severity: 'hard_fail', type: 'unstable_object_name', message: `对象 id=${id} 缺少稳定语义名称: ${name || '(empty)'}` });
    }
  }
  if (new Set(names).size !== names.length) {
    issues.push({ severity: 'hard_fail', type: 'duplicate_object_name', message: '同页存在重复 objectName' });
  }
  return { issues, names };
}

function inspectNativeObjects(slideXml) {
  const counts = {
    text_shapes: (slideXml.match(/<p:sp\b/g) || []).length,
    native_tables: (slideXml.match(/<a:tbl\b/g) || []).length,
    native_charts: (slideXml.match(/<c:chart\b/g) || []).length,
    native_lines: (slideXml.match(/<a:prstGeom\s+prst="line"/g) || []).length,
    pictures: (slideXml.match(/<p:pic\b/g) || []).length,
  };
  const issues = [];
  if (counts.pictures > 0 && counts.text_shapes === 0 && counts.native_tables === 0 && counts.native_charts === 0) {
    issues.push({ severity: 'hard_fail', type: 'full_page_image_delivery', message: '页面仅包含图片，缺少原生可编辑内容' });
  }
  return { counts, issues };
}

/**
 * 验证 slide 数量与预期一致。
 */
function checkSlideCount(actualSlides, expectedSlides) {
  if (expectedSlides && actualSlides !== expectedSlides) {
    return [{ severity: 'warning', type: 'slide_count_mismatch', message: `预期 ${expectedSlides} 张幻灯片，实际 ${actualSlides} 张` }];
  }
  return [];
}

/**
 * 使用 JSZip 精确解析 PPTX 结构。
 * 统计 ppt/slides/slide*.xml 文件数量，从 slide XML 中提取可见文本。
 * 同时提取 slideMaster XML 中的文本用于母版残留检测。
 * @param {string} filePath - PPTX 文件路径
 * @returns {Promise<{slideCount: number, texts: string[], masterTexts: string[], slideXmls: Map}>}
 */
async function inspectPptxStructure(filePath) {
  const buffer = fs.readFileSync(filePath);

  // Validate ZIP header (PK)
  if (buffer[0] !== 0x50 || buffer[1] !== 0x4b) {
    throw new Error('Not a valid PPTX/ZIP file');
  }

  const zip = await JSZip.loadAsync(buffer);

  // Count slides: entries matching ppt/slides/slide<N>.xml
  const slideFiles = Object.keys(zip.files).filter(name =>
    /^ppt\/slides\/slide\d+\.xml$/i.test(name)
  ).sort((a, b) => {
    const numA = parseInt(a.match(/slide(\d+)/i)[1], 10);
    const numB = parseInt(b.match(/slide(\d+)/i)[1], 10);
    return numA - numB;
  });

  const slideCount = slideFiles.length;

  // Extract text from slide XMLs only (not from master/theme)
  const texts = [];
  const slideXmls = new Map();
  for (const slideFile of slideFiles) {
    const content = await zip.files[slideFile].async('string');
    slideXmls.set(slideFile, content);
    // <a:t>...</a:t> contains visible text in DrawingML
    const textRegex = /<a:t[^>]*>([^<]*)<\/a:t>/g;
    let match;
    while ((match = textRegex.exec(content)) !== null) {
      const text = match[1].trim();
      if (text) {
        texts.push(text);
      }
    }
  }

  // Also extract text from slideMaster XMLs for master residual detection
  const masterTexts = [];
  const masterFiles = Object.keys(zip.files).filter(name =>
    /^ppt\/slideMasters\/slideMaster\d+\.xml$/i.test(name)
  );
  for (const masterFile of masterFiles) {
    const content = await zip.files[masterFile].async('string');
    const textRegex = /<a:t[^>]*>([^<]*)<\/a:t>/g;
    let match;
    while ((match = textRegex.exec(content)) !== null) {
      const text = match[1].trim();
      if (text) {
        masterTexts.push(text);
      }
    }
  }

  // Also check slideLayout XMLs (placeholders may define default text here)
  const layoutFiles = Object.keys(zip.files).filter(name =>
    /^ppt\/slideLayouts\/slideLayout\d+\.xml$/i.test(name)
  );
  for (const layoutFile of layoutFiles) {
    const content = await zip.files[layoutFile].async('string');
    const textRegex = /<a:t[^>]*>([^<]*)<\/a:t>/g;
    let match;
    while ((match = textRegex.exec(content)) !== null) {
      const text = match[1].trim();
      if (text) {
        masterTexts.push(text);
      }
    }
  }

  return { slideCount, texts, masterTexts, slideXmls };
}

/**
 * 执行 post-check (async).
 * @param {string} outputPath - PPTX 文件路径
 * @param {Object} options - 可选参数
 * @param {number} options.expectedSlides - 预期幻灯片数量
 * @param {string[]} options.expectedTexts - 预期应包含的文本列表
 * @param {boolean} options.releaseMode - release 模式（母版残留视为 hard_fail）
 * @returns {Promise<{success: boolean, issues: Array, stats: Object|null}>}
 */
async function postcheck(outputPath, options = {}) {
  const { expectedSlides, expectedTexts, releaseMode = false } = options;
  const allIssues = [];

  // 1. File existence
  const fileResult = checkFileExists(outputPath);
  if (!fileResult.success) {
    return fileResult;
  }
  allIssues.push(...fileResult.issues);
  const stats = { ...fileResult.stats };

  // 2. PPTX structure inspection via JSZip
  let slideCount = 0;
  let extractedTexts = [];
  let masterTexts = [];
  let slideXmls = new Map();
  const editableObjects = { text_shapes: 0, native_tables: 0, native_charts: 0, native_lines: 0, pictures: 0 };
  const semanticNames = [];
  const fontSizes = new Set();
  try {
    const pptxStructure = await inspectPptxStructure(outputPath);
    slideCount = pptxStructure.slideCount;
    extractedTexts = pptxStructure.texts;
    masterTexts = pptxStructure.masterTexts || [];
    slideXmls = pptxStructure.slideXmls || new Map();
    stats.slide_count = slideCount;
    stats.text_element_count = extractedTexts.length;
    stats.master_text_count = masterTexts.length;
  } catch (e) {
    allIssues.push({ severity: 'warning', type: 'structure_inspect_failed', message: `PPTX 结构解析失败: ${e.message}` });
    stats.structure_inspectable = false;
  }

  // 3. Slide count check
  allIssues.push(...checkSlideCount(slideCount, expectedSlides));

  // 4. XML-level checks: duplicate cNvPr id, fallback coords, table geometry
  for (const [fileName, xmlContent] of slideXmls) {
    allIssues.push(...checkDuplicateCnvrId(xmlContent));
    const shapeCoords = extractShapeCoords(xmlContent);
    allIssues.push(...checkFallbackClustering(shapeCoords));
    allIssues.push(...checkTableGeometry(xmlContent));
    const deterministic = checkDeterministicText(xmlContent);
    allIssues.push(...deterministic.issues);
    deterministic.fontSizes.forEach(size => fontSizes.add(size));
    const naming = checkSemanticObjectNames(xmlContent);
    allIssues.push(...naming.issues);
    semanticNames.push(...naming.names);
    const native = inspectNativeObjects(xmlContent);
    allIssues.push(...native.issues);
    for (const key of Object.keys(editableObjects)) editableObjects[key] += native.counts[key];
  }
  stats.editable_objects = editableObjects;
  stats.semantic_object_names = semanticNames;
  stats.font_sizes_pt = [...fontSizes].sort((a, b) => a - b);

  // 5. Placeholder scan (slide text only)
  if (extractedTexts.length > 0) {
    allIssues.push(...scanPlaceholder(extractedTexts));
    allIssues.push(...scanPathLeaks(extractedTexts));
  }

  // 6. Master residual scan (both slide text and master text)
  const slideMasterIssues = scanMasterResidual(extractedTexts, releaseMode);
  allIssues.push(...slideMasterIssues);

  // Also check master XML itself for default template patterns
  if (masterTexts.length > 0) {
    const masterResiduals = scanMasterResidual(masterTexts, releaseMode);
    if (masterResiduals.length > 0) {
      const masterSeverity = releaseMode ? 'hard_fail' : 'warning';
      allIssues.push({
        severity: masterSeverity,
        type: 'template_master_residual',
        message: `PPTX 使用默认母版模板，包含 ${masterResiduals.length} 处母版占位残留（详见 master XML）`
      });
    }
  }

  // 7. Expected text check
  if (expectedTexts) {
    for (const expected of expectedTexts) {
      const found = extractedTexts.some(t => t.includes(expected));
      if (!found) {
        allIssues.push({ severity: 'warning', type: 'expected_text_missing', message: `预期文本未找到: "${expected.slice(0, 40)}..."` });
      }
    }
  }

  const hasHardFail = allIssues.some(i => i.severity === 'hard_fail');
  return { success: !hasHardFail, issues: allIssues, stats };
}

module.exports = {
  postcheck,
  checkFileExists,
  scanPlaceholder,
  scanPathLeaks,
  scanMasterResidual,
  checkSlideCount,
  inspectPptxStructure,
  // New XML-level checks
  checkDuplicateCnvrId,
  extractShapeCoords,
  checkFallbackClustering,
  checkTableGeometry,
  checkDeterministicText,
  checkSemanticObjectNames,
  inspectNativeObjects,
  MASTER_RESIDUAL_PATTERNS,
  PLACEHOLDER_PATTERNS,
  PATH_LEAK_PATTERNS,
};
