#!/usr/bin/env python3
"""兼容入口：Agent 配置已统一由 multica-ops 管理，避免两套写入逻辑。"""
import sys
print('请使用 multica-ops plan，然后 multica-ops apply --plan-id <摘要>；旧同步入口已停用。', file=sys.stderr)
sys.exit(2)
