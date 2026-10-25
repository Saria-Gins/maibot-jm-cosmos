#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""处理 jmcomic 的 `common` 包与 MaiBot `src/common` 的命名冲突。

默认只打印计划；加 --apply 才会执行重命名与引用改写。
执行前会：
  1. 扫描 site-packages，确认除 jmcomic 外没有其他包引用顶层 `common`
  2. 把原 `common` 目录备份到 common.backup-<时间戳>
  3. 改名并改写 jmcomic / 新包内部的 `from common import ...`
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import site
import sys
import time
from pathlib import Path

PACKAGE_OLD = "common"
PACKAGE_NEW = "jmcommon"
FROM_RE = re.compile(r"(?m)^(\s*from\s+)common(\s+import\b)")
IMPORT_RE = re.compile(r"(?m)^(\s*import\s+)common(\s*$)")


def site_packages() -> Path:
    """定位当前解释器的 site-packages。"""

    for path in site.getsitepackages() + [site.getusersitepackages()]:
        candidate = Path(path)
        if candidate.is_dir():
            return candidate
    raise SystemExit("找不到 site-packages 目录")


def other_importers(sp: Path) -> list[Path]:
    """找出除 jmcomic / common 之外引用顶层 common 的文件。"""

    hits: list[Path] = []
    for py in sp.rglob("*.py"):
        parts = py.parts
        if "jmcomic" in parts or PACKAGE_OLD in parts:
            continue
        try:
            text = py.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for line in text.splitlines():
            stripped = line.lstrip()
            if stripped.startswith(("from common import", "from common.", "import common")):
                hits.append(py)
                break
    return hits


def rewrite(root: Path) -> int:
    """把 root 下所有 .py 里的 common 引用改成 jmcommon。"""

    changed = 0
    for py in root.rglob("*.py"):
        text = py.read_text(encoding="utf-8", errors="ignore")
        new = IMPORT_RE.sub(r"\1jmcommon\2", FROM_RE.sub(r"\1jmcommon\2", text))
        if new != text:
            py.write_text(new, encoding="utf-8", newline="\n")
            changed += 1
    return changed


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--apply", action="store_true", help="真正执行修改，默认只打印计划")
    args = parser.parse_args()

    sp = site_packages()
    old_dir = sp / PACKAGE_OLD
    new_dir = sp / PACKAGE_NEW
    jm_dir = sp / "jmcomic"

    print(f"site-packages: {sp}")
    if not old_dir.is_dir() or not jm_dir.is_dir():
        print("没有检测到 common / jmcomic 目录，可能已经处理过或未安装 jmcomic。")
        return 1
    if new_dir.exists():
        print(f"{new_dir} 已存在，请先确认是否已处理过。")
        return 1

    hits = other_importers(sp)
    print(f"除 jmcomic 外引用顶层 common 的文件：{len(hits)} 个")
    for hit in hits[:10]:
        print("  -", hit)
    if hits:
        print("存在其他使用者，重命名会影响它们。请改用独立虚拟环境方案。")
        return 2

    print("\n计划：")
    print(f"  1. 复制 {old_dir} -> {new_dir}")
    print(f"  2. 改写 {PACKAGE_NEW} 与 jmcomic 内部的 common 引用")
    print(f"  3. 把原目录改名为 {PACKAGE_OLD}.backup-<时间戳>（不删除，可回滚）")

    if not args.apply:
        print("\n这是预演。确认无误后加 --apply 执行。")
        return 0

    stamp = time.strftime("%Y%m%d-%H%M%S")
    backup = old_dir.with_name(f"{PACKAGE_OLD}.backup-{stamp}")

    if new_dir.exists():
        print(f"{new_dir} 已存在，为避免覆盖已改写过的包，请先人工确认后移走它再重试。")
        return 1

    shutil.copytree(old_dir, new_dir, ignore=shutil.ignore_patterns("__pycache__"))
    changed = rewrite(new_dir) + rewrite(jm_dir)

    # 只改名，不删除：原目录保留为 <common>.backup-<时间戳>，随时可回滚
    os.rename(old_dir, backup)
    print(f"已改写 {changed} 个文件。")
    print(f"原目录已改名为 {backup.name}（未删除），需要回滚时改回 {PACKAGE_OLD} 即可。")
    print("建议重启 MaiBot 后验证 import jmcomic 是否正常。")
    return 0


if __name__ == "__main__":
    sys.exit(main())