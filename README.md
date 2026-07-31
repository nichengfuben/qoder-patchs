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

逆向 `%LOCALAPPDATA%\cursor-agent\versions\<ver>\index.js` 中 AuthStorage：

- 原逻辑：`getAccessToken` 等优先返回内存 `cachedAccessToken`
- 补丁后：每次 `readAuthData()` 读盘，外部改写 `%APPDATA%\Cursor\auth.json` **无需重启** cursor-agent
- 同时在安装根写入 `sc.cmd` / `sc.ps1`

### `/sc` 便携换号

`config.json` **不**放在执行目录，与 cursor-agent 的 `auth.json` 同级：

- Windows: `%APPDATA%\Cursor\config.json` + `auth.json`
- macOS: `~/.cursor/config.json` + `auth.json`
- Linux: `$XDG_CONFIG_HOME/cursor/`（或 `~/.config/cursor/`）

```bash
sc addkey sc_xxxxxxxx          # 写入同级 config.json
sc pull                        # 拉号 → 写 auth.json（热生效）
sc usage / sc token / sc status
sc auto                        # 后台轮询，超限自动换号
sc auto stop
# 等价：/sc pull  /sc auto
```

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
