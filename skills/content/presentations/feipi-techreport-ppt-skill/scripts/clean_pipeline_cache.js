#!/usr/bin/env node
/**
 * clean_pipeline_cache.js — Pipeline 缓存清理。
 *
 * 用法:
 *   node scripts/clean_pipeline_cache.js [--all] [--older-than-days 7] [--stats]
 *
 * 默认: 清理超过 7 天的缓存条目。
 *   --all: 清理所有缓存。
 *   --older-than-days N: 清理超过 N 天的缓存。
 *   --stats: 仅显示缓存统计。
 */
'use strict';

const path = require('path');
const cache = require('../helpers/pipeline/cache');

const args = process.argv.slice(2);
const allFlag = args.includes('--all');
const statsFlag = args.includes('--stats');
const olderDaysMatch = args.findIndex(a => a === '--older-than-days');
const olderThanDays = olderDaysMatch >= 0 ? parseInt(args[olderDaysMatch + 1], 10) : 7;

if (statsFlag) {
  const s = cache.stats();
  console.log(`Cache stats: ${s.total_entries} entries, ${(s.total_size_bytes / 1024).toFixed(1)} KB`);
  console.log(`Cache dir: ${cache.CACHE_DIR}`);
  process.exit(0);
}

if (!allFlag && olderThanDays < 0) {
  console.error('用法: node clean_pipeline_cache.js [--all] [--older-than-days N] [--stats]');
  process.exit(1);
}

const removed = cache.clean({ all: allFlag, olderThanDays: allFlag ? undefined : olderThanDays });
const s = cache.stats();

if (allFlag) {
  console.log(`Cache cleared: ${removed} entries removed.`);
} else {
  console.log(`Cache cleared: ${removed} entries older than ${olderThanDays} days removed.`);
}
console.log(`Remaining: ${s.total_entries} entries, ${(s.total_size_bytes / 1024).toFixed(1)} KB`);
console.log(`Cache dir: ${cache.CACHE_DIR}`);
