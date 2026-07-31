# AgentCLI Patchs

多 Agent CLI 补丁管理工具：交互式蓝色 CLI + 可扩展补丁。当前内置：

| Patch | 作用 |
|-------|------|
| `win10-warning` | 抑制 Qoder CLI 的 Windows 10 启动警告 |
| `cursor-agent` | Cursor Agent `auth.json` 热读 + 启动自动 `sc auto` + statusline |

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
```

源码布局（`pythonpath=src`）：

```
src/
  cli/       # Typer 交互与主题
  core/      # 引擎 / 注册表 / PatchBase
  patches/   # win10-warning、cursor-agent
  sc/        # 便携换号（config 与 auth 同级；agent 启动自动 auto）
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

逆向 `%LOCALAPPDATA%\cursor-agent\`：

- **Auth 热读**（`index.js`）：去掉缓存短路，外部改写 `%APPDATA%\Cursor\auth.json` 立即生效
- **启动自动换号**：改写 `cursor-agent.cmd`，进入 `ag` 时后台启动 `sc auto`（**无 /sc slash 命令**）
- **配置**：从 `X:\Project\Common\Common\config.json`（client.py 同目录）复制到 `%APPDATA%\Cursor\config.json`
- **statusline**：提示符上一行显示额度 / 换号状态

应用后**重启一次** `ag`。

### 配置与状态

`config.json` 与 `auth.json` 同级：`%APPDATA%\Cursor\`

```bash
sc status          # 查看配置/用量/auto 进程
sc auto stop       # 停止后台换号
sc pull            # 手动拉号（一般不需要）
```

### Statusline

apply 后写入 `~/.cursor/cli-config.json` 的 `statusLine`。一行紧凑状态：

- 常态：`SC A OK 67.2% [######....] a12.0% p55.0% user@x/pro #12`
- 刷新：`SC A ↻#12 OK …`
- 换号：`SC SWITCH 96.0% … thr>=95% → …`

`A`=auto 开，`-`=关。详情用 `sc status`。

**重启一次 `ag`** 后 statusLine 与 auto-boot 生效。若你已有自定义 statusLine，apply 会覆盖 `statusLine` 字段（其它 cli-config 项保留）。
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
