#!/usr/bin/env bash
set -euo pipefail

# 手工启动本地 PlantUML 服务；新机初始化入口不会调用本脚本。
podman run --rm -d -p 8199:8080 --name plantuml docker.io/plantuml/plantuml-server:jetty
