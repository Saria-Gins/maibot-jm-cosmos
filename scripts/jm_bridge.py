#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""jmcomic 查询桥接进程。

插件通过子进程调用本脚本，把 jmcomic 的导入隔离在独立进程里：
子进程的 sys.path[0] 是 scripts 目录，不会包含 MaiBot 的 src，
因此 jmcomic 依赖的顶层包 `common` 能正确解析到 site-packages，
不受 `src/common` 同名冲突影响。

协议：stdin 读一个 JSON 对象 {"op": "...", ...}，stdout 输出
{"ok": true, "result": ...} 或 {"ok": false, "error": "..."}。
"""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, List


def _items(page: Any, limit: int) -> List[Dict[str, str]]:
    """把 JmSearchPage 的 content 统一成 {id, name, author} 列表。"""

    result: List[Dict[str, str]] = []
    for item in list(getattr(page, "content", []) or [])[:limit]:
        album_id, info = item
        result.append({
            "id": str(album_id),
            "name": str((info or {}).get("name") or ""),
            "author": str((info or {}).get("author") or ""),
        })
    return result


def handle(payload: Dict[str, Any]) -> Any:
    """按 op 分发查询，返回可 JSON 序列化的结果。"""

    import jmcomic

    client = jmcomic.JmOption.default().build_jm_client()
    op = str(payload.get("op") or "")
    limit = int(payload.get("limit") or 8)

    if op == "detail":
        detail = client.get_album_detail(str(payload["album_id"]))
        return {
            "id": str(getattr(detail, "album_id", "")),
            "name": str(getattr(detail, "name", "") or ""),
            "page_count": int(getattr(detail, "page_count", 0) or 0),
            "authors": [str(x) for x in (getattr(detail, "authors", []) or [])],
            "tags": [str(x) for x in (getattr(detail, "tags", []) or [])],
        }
    if op == "search":
        return _items(client.search_site(str(payload["keyword"]), 1), limit)
    if op == "ranking":
        kind = str(payload.get("kind") or "week")
        page = int(payload.get("page") or 1)
        fetch = client.week_ranking if kind == "week" else client.month_ranking
        return _items(fetch(page), limit)
    if op == "recommend":
        page = int(payload.get("page") or 1)
        order_by = str(payload.get("order_by") or "mr")
        time_range = str(payload.get("time_range") or "a")
        return _items(client.categories_filter(page, time_range, "0", order_by), limit)
    raise ValueError(f"未知操作: {op}")


def main() -> int:
    # jmcomic 的日志走 print，会污染 stdout 的 JSON；处理期间把 stdout 临时改成 stderr
    real_stdout = sys.stdout
    result: Any = None
    error = ""
    sys.stdout = sys.stderr
    try:
        payload = json.load(sys.stdin)
        result = handle(payload)
    except Exception as exc:  # noqa: BLE001 - 统一以 JSON 返回错误，便于宿主展示
        error = f"{type(exc).__name__}: {exc}"
    finally:
        sys.stdout = real_stdout

    if error:
        json.dump({"ok": False, "error": error}, sys.stdout, ensure_ascii=False)
        return 1
    json.dump({"ok": True, "result": result}, sys.stdout, ensure_ascii=False)
    return 0


if __name__ == "__main__":
    sys.exit(main())