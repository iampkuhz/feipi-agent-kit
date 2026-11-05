#!/usr/bin/env node
/**
 * 运行时能力探测：输出 JSON 格式环境状态。
 * 不安装任何依赖，仅探测已安装内容。
 */
const { computePipelineLevel } = require('../helpers/pipeline/level');
const { execSync } = require('child_process');
const path = require('path');
const dependency = require('../helpers/dependencies');

function detectNode() {
  const version = process.version.replace(/^v/, '');
  return { available: true, version };
}

function detectModule(name) {
  return dependency.info(name);
}

function detectCommand(cmd) {
  try {
    const result = execSync(`command -v ${cmd}`, { encoding: 'utf-8', stdio: ['pipe', 'pipe', 'pipe'] }).trim();
    return { available: true, path: result };
  } catch {
    return { available: false };
  }
}

function main() {
  const node = detectNode();
  const pptxgenjs = detectModule('pptxgenjs');
  const soffice = detectCommand('soffice');
  const libreoffice = detectCommand('libreoffice');

  const render = {
    status: (soffice.available || libreoffice.available) ? 'available' : 'unavailable',
    engine: soffice.available ? 'soffice' : (libreoffice.available ? 'libreoffice' : null),
  };

  const result = {
    node,
    pptxgenjs,
    soffice,
    libreoffice,
    render,
    pipeline_level: computePipelineLevel({ pptxgenjs, render }),
  };

  process.stdout.write(JSON.stringify(result, null, 2) + '\n');
}

main();
