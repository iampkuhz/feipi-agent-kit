#!/usr/bin/env python3
"""用于本地测试 check_render.sh 的极简 PlantUML mock 服务。"""

from __future__ import annotations

import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer


SVG_BODY = """<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 120 40">
  <text x="8" y="24">mock plantuml</text>
</svg>
"""


class MockPlantUMLHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return

        if self.path.startswith("/plantuml/txt/"):
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"Mock render success")
            return

        if self.path.startswith("/plantuml/svg/"):
            body = SVG_BODY.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "image/svg+xml; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return

        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="启动 PlantUML mock 服务")
    parser.add_argument("--port", type=int, required=True, help="监听端口")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), MockPlantUMLHandler)
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
