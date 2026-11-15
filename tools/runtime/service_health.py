"""本地服务首次初始化的有界就绪等待，不停止或重建容器。"""
import time
import urllib.request


def wait_service(component, endpoint):
    """首次迁移/浏览器准备可能较慢；有界等待健康检查，不反复重建。"""
    deadline = time.monotonic()+600
    attempt = 0
    while time.monotonic() < deadline:
        try:
            with urllib.request.build_opener(urllib.request.ProxyHandler({})).open(endpoint, timeout=3) as response:
                if response.status == 200:
                    print(component+' readiness 已通过；业务能力需真实请求验证。')
                    break
        except OSError:
            pass
        if attempt % 10 == 0:
            print('等待 '+component+' 首次初始化及服务就绪…', flush=True)
        time.sleep(2)
        attempt += 1
    else:
        raise ValueError(component+' 未在 10 分钟内就绪；保留运行状态供 service '+component+' logs 检查，不重复重建数据库。')
