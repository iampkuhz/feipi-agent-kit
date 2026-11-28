#!/usr/bin/env node
/**
 * PPTX 产物反检 CLI
 * 解析已生成的 PPTX 文件，输出结构信息用于验证。
 *
 * 用法:
 *   node scripts/inspect_pptx_artifact.js <output.pptx> [--json] [--expected-slides <n>] [--release]
 *
 * 选项:
 *   --help, -h          显示帮助信息并 exit 0
 *   --json              输出 JSON 格式
 *   --expected-slides   期望的幻灯片数量（用于验证）
 *   --release           release 模式：母版残留等视为 hard_fail
 */
'use strict';

const path = require('path');
const fs = require('fs');
const postcheck = require('../helpers/pptx/postcheck');

function printHelp() {
  console.log(`用法: node inspect_pptx_artifact.js <output.pptx> [选项]

选项:
  --help, -h              显示此帮助信息
  --json                  输出 JSON 格式结果
  --expected-slides <n>   期望的幻灯片数量
  --release               release 模式（母版残留视为 hard_fail）

示例:
  node scripts/inspect_pptx_artifact.js output.pptx --json
  node scripts/inspect_pptx_artifact.js output.pptx --expected-slides 1 --release
  node scripts/inspect_pptx_artifact.js output.pptx --json --expected-slides 1`);
}

async function main() {
  const args = process.argv.slice(2);

  // Handle --help / -h (must exit 0)
  if (args.includes('--help') || args.includes('-h')) {
    printHelp();
    process.exit(0);
  }

  const jsonFlag = args.includes('--json');
  const releaseMode = args.includes('--release');
  const expectedIdx = args.indexOf('--expected-slides');
  const expectedSlides = expectedIdx >= 0 ? parseInt(args[expectedIdx + 1], 10) : undefined;

  // Find the PPTX file path (non-flag argument that isn't a value for --expected-slides)
  const pptxPath = args.find((a, i) => {
    if (a.startsWith('--') || a === '-h') return false;
    if (i > 0 && args[i - 1] === '--expected-slides') return false;
    return true;
  });

  if (!pptxPath) {
    console.error('错误: 未指定 PPTX 文件路径');
    console.error('使用 --help 查看用法');
    process.exit(1);
  }

  const resolvedPath = path.resolve(pptxPath);

  if (!fs.existsSync(resolvedPath)) {
    console.error(`错误: 文件不存在: ${resolvedPath}`);
    process.exit(1);
  }

  // Inspect structure and run postcheck (both async)
  let structure;
  try {
    structure = await postcheck.inspectPptxStructure(resolvedPath);
  } catch (e) {
    if (jsonFlag) {
      console.log(JSON.stringify({ error: e.message, file: resolvedPath }, null, 2));
    } else {
      console.error(`解析失败: ${e.message}`);
    }
    process.exit(1);
  }

  const result = await postcheck.postcheck(resolvedPath, {
    expectedSlides,
    releaseMode,
  });

  if (jsonFlag) {
    console.log(JSON.stringify({
      file: resolvedPath,
      size_bytes: result.stats?.size_bytes || 0,
      slide_count: structure.slideCount,
      text_elements: structure.texts.length,
      texts: structure.texts,
      master_texts: structure.masterTexts?.length || 0,
      master_texts_sample: (structure.masterTexts || []).slice(0, 10),
      postcheck: { success: result.success, issues: result.issues }
    }, null, 2));
  } else {
    console.log(`PPTX 产物反检报告: ${resolvedPath}`);
    console.log('='.repeat(50));
    console.log(`  文件大小: ${result.stats?.size_bytes || 0} bytes`);
    console.log(`  幻灯片数: ${structure.slideCount}`);
    console.log(`  文本元素: ${structure.texts.length}`);
    console.log('');

    if (structure.texts.length > 0) {
      console.log('  提取的文本:');
      for (const t of structure.texts.slice(0, 20)) {
        console.log(`    - ${t}`);
      }
      if (structure.texts.length > 20) {
        console.log(`    ... 还有 ${structure.texts.length - 20} 条`);
      }
      console.log('');
    }

    if (result.issues.length > 0) {
      console.log(`  问题 (${result.issues.length}):`);
      for (const issue of result.issues) {
        console.log(`    [${issue.severity}] ${issue.message}`);
      }
    } else {
      console.log('  问题: 无');
    }

    console.log('');
    console.log(`  结论: ${result.success ? '通过' : '未通过'}`);
  }

  // Exit code consistent with postcheck success
  process.exit(result.success ? 0 : 1);
}

main();
