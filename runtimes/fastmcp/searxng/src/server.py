"""SearXNG MCP Server - 网络搜索工具

使用方式：
    统一启动：python -m runtimes.fastmcp.gateway.server
    独立调试：python -m runtimes.fastmcp.searxng.src.server
"""

import os
from runtimes.fastmcp import create_mcp
from .searxng_client import SearXNGClient
from .schemas import SearchWebOutput

mcp = create_mcp("searxng")


def get_client() -> SearXNGClient:
    """获取 SearXNG 客户端"""
    return SearXNGClient(os.getenv("SEARXNG_URL", "http://localhost:8873"))


@mcp.tool()
async def search_web(
    query: str, category: str = "general", max_results: int = 8,
    language: str | None = None, time_range: str | None = None,
) -> dict:
    """使用 SearXNG 元搜索引擎进行网络搜索

    Args:
        query: 搜索查询（必填）
        category: 搜索分类（默认：general）
        max_results: 最大结果数 1-20（默认：8）
        language: 语言代码（可选）
        time_range: 时间范围（可选）

    Returns:
        搜索结果：{query, results: [{title, url, snippet, engine}], total_returned}
    """
    max_results = max(1, min(20, max_results))
    client = get_client()

    try:
        results = await client.search(query, category, max_results, language, time_range)
        return SearchWebOutput(query=query, results=results, total_returned=len(results)).model_dump()
    except Exception as e:
        return {"query": query, "results": [], "total_returned": 0, "error": str(e)}
