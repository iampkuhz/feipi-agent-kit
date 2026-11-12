# feipi-skill-govern 源码维护

本目录只供维护治理 Skill 源码时读取，不安装到客户端。执行治理任务所需的规范仍在 `references/`。

先读 [术语与命名](terminology.md)，再根据改动读取以下真源：

| 内容 | 维护位置 |
|---|---|
| 治理触发、范围与执行顺序 | `../SKILL.md`、`../agents/openai.yaml`、`../references/` |
| 新建 Skill 与维护资料模板 | `../scripts/init_skill*.sh`、`../templates/` |
| 结构、维护资料与运行依赖校验 | `../scripts/validate.sh`、`../scripts/validate_resources.py` |
| 路径与双平台静态检查 | `../scripts/check_portability.py` |
| 确定性回归与行为用例 | `../tests/run.sh`、`../evals/cases.json` |
| 安装与打包 | 仓库 `scripts/install_skills.sh`、`scripts/package_skill.py` |
| 全登记集合验收 | 仓库 `scripts/harness/validate_skill_layout.py` |

## 修改与验收

治理 Skill 可读取目标源码的维护资料；安装后的自身运行资源仍不能依赖本目录。校验器只允许明确的目标源码路径，不能按 Skill 名整体豁免维护依赖。

新建 Skill 自动生成维护入口与术语表；本次治理的目标缺少资料时补齐。历史 Skill 不在这次批量迁移，仓库布局检查允许它们暂缺维护目录；单个治理交付用严格参数检查。

在本 Skill 根目录运行：

```bash
bash scripts/validate.sh . --require-maintenance
bash tests/run.sh
```

修改安装器时还要在仓库根运行：

```bash
python3 scripts/harness/validate_skill_layout.py
python3 -m unittest discover -s tests -p 'test_install_output.py'
python3 -m unittest discover -s tests/workbench
```

链接模式只链接没有被排除子目录的运行目录；需要过滤的目录展开成真实目录，再链接干净的子目录，避免嵌套维护资料透传。拷贝模式递归过滤同一集合，比较安装内容时使用相同规则。维护资料变化不应触发无意义的重复安装。

指向维护资料的别名链接同样排除；指向含开发资料目录的链接先展开过滤。循环目录链接会使安装失败，保留原安装。

版本按 `../references/version-changelog-policy.md` 更新。临时审计、验证输出和安装证据写到仓库 `tmp/`，不写回本目录。静态检查不等于在 macOS、Linux 分别实测。
