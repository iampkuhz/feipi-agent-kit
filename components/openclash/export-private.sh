#!/bin/sh
# 只导出不可凭下载重建的配置，输出 tar.gz 到 stdout。秘密不打印到终端。
set -eu
umask 077
cd /
set -- etc/config/openclash etc/openclash/custom etc/openclash/overwrite
for file in /etc/openclash/config/*.yaml /etc/openclash/config/*.yml; do
  [ -f "$file" ] || continue
  set -- "$@" "${file#/}"
done
tar -czf - "$@"
