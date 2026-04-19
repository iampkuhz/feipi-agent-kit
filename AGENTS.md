# 仓库级大模型上下文（Agent Tools）

> **版本**：v2.0（agent-tools 重构后）
> **定位**：指导 AI 在本仓库中高效协作

---

## 角色与任务

1. **你的角色**：本仓库的 agent-tools 工程助手
2. **主要职责**：创建、更新、重构和验证 skills、tools、rules、commands
3. **工作方式**：默认进入"先规则后实现"的工作流

---

## 强约束（必须遵守）

1. **中文优先**：所有面向用户的可见输出默认使用简体中文
   - 包括计划、分析、拆解、审阅、总结、步骤说明、修改说明
   - 若产生可见 reasoning / planning summary 等过程文本，也必须用简体中文表达
   - 代码、shell 命令、文件路径、JSON/YAML key、API/class/function/library/protocol 名称保持英文原样
   - 外部系统返回的英文中间结果应先给出中文解释或归纳，仅在必要时保留原文片段作为引用
   - 详见 `rules/global/language.md`
2. **规则先行**：处理 skill/tool 相关任务时，先遵循 `rules/` 和 `feipi-skill-govern`
3. **职责分离**：
   - `skills/` - Agent 能力扩展
   - `tools/` - 外部服务封装
   - `rules/` - 行为约束规范
   - `commands/` - 显式命令
   - `runtimes/` - 运行时框架

---

## 目录职责与使用场景

### skills/

**职责**：Agent 技能，扩展 AI 的特定领域能力

**触发方式**：隐式（用户描述任务）或显式（@skill）

**示例**：
- `feipi-plantuml-generate-architecture-diagram` - 生成架构图
- `feipi-patent-generate-innovation-disclosure` - 撰写专利交底书

**工作流**：
```
用户："帮我画一个系统架构图"
    │
    ▼
AI 隐式调用 skills/diagram/ 中的技能
    │
    ▼
遵循 rules/diagram/ 中的规范
    │
    ▼
产出 PlantUML 代码和渲染图
```

### tools/

**职责**：外部服务封装，通过 MCP 或直接 HTTP 调用

**触发方式**：MCP 工具调用或内部脚本

**示例**：
- `tools/search/searxng-mcp/` - SearXNG 搜索服务
- `tools/gateway/litellm/` - LiteLLM 模型网关

**使用方式**：
```
用户在 Claude Code 中："搜索一下 Python 异步编程"
    │
    ▼
Claude Code 调用配置的 MCP server (searxng-mcp)
    │
    ▼
返回标准化搜索结果
```

### rules/

**职责**：行为规则和约束规范，自动应用

**触发方式**：自动（无需显式调用）

**示例**：
- `rules/global/language.md` - 语言使用规范
- `rules/coding/python.md` - Python 编码规范

**优先级**：rules > 通用最佳实践

### commands/

**职责**：Slash Commands，显式命令

**触发方式**：`/command`

**示例**：
- `/help` - 帮助信息
- `/status` - 项目状态

**与 skills 的区别**：
| 维度 | commands | skills |
|------|----------|--------|
| 触发 | 显式 `/` | 隐式/@ |
| 职责 | 仓库级命令 | 领域能力 |
| 示例 | `/help` | @plantuml |

### runtimes/

**职责**：运行时框架，提供服务化支撑

**示例**：
- `runtimes/fastmcp/` - FastMCP 模板和共享库

**与 tools 的关系**：
- `runtimes/` 提供通用框架
- `tools/*-mcp/` 使用框架实现具体服务

---

## 规则优先级

```
系统/开发者指令（最高）
    │
    ▼
AGENTS.md（本文件）
    │
    ▼
rules/ 中的具体规范
    │
    ▼
skills/ 中的专属规则
    │
    ▼
通用最佳实践（最低）
```

---

## 工作流程

### 创建新 Skill

1. **查阅规则**：`rules/` 中是否有相关规范
2. **使用治理工具**：`feipi-skill-govern` 工作流
3. **创建文件**：按 `skills/` 目录约定组织
4. **编写测试**：确保可验证
5. **更新文档**：同步更新 README 和 `.env.example`

### 创建新 MCP 服务

1. **使用模板**：`runtimes/fastmcp/templates/python/`
2. **实现 server**：定义工具函数
3. **实现 client**：封装外部 API
4. **定义 schema**：输入/输出模型
5. **编写测试**：确保可验证
6. **更新配置**：在 Claude Code 中注册 MCP server

### 修改服务配置

1. **定位服务**：确认修改 `tools/` 中哪个服务
2. **修改配置**：编辑 compose/、env/ 或 settings/
3. **重启服务**：使用 `make <service>-restart`
4. **验证变更**：运行健康检查或测试

---

## 完成定义（DoD）

交付结果必须满足：

1. **可追溯**：改动与用户目标直接对应
2. **可验证**：必要验证已执行并反馈结果
3. **文档同步**：代码和文档同步更新
4. **规范一致**：遵循 `rules/` 和 `AGENTS.md`

---

## 变更同步要求

### 修改规范类文件

修改 `AGENTS.md`、`rules/`、`skills/authoring/feipi-skill-govern/` 后：
- 检查是否影响现有技能/工具
- 更新受影响的文档

### 新增环境变量

- 同步更新 `.env.example`（仓库根目录）
- 同步更新对应 `SKILL.md` 或 `README.md`
- 不在 skill/tool 目录下分散维护 `.env.example`

### 修改测试入口

- 同步检查对应技能/工具的 `scripts/test.sh`
- 同步检查仓库级包装命令

---

## 常用命令

### Skills 管理

```bash
# 安装 skills（软链接）
make install-links

# 安装到项目目录
make install-project PROJECT=/path/to/project

# 初始化新 skill
bash skills/authoring/feipi-skill-govern/scripts/init_skill.sh <name> --layer <layer>

# 校验 skill
bash skills/authoring/feipi-skill-govern/scripts/validate.sh <skill-path>

# 执行技能测试
bash <skill-path>/scripts/test.sh
```

### 服务管理

```bash
# LiteLLM
make litellm-up
make litellm-down
make litellm-restart

# SearXNG
make searxng-up
make searxng-down
make searxng-restart

# SearXNG MCP
make searxng-mcp-run
```

### 仓库维护

```bash
# 初始化设置
./scripts/bootstrap/setup.sh

# 健康检查
./scripts/doctor/check.sh
```

---

## 服务接入指南

### Claude Code 使用 SearXNG MCP

1. **确保服务运行**：
   ```bash
   make searxng-up
   make searxng-mcp-run
   ```

2. **配置 MCP Server**：
   在 `~/.claude/settings.local.json` 添加：
   ```json
   {
     "mcpServers": {
       "searxng": {
         "command": "uv",
         "args": ["run", "python", "src/server.py"],
         "cwd": "/Users/zhehan/Documents/tools/llm/skills/agent-skills/tools/search/searxng-mcp",
         "env": {
           "SEARXNG_BASE_URL": "http://localhost:8873"
         }
       }
     }
   }
   ```

3. **使用工具**：
   ```
   使用 search_web 搜索 "Python async best practices"
   ```

### 使用 LiteLLM 作为模型网关

1. **启动服务**：
   ```bash
   make litellm-up
   ```

2. **客户端配置**：
   ```python
   from openai import OpenAI

   client = OpenAI(
       base_url="http://127.0.0.1:4000/v1",
       api_key="your-LITELLM_MASTER_KEY"
   )
   ```

---

## 故障排查

### 服务无法启动

1. **检查端口占用**：`lsof -i :<port>`
2. **查看日志**：`docker compose logs`
3. **验证配置**：检查 env/ 和 compose/ 文件

### MCP 服务不可用

1. **检查基础服务**：`curl http://localhost:8873/healthz`
2. **检查 MCP 进程**：确认服务正在运行
3. **检查 Claude Code 配置**：验证 settings.json 中的 MCP 配置

### Skill 无法使用

1. **检查安装**：`ls ~/.claude/skills/`
2. **检查权限**：确保软链接正确
3. **重新安装**：`make install-links`

---

## 参考

- [README.md](README.md) - 仓库总览
- [rules/](rules/) - 行为规则
- [commands/](commands/) - Slash Commands
- [skills/](skills/) - Agent Skills
- [tools/](tools/) - External Tools
- [runtimes/fastmcp/](runtimes/fastmcp/) - FastMCP Runtime
