#!/usr/bin/env python3
"""用于本地测试钉钉 webhook 发送脚本的极简 mock 服务。"""

from __future__ import annotations

import argparse
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse


class MockDingTalkHandler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/healthz":
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"ok")
            return

        self.send_response(404)
        self.end_headers()

    def do_POST(self) -> None:  # noqa: N802
        parsed = urlparse(self.path)
        if parsed.path != "/robot/send":
            self.send_response(404)
            self.end_headers()
            return

        content_length = int(self.headers.get("Content-Length", "0"))
        body = self.rfile.read(content_length).decode("utf-8")
        payload = json.loads(body)

        record = {
            "path": self.path,
            "query": parse_qs(parsed.query),
            "payload": payload,
        }
        Path(self.server.record_file).write_text(  # type: ignore[attr-defined]
            json.dumps(record, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

        response = {"errcode": 0, "errmsg": "ok"}
        encoded = json.dumps(response).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)

    def log_message(self, format: str, *args: object) -> None:  # noqa: A003
        return


def main() -> int:
    parser = argparse.ArgumentParser(description="启动钉钉 webhook mock 服务")
    parser.add_argument("--port", type=int, required=True, help="监听端口")
    parser.add_argument("--record-file", required=True, help="请求记录输出文件")
    args = parser.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", args.port), MockDingTalkHandler)
    server.record_file = args.record_file  # type: ignore[attr-defined]
    try:
        server.serve_forever()
    finally:
        server.server_close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
