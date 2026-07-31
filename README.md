# Patcher

多 Agent CLI 补丁管理工具（原 AgentCLI-Patchs）：交互式蓝色 CLI + 可扩展补丁。当前内置：

| Patch | 作用 |
|-------|------|
| `remove-qoder-warning` | 抑制 Qoder CLI 的 Windows 10 启动警告 |
| `cursor-agent` | Cursor Agent `auth.json` 热读 + 启动自动 `sc auto` + statusline |

变更历史见 [CHANGELOG.md](CHANGELOG.md)。

---

## 安装

```bash
git clone https://github.com/nichengfuben/Patcher.git
cd Patcher
pip install -e ".[dev]"
```

入口：

```bash
python main.py          # 交互菜单
patcher                 # 同上（pip 后）
agentcli-patchs / acp / qp   # 兼容旧命令
sc                      # 便携换号 CLI
```

源码布局（`pythonpath=src`）：

```
src/
  cli/       # Typer 交互与主题
  core/      # 引擎 / 注册表 / PatchBase
  patches/   # remove-qoder-warning、cursor-agent
  sc/        # 便携换号（core/ + run/）
  utils/     # 路径 / 备份 / 平台
```

---

## 补丁用法

```bash
# 预览
python main.py apply --all --dry-run

# 应用全部 / 单个
python main.py apply --all
python main.py apply remove-qoder-warning
python main.py apply cursor-agent

# 状态 / 回滚
python main.py status
python main.py rollback cursor-agent
```

### `cursor-agent` 做了什么

逆向 `%LOCALAPPDATA%\cursor-agent\`：

- **Auth 热读**（`index.js`）：
  - AuthStorage / keychain：去掉缓存短路，每次读盘
  - 禁用 ephemeral 与 apiKeyOverride
  - 每次设 `Authorization` 前强制覆盖 Bearer
  - 请求时写 `%APPDATA%\Cursor\agentcli-last-bearer.json` 便于对照
  - 禁用 `cursor-agent.ps1` 的 `NODE_COMPILE_CACHE`
- **statusLine**：leader auto 写 `sc_instances.json`；任意实例只读刷新用量/`#`
- **配置**：只读 `~/.cursor/config.json`（不硬编码）。可选 `PATCHER_SC_CONFIG_SRC` / `AGENTCLI_SC_CONFIG_SRC` 播种

应用后**必须完全退出并重启** `ag`。换号后对照：
`sc status` 的 `token … sub=` ≡ `agentcli-last-bearer.json` 的 `sub`。

### 配置与状态

`auth.json`：Windows `%APPDATA%\Cursor\`；macOS/Linux 见平台 auth 目录  
`config.json` / `sc_status.json` / `sc_auto.*` / 实例心跳：`%USERPROFILE%\.cursor\`（即 `~/.cursor`）

```bash
sc status          # 配置 / 在线实例 / 用量 / leader
sc doctor          # 自检 hot-auth 补丁与 Bearer sub 对照
sc auto stop       # 停止全部实例
sc pull            # 手动拉号（一般不需要）
```

### Statusline

apply 后写入 `~/.cursor/cli-config.json` 的 `statusLine`。一行紧凑状态：

- 常态：`SC A OK [████…░░░░] 38.0% a12.0% p55.0% user@x/pro #12`
- 刷新：`SC A ↻#12 OK …`
- 换号：`SC SWITCH thr>=95% → …`

**重启一次 `ag`** 后 statusLine 与 auto-boot 生效。

---

## 配置（补丁管理器本身）

查找顺序：`--config` → `PATCHER_CONFIG`（兼容 `AGENTCLI_PATCHS_CONFIG`）→ 项目根 `config.toml` → 用户目录 → 默认。

Qoder bundle：`PATCHER_BUNDLE`（兼容 `AGENTCLI_PATCHS_BUNDLE`）或 `config.toml` 的 `paths.bundle_dir`。

---

## 开发

```bash
pytest
python achecker.py
```

新补丁：在 `src/patches/` 实现 `PatchBase` 子类；可在 `pyproject.toml` `[project.entry-points."patches"]` 注册。

CI：push/PR 到 `main` 跑 pytest；打 `v*` tag 发 GitHub Release。

---

## License

MIT
