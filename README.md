# AgentCLI Patchs

多 Agent CLI 补丁管理工具：交互式蓝色 CLI + 可扩展补丁。当前内置：

| Patch | 作用 |
|-------|------|
| `remove-qoder-warning` | 抑制 Qoder CLI 的 Windows 10 启动警告 |
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
  patches/   # remove-qoder-warning、cursor-agent
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
python main.py apply remove-qoder-warning
python main.py apply cursor-agent

# 状态 / 回滚
python main.py status
python main.py rollback cursor-agent
```

### `cursor-agent` 做了什么

逆向 `%LOCALAPPDATA%\cursor-agent\`：

- **Auth 热读 v2.3.1**（`index.js`）：
  - AuthStorage / keychain：去掉 `cachedAccessToken` 短路，每次 `readAuthData` / `getSecret`
  - 禁用两套 ephemeral（`auth-refresh` 的 `i` + 主链路内联 `R`）与 apiKeyOverride
  - **每次设 `Authorization` 前 `readFileSync(auth.json)` 强制覆盖 Bearer**（不信内存）
  - 请求时写 `%APPDATA%\Cursor\agentcli-last-bearer.json`（`sub`/`pid`）便于对照
  - 工厂强制 **file** AuthStorage；memory getter 兜底返回空
  - 禁用 `cursor-agent.ps1` 的 `NODE_COMPILE_CACHE`，避免补丁后仍跑旧字节码
- **statusLine**：leader auto 实时写 `sc_instances.json`；任意实例只读该 json 刷新用量/`#`；**时间**为当前时刻实时时钟；**模型**为用户所选（stdin）
- **配置**：只读 `%APPDATA%\Cursor\config.json`（`base_url` / `api_keys` 等，代码不硬编码）。可选用环境变量 `AGENTCLI_SC_CONFIG_SRC` 指向一份模板 config 做首次播种。
- **statusline**：提示符上一行显示额度 / 换号状态（`AxN` 表示 N 个在线实例）

应用后**必须完全退出并重启** `ag`。换号后对照：
`sc status` 的 `token … sub=` ≡ `agentcli-last-bearer.json` 的 `sub`。

### 配置与状态

`config.json` / `auth.json` / `sc_status.json`：`%APPDATA%\Cursor\`  
实例心跳：`%USERPROFILE%\.cursor\sc_instances.json`

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
- 换号：`SC SWITCH thr>=95% → …`（不展示旧账号满额条）

`A`=有 leader，`-`=无；多开时 `Ax2`。详情用 `sc status`。

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
