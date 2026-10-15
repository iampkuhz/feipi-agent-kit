#!/usr/bin/env python3
"""仅供本地 Podman 使用的 draw.io 渲染服务。"""
import base64
import json
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import sync_playwright

ROOT = Path('/app')
ORIGIN = 'http://127.0.0.1:8081'
LIMIT = 2 * 1024 * 1024
RENDER = (ROOT / 'render.js').read_text()


class Assets(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / 'webapp'), **kwargs)

    def log_message(self, *args):
        pass


class Handler(SimpleHTTPRequestHandler):
    def reply(self, code, data):
        content = json.dumps(data, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Content-Length', str(len(content)))
        self.end_headers()
        self.wfile.write(content)

    def do_GET(self):
        if self.path != '/health':
            return self.reply(404, {'error': '未知路径'})
        self.reply(200, {'status': 'ready', 'service': 'feipi-drawio',
                         'contract': 1, 'drawio': '29.7.12',
                         'network': 'local-only', 'browser': browser.version})

    def do_POST(self):
        if self.path != '/render':
            return self.reply(404, {'error': '未知路径'})
        context = None
        try:
            length = int(self.headers.get('Content-Length', '0'))
            if not 0 < length <= LIMIT:
                return self.reply(413, {'error': '请求必须为 1 字节到 2 MiB'})
            self.connection.settimeout(35)
            data = json.loads(self.rfile.read(length))
            xml = data['xml']
            if not isinstance(xml, str) or '<mxGraphModel' not in xml:
                raise ValueError('需要 mxGraphModel XML')
            context = browser.new_context(viewport={'width': 1600, 'height': 1200},
                                          device_scale_factor=1, service_workers='block')
            blocked = []

            def local_only(route):
                url = route.request.url
                parsed = urlsplit(url)
                if (parsed.scheme, parsed.netloc) == ('http', '127.0.0.1:8081'):
                    route.continue_()
                elif parsed.scheme in ('data', 'blob'):
                    route.continue_()
                else:
                    blocked.append(url)
                    route.abort()

            context.route('**/*', local_only)
            page = context.new_page()
            page.set_default_timeout(25000)
            page.goto(ORIGIN + '/export3.html?offline=1&svg-warning=0', wait_until='load')
            page.wait_for_function("typeof Graph === 'function' && typeof mxCodec === 'function'")
            result = page.evaluate(RENDER, xml)
            if blocked:
                raise ValueError('图包含被阻止的外部资源')
            page.set_content(result['svg'])
            await_fonts = 'document.fonts.ready.then(() => true)'
            page.evaluate(await_fonts)
            svg = page.locator('svg').first
            box = svg.bounding_box()
            if not box or min(box['width'], box['height']) < 1 or max(box['width'], box['height']) > 6000:
                raise ValueError('渲染尺寸必须在 1–6000 像素之间')
            result['png'] = base64.b64encode(svg.screenshot(timeout=25000)).decode()
            if blocked:
                raise ValueError('SVG 包含被阻止的外部资源')
            result['renderer'] = {'service': 'feipi-drawio', 'contract': 1,
                                  'drawio': '29.7.12', 'network': 'local-only'}
            self.reply(200, result)
        except Exception as exc:
            self.reply(422, {'error': str(exc)[:1000]})
        finally:
            if context:
                context.close()


if __name__ == '__main__':
    # 静态资源服务仅容器内可见，外部只暴露两个 JSON 端点。
    import threading
    threading.Thread(target=HTTPServer(('127.0.0.1', 8081), Assets).serve_forever,
                     daemon=True).start()
    with sync_playwright() as engine:
        browser = engine.chromium.launch(executable_path='/usr/bin/chromium',
                                         args=['--no-sandbox', '--disable-dev-shm-usage'])
        HTTPServer(('0.0.0.0', 8080), Handler).serve_forever()
