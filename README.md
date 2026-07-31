# AgentCLI Patchs

多 Agent CLI 补丁管理工具：交互式蓝色 CLI + 可扩展补丁。当前内置：

| Patch | 作用 |
|-------|------|
| `win10-warning` | 抑制 Qoder CLI 的 Windows 10 启动警告 |
| `cursor-agent` | Cursor Agent `auth.json` 热读 + 安装便携 `sc` / `/sc` 换号 |

变更历史见 [CHANGELOG.md](CHANGELOG.md)。

---

## 安装

```bash
git clone https://github.com/nichengfuben/AgentCLI-Patchs.git
cd AgentCLI-Patchs
pip install -e ".[dev]"
```

入口：

```bash
python main.py          # 交互菜单
agentcli-patchs         # 同上（pip 后）
acp / qp                # 短命令
sc /sc help             # 便携换号 CLI（需先 apply cursor-agent 或 PYTHONPATH=src）
```

源码布局（`pythonpath=src`）：

```
src/
  cli/       # Typer 交互与主题
  core/      # 引擎 / 注册表 / PatchBase
  patches/   # win10-warning、cursor-agent
  sc/        # /sc 便携换号（config 与 auth 同级）
  utils/     # 路径 / 备份 / 平台
```

---

## 补丁用法

```bash
# 预览
python main.py apply --all --dry-run

# 应用全部 / 单个
python main.py apply --all
python main.py apply win10-warning
python main.py apply cursor-agent

# 状态 / 回滚
python main.py status
python main.py rollback cursor-agent
```

### `cursor-agent` 做了什么

逆向 `%LOCALAPPDATA%\cursor-agent\versions\<ver>\`：

- **Auth 热读**（`index.js` AuthStorage）：去掉 `cachedAccessToken` 短路，每次 `readAuthData()` 读盘；外部改写 `%APPDATA%\Cursor\auth.json` **无需再为换号重启** agent
- **Agent 内置 `/sc` slash**（webpack chunk，如 `5305.index.js`）：在 `/mcp` 后注册 builtin `/sc`；仅装 `sc.cmd` **不会**让交互框里的 `/sc` 生效（会落到技能模糊匹配）
- **便携启动器**：安装根写入 `sc.cmd` / `sc.ps1`（`PYTHONPATH` 指向本仓库 `src`）

应用补丁后需**重启一次** `cursor-agent` / `ag`，slash 表才会重新加载。

### `/sc` 便携换号

`config.json` **不**放在执行目录，与 cursor-agent 的 `auth.json` 同级：

- Windows: `%APPDATA%\Cursor\config.json` + `auth.json`
- macOS: `~/.cursor/config.json` + `auth.json`
- Linux: `$XDG_CONFIG_HOME/cursor/`（或 `~/.config/cursor/`）

在 **Agent 输入框**（与 `/mcp` 同级）：

```text
/sc help
/sc pull
/sc usage
/sc status
/sc auto
```

或在 shell：

```bash
sc addkey sc_xxxxxxxx          # 写入同级 config.json
sc pull                        # 拉号 → 写 auth.json（热生效）
sc usage / sc token / sc status
sc auto                        # 后台轮询，超限自动换号
sc auto stop
```

### Statusline（完整 sc 状态栏）

apply `cursor-agent` 后会：

1. 安装 `%LOCALAPPDATA%\cursor-agent\sc-statusline.cmd`
2. 写入/合并 `~/.cursor/cli-config.json` 的 `statusLine`，指向上述命令
3. 运行时把完整状态写入 `%APPDATA%\Cursor\sc_status.json`（与 auth 同级）

Agent 提示符上方会显示约 3 行：

- auto 开/关、当前动作（polling/pulling/switching）、轮询序号、阈值
- 账号 email / card / uid、用量 total/auto/api
- 正在做什么的 message、上次更新时间、错误

`/sc status` 会刷新并打印同样信息。`sc auto` 日志另写 `sc_auto.log`。

**重启一次 `ag`** 后 statusLine 生效。若你已有自定义 statusLine，apply 会覆盖 `statusLine` 字段（其它 cli-config 项保留）。
---

## 配置（补丁管理器本身）

查找顺序：`--config` → `AGENTCLI_PATCHS_CONFIG` → 项目根 `config.toml` → 用户目录 → 默认。

Qoder bundle 还可用 `AGENTCLI_PATCHS_BUNDLE` 或 `config.toml` 的 `paths.bundle_dir`。

---

## 开发

```bash
pytest
pytest --cov=cli --cov=core --cov=patches --cov=sc --cov=utils
python achecker.py
```

新补丁：在 `src/patches/` 实现 `PatchBase` 子类；可在 `pyproject.toml` `[project.entry-points."patches"]` 注册。参考 `docs-src/patches/guide.md`。

---

## License

MIT
