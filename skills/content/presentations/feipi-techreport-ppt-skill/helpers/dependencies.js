'use strict';

// npm 依赖从锁定缓存解析，不改全局 Node 模块路径。
const fs = require('fs');
const path = require('path');
const { createRequire } = require('module');
const { execFileSync } = require('child_process');
let loader;
let runtimePath;

function resolveRuntime(check = false) {
  if (!loader) {
    const args = [path.join(__dirname, '../scripts/prepare_runtime.py')];
    if (check) args.push('--check');
    const info = JSON.parse(execFileSync('python3', args, {
      encoding: 'utf8', timeout: 195000,
      stdio: ['ignore', 'pipe', check ? 'pipe' : 'inherit'],
    }));
    runtimePath = info.path;
    loader = createRequire(path.join(runtimePath, 'package.json'));
  }
  return loader;
}

function dependency(name) {
  return resolveRuntime()(name);
}

dependency.info = name => {
  try {
    resolveRuntime(true);
    const pkg = JSON.parse(fs.readFileSync(path.join(runtimePath, 'node_modules', name, 'package.json'), 'utf8'));
    return { available: true, version: pkg.version, location: 'shared-lockfile-cache' };
  } catch {
    return { available: false, install_hint: 'python3 scripts/prepare_runtime.py' };
  }
};

module.exports = dependency;
