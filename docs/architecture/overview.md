# Feipi Agent Kit 架构说明

仓库集中维护 Mac 配置、Agent 技能和本地服务定义。日常操作用 `./workbench`，修改源码后直接运行组件测试。

## 目录职责

| 目录 | 放什么 |
| --- | --- |
| `components/` | Mac、Multica、OpenClaw、OpenClash 的安装、配置与组件文档 |
| `skills/` | 客户端加载的技能及其资源，分发范围由 `skills/registry.yaml` 管理 |
| `rules/` | 适用范围、优先级和行为规则 |
| `commands/` | 用户显式触发的 slash command 入口 |
| `tools/` | 服务及工具封装，例如 LiteLLM、Crawl4AI、SearXNG、OTel |
| `runtimes/` | 可复用的运行时和模板，例如 FastMCP |

服务的 Compose 定义、设置、环境示例和运维脚本随服务存放。例如，SearXNG 的配置和启动方式见 [SearXNG README](../../tools/search/searxng/README.md)。

## 源码与日常环境

配置通过 `./workbench install <组件>` 发布到本机运行位置或路由器。客户端加载已发布的 Skill，托管服务从已发布的定义启动。修改生效后，用实际客户端或服务请求确认效果。 [配置工作流](../workbench.md#安装和检查) · [服务验收指南](../verification/README.md)

版本化内容包含声明、模板和脚本。密钥、登录态、会话及业务数据留在私有位置，按组件的备份和恢复说明处理。操作细节见 [工作台手册](../workbench.md)。

## 客户端怎样调用服务

- **HTTP API** · SearXNG 提供搜索接口，LiteLLM 提供 OpenAI 兼容模型接口。脚本或客户端可直接请求服务。 [SearXNG](../../tools/search/searxng/README.md) · [LiteLLM](../../tools/gateway/litellm/README.md)
- **MCP** · Crawl4AI 自带 MCP 接口，支持 MCP 的客户端可接入后执行抓取。 [Crawl4AI](../../tools/crawl/crawl4ai/README.md)

## 在哪里扩展

| 要新增什么 | 从哪里开始 |
| --- | --- |
| Skill | 按主要对象归类，登记路径索引，提供用例和随附测试。 [Skill 工程治理](../../skills/agent/skills/feipi-skill-govern/SKILL.md) |
| MCP 服务 | 查看 FastMCP 运行时和 Python 模板，将业务封装放在对应服务目录。 [FastMCP](../../runtimes/fastmcp/README.md) · [Python 模板](../../runtimes/fastmcp/templates/python/) |
| 规则 | 按适用范围放入 `rules/`，说明何时适用并补充正反示例。 [规则索引](../../rules/README.md) |

环境依赖和版本以各组件 README、锁文件及部署清单为准。提交服务改动时，说明检查方式、实际请求和通过条件。 [服务验收指南](../verification/README.md) · [仓库协作规则](../../AGENTS.md)
