#!/usr/bin/env node
'use strict';

/**
 * Slide IR 静态布局检测器
 * 用法: node inspect_slide_ir_layout.js <slide-ir.json> [--json]
 * 默认输出中文摘要，--json 输出完整 JSON report。
 * 失败时退出码非 0。
 * 不依赖外部 npm 包。
 */

const fs = require('fs');
const path = require('path');

// 解析参数
const args = process.argv.slice(2);
const jsonFlag = args.includes('--json');
const filePath = args.find(a => !a.startsWith('--'));

if (!filePath) {
  console.error('用法: node inspect_slide_ir_layout.js <slide-ir.json> [--json]');
  process.exit(1);
}

const resolvedPath = path.resolve(filePath);
let raw;
try {
  raw = fs.readFileSync(resolvedPath, 'utf-8');
} catch (e) {
  console.error(`错误: 无法读取文件 ${resolvedPath}`);
  console.error(e.message);
  process.exit(1);
}

let slideIR;
try {
  slideIR = JSON.parse(raw);
} catch (e) {
  console.error('错误: JSON 解析失败');
  console.error(e.message);
  process.exit(1);
}

// 加载静态 QA 引擎
const helpersDir = path.join(__dirname, '..', 'helpers');
const staticQA = require(path.join(helpersDir, 'static-qa.js'));

const report = staticQA.runStaticQA(slideIR);

if (jsonFlag) {
  console.log(JSON.stringify(report, null, 2));
} else {
  console.log(`\n文件: ${resolvedPath}`);
  console.log(`slide_id: ${slideIR.slide_id}`);
  console.log(`layout_pattern: ${slideIR.layout_pattern}`);
  console.log(`elements: ${slideIR.elements ? slideIR.elements.length : 0} 个`);
  console.log('');
  console.log('## 静态 QA 报告');
  console.log('');
  console.log(`综合判定: ${report.status === 'pass' ? '通过' : '失败'}`);
  console.log(`- Hard Fail: ${report.summary.hard_fail}`);
  console.log(`- Warning: ${report.summary.warning}`);
  console.log(`- Acceptable (有意): ${report.summary.acceptable_intentional}`);
  console.log('');

  if (report.summary.hard_fail > 0) {
    console.log('### Hard Fail');
    for (const issue of report.issues) {
      if (issue.severity === 'hard_fail') {
        console.log(`  [✗] ${issue.message}`);
        console.log(`      修复: ${issue.suggestion}`);
      }
    }
    console.log('');
  }

  if (report.summary.warning > 0) {
    console.log('### Warning');
    for (const issue of report.issues) {
      if (issue.severity === 'warning') {
        console.log(`  [!] ${issue.message}`);
        console.log(`      建议: ${issue.suggestion}`);
      }
    }
    console.log('');
  }

  if (report.summary.acceptable_intentional > 0) {
    console.log('### Acceptable (有意)');
    for (const issue of report.issues) {
      if (issue.severity === 'acceptable_intentional') {
        console.log(`  [✓] ${issue.message}`);
      }
    }
    console.log('');
  }

  if (report.summary.hard_fail === 0 && report.summary.warning === 0 && report.summary.acceptable_intentional === 0) {
    console.log('所有检查项通过，未发现问题。');
    console.log('');
  }
}

process.exit(report.status === 'pass' ? 0 : 1);
