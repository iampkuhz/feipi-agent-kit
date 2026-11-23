#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source-path=SCRIPTDIR
# shellcheck source=../../../tools/lib/podman.sh
source "$script_dir/../../../tools/lib/podman.sh"
podman_require_runtime

podman exec -i fastmcp-gateway python - "${1:-Podman documentation}" "${2:-3}" <<'PYTHON'
import asyncio
import json
import sys

from fastmcp import Client


async def search():
    async with Client("http://127.0.0.1:18080/mcp") as client:
        result = await client.call_tool("searxng_search_web", {
            "query": sys.argv[1], "max_results": int(sys.argv[2]),
        })
        data = result.structured_content
        if not isinstance(data, dict) or not data.get("total_returned"):
            raise SystemExit(f"MCP 搜索没有返回结果：{data}")
        print(json.dumps(data, indent=2, ensure_ascii=False))


asyncio.run(search())
PYTHON
