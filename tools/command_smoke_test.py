import json
from pathlib import Path

try:
    from astrbot.api import logger
except ImportError:
    # 在獨立環境或CI中沒有 astrbot 套件時，降級為簡單日誌
    class _SimpleLogger:
        @staticmethod
        def info(msg: str) -> None:
            print(f"[INFO] {msg}")

        @staticmethod
        def error(msg: str) -> None:
            print(f"[ERROR] {msg}")

    logger = _SimpleLogger()  # type: ignore

try:
    # 從 handlers.common_handlers 中複用 AST 解析邏輯
    from ..handlers.common_handlers import extract_command_table  # type: ignore
except ImportError:
    # 在未作為套件載入時（例如直接 python3 tools/xxx.py），使用本地 AST 解析
    import ast
    import os

    def extract_command_table():
        """
        從當前專案根目錄的 main.py 中解析所有 @filter.command 指令。
        與 handlers.common_handlers.extract_command_table 保持邏輯一致，
        但不依賴套件導入，方便在 CI / 獨立環境下執行。
        """
        # 定位到 ../main.py
        main_path = Path(__file__).resolve().parents[1] / "main.py"
        commands = []
        try:
            with main_path.open("r", encoding="utf-8") as f:
                src = f.read()
            tree = ast.parse(src)
            for node in ast.walk(tree):
                if not isinstance(node, ast.AsyncFunctionDef):
                    continue
                for dec in node.decorator_list:
                    if not (
                        isinstance(dec, ast.Call)
                        and isinstance(dec.func, ast.Attribute)
                        and dec.func.attr == "command"
                    ):
                        continue
                    if not dec.args or not isinstance(dec.args[0], ast.Constant):
                        continue
                    cmd = str(dec.args[0].value)
                    aliases = []
                    for kw in dec.keywords:
                        if kw.arg == "alias" and isinstance(
                            kw.value, (ast.List, ast.Tuple)
                        ):
                            for e in kw.value.elts:
                                if isinstance(e, ast.Constant):
                                    aliases.append(str(e.value))
                    seen = set()
                    uniq_aliases = []
                    for a in aliases:
                        if a not in seen:
                            seen.add(a)
                            uniq_aliases.append(a)
                    commands.append(
                        {"line": node.lineno, "command": cmd, "aliases": uniq_aliases}
                    )
            commands.sort(key=lambda x: x["line"])
        except Exception as e:
            logger.error(f"本地解析 main.py 指令清單失敗: {e}")
        return commands


def main() -> None:
    """
    簡單的指令自檢工具。

    功能：
    - 解析 main.py 中所有通過 @filter.command 聲明的指令
    - 輸出為人類可讀列表
    - 同時導出一份 JSON，方便後續集成自動化批量測試（例如調用機器人 HTTP 接口逐條發送）
    """
    commands = extract_command_table()
    if not commands:
        print("未能從 main.py 中解析出任何指令，請檢查日誌輸出。")
        return

    print("==== 釣魚插件指令總覽（按來源行號排序） ====")
    for c in commands:
        name = c["command"]
        aliases = c.get("aliases") or []
        alias_str = f" [別名: {', '.join(aliases)}]" if aliases else ""
        print(f"- /{name}{alias_str}")

    # 導出到 JSON，方便外部批量測試腳本使用
    out_path = (
        Path(__file__).resolve().parents[1]
        / "tmp"
        / "fishing_commands_snapshot.json"
    )
    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with out_path.open("w", encoding="utf-8") as f:
            json.dump(commands, f, ensure_ascii=False, indent=2)
        print(f"\n指令快照已導出：{out_path}")
        print("你可以在自己的集成測試中讀取這個 JSON，逐條向機器人發送指令做批量驗證。")
    except Exception as e:
        logger.error(f"導出指令 JSON 失敗: {e}")
        print(f"\n指令列表解析成功，但導出 JSON 失敗：{e}")


if __name__ == "__main__":
    main()

