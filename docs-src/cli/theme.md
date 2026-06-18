# Theme Customization Guide / 主题定制指南

This guide explains the blue theme system used by qoder-patchs, including the color palette, Rich theme configuration, Questionary styling, charmap-based ASCII art, and how to customize them.
本指南说明 qoder-patchs 使用的蓝色主题系统, 包括调色板, Rich 主题配置, Questionary 样式, charmap ASCII 艺术, 以及如何自定义.

---

## Architecture Overview / 架构概览

The theme system consists of four interconnected components:
主题系统由四个相互关联的组件组成:

```
+---------------------+     +---------------------+
| BluePalette         |     | BLUE_THEME           |
| (theme.py)          |---->| (Rich Theme)         |
|                     |     |                      |
| Color constants     |     | Style rules for      |
| (hex strings)       |     | Rich console output  |
+---------------------+     +----------+----------+
                                       |
                                       v
+---------------------+     +----------+----------+
| QUESTIONARY_STYLE   |     | BlueCLI (ui.py)     |
| (theme.py)          |     |                      |
|                     |     | Uses theme + palette |
| prompt_toolkit      |     | for all output       |
| style for menus     |     +----------------------+
+---------------------+

+---------------------+
| CHAR_MAP            |
| (charmap.py)        |
|                     |
| ASCII art glyphs    |
| + gradient palette  |
+---------------------+
```

---

## Blue Palette / 蓝色调色板

The `BluePalette` class in `theme.py` defines the color constants:
`theme.py` 中的 `BluePalette` 类定义颜色常量:

```python
class BluePalette:
    DARK_NAVY   = "#0a1628"   # Darkest blue / 最深蓝
    NAVY        = "#1a2744"   # Dark background / 深色背景
    DEEP_BLUE   = "#1e3a5f"   # Accent dark / 深色强调
    BLUE        = "#2563eb"   # Primary blue / 主蓝色
    BRIGHT_BLUE = "#3b82f6"   # Primary bright / 主亮蓝
    LIGHT_BLUE  = "#60a5fa"   # Secondary / 次要蓝
    SKY         = "#93c5fd"   # Light accent / 浅色强调
    ICE_BLUE    = "#bfdbfe"   # Very light / 极浅蓝
    WHITE_BLUE  = "#dbeafe"   # Near-white / 近白蓝
    SUCCESS     = "#22c55e"   # Green / 绿色
    WARNING     = "#eab308"   # Yellow / 黄色
    ERROR       = "#ef4444"   # Red / 红色
    INFO        = "#06b6d4"   # Cyan / 青色
    MUTED       = "#64748b"   # Gray / 灰色
```

These are hex color strings used throughout the Rich theme, Questionary style, and custom output helpers.
这些是十六进制颜色字符串, 用于 Rich 主题, Questionary 样式和自定义输出辅助函数.

---

## Rich Theme / Rich 主题配置

The `BLUE_THEME` is a Rich `Theme` object that maps style names to Rich markup:
`BLUE_THEME` 是一个 Rich `Theme` 对象, 将样式名映射到 Rich 标记:

```python
BLUE_THEME = Theme({
    "info":           "cyan",
    "warning":        "yellow",
    "error":          "bold red",
    "success":        "bold green",
    "header":         "bold bright_blue",
    "header.title":   "bold blue on dark_blue",
    "menu.selected":  "bold white on blue",
    "menu.unselected":"dim blue",
    "prompt":         "bold cyan",
    "accent":         "bright_blue",
    "muted":          "dim blue",
    "border":         "blue",
    "table.header":   "bold white on blue",
    "table.row":      "blue",
    "table.footer":   "bold bright_blue",
})
```

### Modifying Colors / 修改颜色

To change the theme colors, edit the `BLUE_THEME` definition in `src/qoder_patchs/cli/theme.py`:
要修改主题颜色, 编辑 `src/qoder_patchs/cli/theme.py` 中的 `BLUE_THEME` 定义:

```python
# Example: Change to a green theme
GREEN_THEME = Theme({
    "info":           "cyan",
    "warning":        "yellow",
    "error":          "bold red",
    "success":        "bold green",
    "header":         "bold green",
    "header.title":   "bold green on dark_green",
    "menu.selected":  "bold white on green",
    "menu.unselected":"dim green",
    "prompt":         "bold cyan",
    "accent":         "green",
    "muted":          "dim green",
    "border":         "green",
    "table.header":   "bold white on green",
    "table.row":      "green",
    "table.footer":   "bold green",
})
```

Rich style syntax:
Rich 样式语法:

| Syntax | Meaning |
|--------|---------|
| `"blue"` | Simple color name |
| `"bold"` | Bold text |
| `"dim"` | Dimmed text |
| `"bold blue"` | Bold + blue |
| `"white on blue"` | White text on blue background |
| `"#3b82f6"` | Hex color |
| `"bold #3b82f6 on #0a1628"` | Combined |

---

## Questionary Style / Questionary 样式

The Questionary style controls the appearance of interactive menus (arrow-key selections, checkboxes, confirmations):
Questionary 样式控制交互式菜单的外观 (方向键选择, 复选框, 确认):

```python
Style([
    ("qmark",        "fg:#3b82f6 bold"),   # Question mark prefix
    ("question",     "fg:#60a5fa bold"),   # Question text
    ("answer",       "fg:#22c55e bold"),   # Selected answer
    ("pointer",      "fg:#3b82f6 bold"),   # Arrow pointer
    ("highlighted",  "fg:#ffffff bg:#2563eb bold"),  # Currently highlighted
    ("selected",     "fg:#93c5fd"),         # Checkbox selected
    ("separator",    "fg:#1e3a5f"),         # Menu separator
    ("instruction",  "fg:#64748b"),         # Help text
])
```

To modify, update the `_build_questionary_style()` function in `theme.py`:
要修改, 更新 `theme.py` 中的 `_build_questionary_style()` 函数:

```python
def _build_questionary_style():
    from prompt_toolkit.styles import Style
    return Style([
        ("qmark",       "fg:#<hex> bold"),
        ("question",    "fg:#<hex> bold"),
        # ... etc
    ])
```

---

## Console Factory / 控制台工厂

The `get_console()` function creates a Rich Console configured for the blue theme:
`get_console()` 函数创建配置了蓝色主题的 Rich Console:

```python
def get_console(theme: bool = True) -> Console:
    kwargs = {}
    if theme:
        kwargs["theme"] = BLUE_THEME

    if sys.platform == "win32":
        kwargs["file"] = _get_utf8_stdout()
        kwargs["force_terminal"] = True

    return Console(**kwargs)
```

### Windows UTF-8 Handling / Windows UTF-8 处理

On Chinese Windows, the console uses GBK encoding (cp936), which cannot encode many Unicode symbols. The `_get_utf8_stdout()` helper wraps `sys.stdout.buffer` in a UTF-8 `TextIOWrapper` with `errors="replace"`, ensuring symbols like `ℹ`, `✔`, `✘`, `⚠` render correctly.

Additionally, `force_terminal=True` disables Rich's legacy Windows rendering, forcing it to emit ANSI escape codes directly.

---

## ASCII Art Character Map / ASCII 艺术字符映射

### CHAR_MAP

The `CHAR_MAP` dictionary in `charmap.py` maps characters to 6-line-high block glyphs:
`charmap.py` 中的 `CHAR_MAP` 字典将字符映射到 6 行高的方块字形:

```python
CHAR_MAP = {
    'A': [' █████╗ ', '██╔══██╗', '███████║', '██╔══██║', '██║  ██║', '╚═╝  ╚═╝'],
    'B': ['██████╗ ', '██╔══██╗', '██████╔╝', '██╔══██╗', '██████╔╝', '╚═════╝ '],
    # ... 90+ characters including:
    # - A-Z, a-z uppercase/lowercase
    # - 0-9 digits
    # - Punctuation: ! " # $ % & ' ( ) + , - . / : ; = ? @ [ \ ] { } | ^ ~ < >
    # - Symbols: ± × ÷ ° € £ ¥ ¢ § © ® ™
    # - Arrows: → ← ↑ ↓
    # - Math: ∑ ∆ √ ≤ ≥ ≠ ≈ ∴ ∵ ∈ ∉ ⊂ ⊃ ∪ ∩ ∞
    # - Greek: α β γ δ π Σ Ω
    # - Faces: ☺ ☹
    # - Suits: ♥ ♦ ♠ ♣
    # - Space, tab, newline
}
```

### Rendering Text / 渲染文本

Use `render_text()` to convert a string into 6-line ASCII art:
使用 `render_text()` 将字符串转换为 6 行 ASCII 艺术:

```python
from qoder_patchs.cli.charmap import render_text

lines = render_text("QODER")
# Returns 6 strings, each one row of the art:
# [' ██████╗  ██████╗ ██████╗ ███████╗██████╗ ',
#  '██╔═══██╗██╔══██╗██╔══██╗██╔════╝██╔══██╗',
#  ...]
```

Character lookup order:
1. Exact match in `CHAR_MAP`
2. Uppercase version
3. Lowercase version
4. Skip if not found

### Gradient Banner / 渐变横幅

`render_gradient_banner()` applies a diagonal color gradient to rendered ASCII art:
`render_gradient_banner()` 将渐变颜色应用到渲染的 ASCII 艺术:

```python
from qoder_patchs.cli.charmap import (
    render_text,
    render_gradient_banner,
    BLUE_GRADIENT_PALETTE,
)

lines = render_text("QODER")
banner = render_gradient_banner(lines, BLUE_GRADIENT_PALETTE)
print(banner)
```

The gradient palette is a list of RGB tuples:
渐变调色板是 RGB 元组列表:

```python
BLUE_GRADIENT_PALETTE = [
    (20, 80, 255),    # deep blue / 深蓝
    (40, 120, 255),   # medium blue / 中蓝
    (60, 160, 255),   # bright blue / 亮蓝
    (80, 200, 255),   # light blue / 浅蓝
    (100, 230, 255),  # ice blue / 冰蓝
]
```

Each non-space character is colored using an ANSI RGB escape sequence. The color is determined by a diagonal factor: characters at the top-left use the first palette color, and characters at the bottom-right use the last.
每个非空格字符使用 ANSI RGB 转义序列着色. 颜色由对角线因子决定: 左上角字符使用第一个调色板颜色, 右下角字符使用最后一个.

### Customizing the Banner / 自定义横幅

**Change banner text:**
**修改横幅文字:**

```python
# In app.py, the banner is rendered with:
cli.banner("QODER")

# Change to any text:
cli.banner("CUSTOM")
```

**Change gradient colors:**
**修改渐变颜色:**

```python
# Define a custom palette (green gradient):
GREEN_GRADIENT = [
    (10, 100, 50),
    (20, 150, 70),
    (30, 200, 90),
    (40, 230, 110),
    (50, 255, 130),
]

lines = render_text("QODER")
banner = render_gradient_banner(lines, GREEN_GRADIENT)
print(banner)
```

**Disable the banner:**
**禁用横幅:**

Set `show_banner = false` in `config.toml`:
在 `config.toml` 中设置:

```toml
[ui]
show_banner = false
```

Or via CLI:
或通过 CLI:

```bash
python main.py config set ui.show_banner false
```

---

## BlueCLI Output Methods / BlueCLI 输出方法

The `BlueCLI` class in `ui.py` provides high-level output methods that use the theme:
`ui.py` 中的 `BlueCLI` 类提供使用主题的高级输出方法:

| Method | Output | Color |
|--------|--------|-------|
| `cli.banner("TEXT")` | ASCII art with gradient | Blue gradient |
| `cli.header("Title")` | Rich panel with border | Blue border, bright title |
| `cli.success("msg")` | `✔ msg` | Green |
| `cli.error("msg")` | `✘ msg` | Red |
| `cli.warning("msg")` | `⚠ msg` | Yellow |
| `cli.info("msg")` | `ℹ msg` | Cyan |
| `cli.table(headers, rows)` | Rich table | Blue-themed |
| `cli.status_table(patches)` | Patch status table | Blue with status colors |
| `cli.divider()` | `───...───` | Dim |
| `cli.heavy_divider()` | `═══...═══` | Cyan |

---

## ANSI Color Helpers / ANSI 颜色辅助函数

Module-level helpers in `ui.py` (ported from warp.py) provide low-level ANSI formatting:
`ui.py` 中的模块级辅助函数 (从 warp.py 移植) 提供低级 ANSI 格式化:

```python
from qoder_patchs.cli.ui import (
    color_text,      # Wrap text in ANSI color
    kv_line,         # Key-value formatted line
    status_dot,      # Colored status circle
    divider,         # Thin horizontal rule
    heavy_divider,   # Thick cyan horizontal rule
    title_line,      # Bold white title
    subtitle_line,   # Dim subtitle
)
```

Constants: `RESET`, `BOLD`, `DIM`, `RED`, `GREEN`, `YELLOW`, `BLUE`, `MAGENTA`, `CYAN`, `WHITE`.

These are used internally and can also be used when extending the CLI with custom output.
这些在内部使用, 也可以在扩展 CLI 自定义输出时使用.

---

## Windows ANSI Support / Windows ANSI 支持

The `charmap.py` module automatically enables ANSI escape sequences on Windows at import time:
`charmap.py` 模块在导入时自动在 Windows 上启用 ANSI 转义序列:

```python
def _enable_windows_ansi():
    """Enable ENABLE_VIRTUAL_TERMINAL_PROCESSING on stdout."""
    import ctypes
    kernel32 = ctypes.windll.kernel32
    handle = kernel32.GetStdHandle(-11)
    mode = ctypes.c_ulong()
    kernel32.GetConsoleMode(handle, ctypes.byref(mode))
    kernel32.SetConsoleMode(handle, mode.value | 0x0004)
```

This is called automatically on `sys.platform == "win32"` and silently does nothing on other platforms.
这在 `sys.platform == "win32"` 时自动调用, 在其他平台上静默跳过.
