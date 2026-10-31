# OpenClash 地区优先

这里只公开无凭据的覆写模块、原生合并校验和操作脚本。日常入口位于仓库根目录：

```bash
./workbench diff openclash
./workbench capture openclash --select OIX-Region-Priority.conf
./workbench apply openclash
./workbench service openclash verify
./workbench private backup openclash
./workbench private verify openclash <私有批次>
```

当前声明：Proxy → 地区优先 fallback，按香港、日本、新加坡、美国、全球排序；各地区内部 URLTest 自动选择。Domestic、CN Mainland TV、Speedtest 保持 DIRECT。测试只验证当前路径，不主动断开节点模拟地区全部故障。

本机 `~/.config/feipi-workbench/router.json` 权限 0600，字段为 `ssh`（SSH 别名或 root@地址）、`controller`（HTTP API 地址）、`secret`（已有控制密钥）、`proxy`（mixed/http 代理地址）、`proxy_auth`（已有 username:password，如启用）、`config`（路由器原订阅路径）。从现有路由器私有配置取得，不能把真实内容放进本仓库。SSH 使用已配置密钥和主机密钥检查。实际代理启用了认证，仅 API 可访问不足以证明代理联网。

锁定运行版本记录在 `versions.json`。路由器用已有 LuCI/OpenClash 安装与升级能力，不从本仓库下载未知内核。apply 先获取当前模块，保存最小私有配置和路由器原模块/UCI，再调用当前 `/usr/share/openclash/YAML.rb` 合并和 `clash_meta -t`。实际内容相同时登记接管；变化时重启并恢复原 Selector 选择。未提交 UCI 改动会阻止应用。

## 最小导出

`export-private.sh` 只导出 `/etc/config/openclash`、`/etc/openclash/custom`、`/etc/openclash/overwrite`、`/etc/openclash/config/*.yaml|*.yml`；另存 Selector 选择、版本与校验清单。排除核心、GeoIP、运行生成 YAML、provider 下载缓存、历史和日志。

2026-10-31 实测：原完整 LuCI 备份 **37,869,578 bytes**，最小配置压缩包 **22,748 bytes**（约减少 99.94%）。大小会随订阅增长；两种备份都含秘密，无论大小都不进公开 Git。旧完整备份已保留作本次回退，不反复下载或提交它。

## 恢复

同机只回退模块：使用 apply 输出的 `/root/feipi-workbench-backup-<时间>/module.conf` 恢复到 overwrite 目录，然后 `/etc/init.d/openclash restart`，核对原选择及 `service openclash verify`。UCI 若本次未改不必恢复整份。

重建路由器：先安装同版 OpenClash 和匹配核心/Geo 数据；校验最小包，解压到私有暂存目录检查路径；通过 SSH 将对应 UCI、custom、overwrite、订阅配置放回原位置，权限保持仅管理员可读；重启并按 selections.json 恢复选择。下载型 provider 和缓存重新获取。核心启动后先 doctor，再进行真实国内/国外联网验证。首次恢复仍需当前订阅有效；备份文件存在不保证订阅或节点可用。

无需开发专门迁移平台，也不把插件内核或缓存提交 Git。
