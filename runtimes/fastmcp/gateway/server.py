"""FastMCP Gateway - 统一 MCP 服务入口

将所有 MCP 服务聚合到一个统一的 FastMCP 服务器中
"""

import logging
import os
import sys
from pathlib import Path

from fastmcp import FastMCP

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 创建统一的 MCP 服务器
mcp = FastMCP("agent-skills-mcp")


def register_service(name: str, service_mcp: FastMCP) -> None:
    """注册 MCP 服务

    Args:
        name: 服务名称
        service_mcp: 服务的 FastMCP 实例
    """
    try:
        # 使用 mount 方法将服务挂载到主 MCP 服务器
        # namespace 参数会给所有工具名称添加前缀
        mcp.mount(service_mcp, namespace=name)
        logger.info(f"Mounted service: {name}")

    except Exception as e:
        logger.error(f"Failed to register service {name}: {e}")


def discover_services() -> list[tuple[str, str]]:
    """自动发现 MCP 服务

    扫描 runtimes/fastmcp/*/ 目录下的 MCP 服务
    返回：[(service_name, module_path), ...]
    """
    services = []
    fastmcp_dir = Path(__file__).parent.parent

    for service_dir in fastmcp_dir.iterdir():
        # 跳过非服务目录
        if not service_dir.is_dir():
            continue
        if service_dir.name.startswith(".") or service_dir.name in ["gateway", "shared", "templates"]:
            continue

        # 检查是否有 server.py
        server_py = service_dir / "src" / "server.py"
        if not server_py.exists():
            continue

        service_name = service_dir.name
        module_path = f"runtimes.fastmcp.{service_name}.src.server"
        services.append((service_name, module_path))

    return services


def main():
    """主入口"""
    logger.info("Starting Agent Skills MCP Gateway...")

    # 自动发现服务
    services = discover_services()

    # 手动注册特定服务（调试用）
    # services = [
    #     ("searxng", "runtimes.fastmcp.searxng.src.server"),
    # ]

    # 注册所有服务
    for service_name, module_path in services:
        module = __import__(module_path, fromlist=[""])
        service_mcp = getattr(module, "mcp", None)
        if service_mcp:
            register_service(service_name, service_mcp)
        else:
            logger.warning(f"Service {service_name} has no 'mcp' instance, skipping...")

    # 启动服务器
    port = int(os.getenv("MCP_PORT", "18080"))
    logger.info(f"Starting HTTP server on http://0.0.0.0:{port}")
    import asyncio
    asyncio.run(mcp.run_http_async(host="0.0.0.0", port=port, transport="streamable-http"))


if __name__ == "__main__":
    main()
