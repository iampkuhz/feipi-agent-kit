#!/usr/bin/env bash

# YouTube 重试策略判断函数（仓库级共享）。
# 下载调用方统一 source 此文件，避免重复维护正则。

is_challenge_error() {
  local err_file="$1"
  rg -qi "n challenge solving failed|Remote components challenge solver script|Only images are available|Requested format is not available|Sign in to confirm|confirm you're not a bot" "$err_file"
}

is_retryable_youtube_download_error() {
  local err_file="$1"
  rg -qi "403 Forbidden|HTTP Error 403|HTTP Error 429|Requested format is not available|Only images are available|n challenge solving failed|Remote components challenge solver script|Sign in to confirm|confirm you're not a bot" "$err_file"
}
