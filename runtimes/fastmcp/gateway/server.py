"""将 MCP 工具聚合到 /mcp，并为服务管理提供 /healthz。"""

import logging
import os
from pathlib import Path
from typing import Dict, Optional

from fastmcp import FastMCP
from starlette.responses import JSONResponse

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# 创建主 MCP 服务器（聚合所有服务）
_main_mcp: Optional[FastMCP] = None

# 服务注册表：name -> FastMCP 实例
_registered_services: Dict[str, FastMCP] = {}


def get_main_mcp() -> FastMCP:
    """获取或创建主 MCP 服务器"""
    global _main_mcp
    if _main_mcp is None:
        _main_mcp = FastMCP("feipi-agent-kit-mcp")
    return _main_mcp


def get_service_mcp(name: str) -> Optional[FastMCP]:
    """获取指定服务的 MCP 实例"""
    return _registered_services.get(name)


def list_services() -> list[str]:
    """获取所有已注册的服务名称"""
    return list(_registered_services.keys())


def register_service(
    name: str,
    service_mcp: FastMCP,
    mount_to_main: bool = True
) -> None:
    """注册 MCP 服务

    Args:
        name: 服务名称
        service_mcp: 服务的 FastMCP 实例
        mount_to_main: 是否挂载到主 MCP 服务器
    """
    try:
        # 挂载到主 MCP 服务器（带 namespace 前缀）
        if mount_to_main:
            main = get_main_mcp()
            main.mount(service_mcp, namespace=name)
            logger.info(f"  -> Mounted to main with namespace '{name}'")

        _registered_services[name] = service_mcp
        logger.info(f"Registered service: {name}")

    except Exception as e:
        logger.error(f"Failed to register service {name}: {e}")
        raise


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
        if service_dir.name.startswith("."):
            continue
        if service_dir.name in ["gateway", "shared", "templates", "scripts", "logs"]:
            continue

        # 检查是否有 server.py
        server_py = service_dir / "src" / "server.py"
        if not server_py.exists():
            continue

        service_name = service_dir.name
        module_path = f"runtimes.fastmcp.{service_name}.src.server"
        services.append((service_name, module_path))
        logger.debug(f"Discovered service: {service_name}")

    return services


def load_service(service_name: str, module_path: str) -> Optional[FastMCP]:
    """加载单个服务

    Args:
        service_name: 服务名称
        module_path: 模块路径

    Returns:
        加载的 FastMCP 实例，失败返回 None
    """
    try:
        module = __import__(module_path, fromlist=[""])
        service_mcp = getattr(module, "mcp", None)
        if service_mcp:
            register_service(service_name, service_mcp)
            return service_mcp
        else:
            logger.warning(f"Service {service_name} has no 'mcp' instance")
            return None
    except ImportError as e:
        logger.error(f"Failed to import service {service_name} from {module_path}: {e}")
        return None
    except Exception as e:
        logger.error(f"Failed to load service {service_name}: {e}")
        return None


async def run_server(host: str = "127.0.0.1", port: int = 18080) -> None:
    """启动 MCP 服务器

    使用 FastMCP 内置的 HTTP 服务器，支持 streamable-http 传输
    """
    mcp = get_main_mcp()

    @mcp.custom_route("/healthz", methods=["GET"])
    async def health(_request):
        return JSONResponse({"services": list_services()}, status_code=200 if _registered_services else 503)

    logger.info(f"Starting MCP server '{mcp.name}' on http://{host}:{port}")
    logger.info(f"Transport: streamable-http")
    logger.info(f"Endpoint: /mcp")
    logger.info(f"Registered services: {', '.join(_registered_services.keys())}")
    logger.info("")
    logger.info("Tool naming convention:")
    logger.info("  {service}_{tool_name}")
    logger.info("  e.g., searxng_search_web")

    await mcp.run_http_async(host=host, port=port, transport="streamable-http")


def main():
    """主入口"""
    logger.info("Starting Feipi Agent Kit MCP Gateway...")
    logger.info("")

    # 自动发现并加载服务
    services_discovered = discover_services()
    logger.info(f"Discovered {len(services_discovered)} services")

    for service_name, module_path in services_discovered:
        load_service(service_name, module_path)

    logger.info("")

    # 启动服务器
    port = int(os.getenv("MCP_PORT", "18080"))
    host = os.getenv("MCP_HOST", "127.0.0.1")

    import asyncio
    asyncio.run(run_server(host=host, port=port))


if __name__ == "__main__":
    main()
