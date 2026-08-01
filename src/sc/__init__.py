"""Star Cursor 便携管理（/sc）：与 cursor-agent auth.json 同级。

注意：不要在此急切 import cli —— Agent 每秒 ``-m sc.statusline_fast``，
包级导入会拖进整棵命令树，导致 statusline 超时后底栏时钟冻结。
"""

__all__ = ["main"]


def __getattr__(name: str):
    if name == "main":
        from sc.cli import main

        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
