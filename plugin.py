"""JM-Cosmos (Metadata) for MaiBot.

只做元数据查询：搜索、详情、榜单、推荐。不下载、不打包、不发送文件。
移植自 AstrBot 插件 astrbot_plugin_jm_cosmos 的查询部分。
"""

from __future__ import annotations

import asyncio
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


from maibot_sdk import Command, Field, MaiBotPlugin, PluginConfigBase, Tool


class PluginSection(PluginConfigBase):
    """插件基础配置。"""

    __ui_label__ = "插件"
    __ui_order__ = 0

    enabled: bool = Field(default=True, description="是否启用插件")
    config_version: str = Field(default="2.0.0", description="配置版本")


class QuerySection(PluginConfigBase):
    """查询配置。"""

    __ui_label__ = "查询"
    __ui_order__ = 1

    timeout_seconds: int = Field(default=45, ge=5, le=300, description="单次查询超时时间（秒）")
    max_results: int = Field(default=8, ge=1, le=20, description="每个列表最多返回多少条")


class AccessSection(PluginConfigBase):
    """权限配置。"""

    __ui_label__ = "权限"
    __ui_order__ = 2

    allowed_users: List[str] = Field(default_factory=list, description="允许使用的 QQ 号；留空表示所有人可用")
    allowed_groups: List[str] = Field(default_factory=list, description="允许使用的群号；留空表示所有群可用")
    allow_groups: bool = Field(default=False, description="是否允许在群聊中使用；默认关闭，成人向标题不会直接进群")


_BRIDGE = Path(__file__).resolve().parent / "scripts" / "jm_bridge.py"


class JMMetaConfig(PluginConfigBase):
    """JM 元数据插件总配置。"""

    plugin: PluginSection = Field(default_factory=PluginSection)
    query: QuerySection = Field(default_factory=QuerySection)
    access: AccessSection = Field(default_factory=AccessSection)


class JMMetaPlugin(MaiBotPlugin):
    """JM 元数据查询插件。"""

    config_model = JMMetaConfig

    async def on_load(self) -> None:
        if not _BRIDGE.is_file():
            self.ctx.logger.warning(f"[JM] 缺少桥接脚本：{_BRIDGE}")
        else:
            self.ctx.logger.info(f"[JM] 查询桥接已就绪：{_BRIDGE}")
        self.ctx.logger.info("[JM] 元数据插件已加载（仅查询，不下载）")

    async def on_unload(self) -> None:
        """无需清理的资源。"""

    async def on_config_update(self, scope: str, config_data: Dict[str, Any], version: str) -> None:
        """配置热更新：仅记录日志，无持久化状态需要重建。"""

        del config_data
        if scope not in ("plugin", "self"):
            return
        self.ctx.logger.info(f"[JM] 配置已更新（scope={scope}, 版本={version}）")

    # ------------------------------------------------------------------ 数据层

    def _call_bridge(self, op: str, params: Dict[str, Any]) -> Any:
        """在线程里同步执行桥接进程。

        `subprocess.run(timeout=...)` 在超时会 kill 子进程，所以不会留下僵尸进程；
        线程本身在 kill 后也会很快结束。
        """

        if not _BRIDGE.is_file():
            raise RuntimeError("查询桥接脚本缺失，请重新安装插件")
        payload = json.dumps({"op": op, "limit": self.config.query.max_results, **params},
                             ensure_ascii=False)
        env = dict(os.environ)
        env.pop("PYTHONPATH", None)  # 不让宿主注入的路径污染子进程
        try:
            proc = subprocess.run(
                [sys.executable, str(_BRIDGE)],
                input=payload,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=self.config.query.timeout_seconds,
                env=env,
                cwd=str(_BRIDGE.parent),
            )
        except subprocess.TimeoutExpired as exc:
            self.ctx.logger.warning("[JM] 查询桥接超时，子进程已终止")
            raise RuntimeError("查询超时") from exc

        text = (proc.stdout or "").strip()
        if not text:
            detail = (proc.stderr or "").strip()[-300:]
            self.ctx.logger.warning(f"[JM] 桥接无输出: {detail or '无输出'}")
            raise RuntimeError("查询失败")
        try:
            data = json.loads(text)
        except json.JSONDecodeError as exc:
            self.ctx.logger.warning(f"[JM] 桥接返回非 JSON: {text[:200]}")
            raise RuntimeError("查询失败") from exc
        if not data.get("ok"):
            self.ctx.logger.warning(f"[JM] 桥接返回错误: {data.get('error')}")
            raise RuntimeError("查询失败")
        return data.get("result")

    async def _run_bridge(self, op: str, **params: Any) -> Any:
        """异步包装：把阻塞的桥接调用丢进线程池，避免卡住事件循环。"""

        return await asyncio.to_thread(self._call_bridge, op, params)

    async def _fetch_detail(self, album_id: str) -> Dict[str, Any]:
        """读取专辑详情。"""

        return await self._run_bridge("detail", album_id=album_id)

    async def _search(self, keyword: str, limit: int) -> List[Dict[str, str]]:
        """按关键词搜索。"""

        return await self._run_bridge("search", keyword=keyword, limit=limit)

    async def _ranking(self, kind: str, page: int, limit: int) -> List[Dict[str, str]]:
        """获取周榜 / 月榜。"""

        return await self._run_bridge("ranking", kind=kind, page=page, limit=limit)

    async def _recommend(self, order_by: str, time_range: str, page: int, limit: int) -> List[Dict[str, str]]:
        """按排序与时间范围获取推荐。"""

        return await self._run_bridge("recommend", order_by=order_by, time_range=time_range,
                                      page=page, limit=limit)

    @staticmethod
    def _format_list(title: str, items: List[Dict[str, str]]) -> str:
        """格式化列表输出。"""

        if not items:
            return f"{title}：没有取到内容，稍后再试。"
        lines = [f"{idx}. [{item['id']}] {item['name'][:60]}" for idx, item in enumerate(items, 1)]
        return f"{title}\n" + "\n".join(lines)

    # ------------------------------------------------------------------ 权限

    @staticmethod
    def _resolve_user_id(kwargs: Dict[str, Any]) -> str:
        """从 kwargs 或 message 结构解析调用者 QQ。"""

        value = str(kwargs.get("user_id") or "").strip()
        if value.isdigit():
            return value
        message = kwargs.get("message")
        if isinstance(message, dict):
            info = message.get("message_info") or {}
            if isinstance(info, dict):
                user_info = info.get("user_info") or {}
                if isinstance(user_info, dict):
                    value = str(user_info.get("user_id") or "").strip()
                    if value.isdigit():
                        return value
        return ""

    @staticmethod
    def _resolve_scope(stream_id: str, kwargs: Dict[str, Any]) -> Tuple[str, str]:
        """判定会话类型，返回 (scope, group_id)。

        scope 取值：group / private / unknown。
        只有能确认是私聊时才返回 private；其余一律 unknown，由权限层拒绝。
        """

        info: Dict[str, Any] = {}
        message = kwargs.get("message")
        if isinstance(message, dict):
            candidate = message.get("message_info")
            if isinstance(candidate, dict):
                info = candidate

        group_info = info.get("group_info")
        if isinstance(group_info, dict):
            value = str(group_info.get("group_id") or "").strip()
            return ("group", value) if value.isdigit() else ("unknown", "")

        if isinstance(info.get("user_info"), dict):
            return "private", ""

        for key in ("group_id", "group", "gid"):
            value = str(kwargs.get(key) or "").strip()
            if value.isdigit():
                return "group", value

        raw = str(stream_id or "")
        matched = re.search(r"(?:group|群)[:：_\-]?(\d{5,})", raw)
        if matched:
            return "group", matched.group(1)
        if re.search(r"(?:private|friend|私聊|好友)", raw, re.I):
            return "private", ""
        return "unknown", ""

    def _check_permission(self, user_id: str, scope: str = "unknown", group_id: str = "") -> bool:
        """用户白名单 + 会话类型 + 群白名单；无法确认会话类型时拒绝。"""

        allowed_users = [str(x).strip() for x in self.config.access.allowed_users if str(x).strip()]
        if allowed_users and str(user_id).strip() not in allowed_users:
            return False

        if scope == "unknown":
            self.ctx.logger.warning("[JM] 无法确认会话类型，按群聊策略拒绝本次调用")
            return False
        if scope == "private":
            return True
        if not self.config.access.allow_groups:
            return False
        allowed_groups = [str(x).strip() for x in self.config.access.allowed_groups if str(x).strip()]
        return not (allowed_groups and str(group_id).strip() not in allowed_groups)

    def _allowed(self, stream_id: str, user_id: str, kwargs: Dict[str, Any]) -> bool:
        """命令与工具共用的权限入口。"""

        user = user_id or self._resolve_user_id(kwargs)
        scope, group_id = self._resolve_scope(stream_id, kwargs)
        return self._check_permission(user, scope, group_id)

    # ------------------------------------------------------------------ 命令

    @Command("jmi", description="查看 JM 本子详情：/jmi 123456", pattern=r"^/jmi\s+(?P<album_id>\d+)")
    async def cmd_info(self, stream_id: str = "", user_id: str = "", matched_groups: Optional[Dict[str, str]] = None, **kwargs: Any) -> Tuple[bool, str, bool]:
        if not self.config.plugin.enabled:
            return True, "", 1
        user_id = user_id or self._resolve_user_id(kwargs)
        if not self._allowed(stream_id, user_id, kwargs):
            await self.ctx.send.text("你没有使用 JM 查询的权限。", stream_id)
            return True, "", 1
        album_id = str((matched_groups or {}).get("album_id") or "").strip()
        try:
            detail = await self._fetch_detail(album_id)
        except asyncio.TimeoutError:
            await self.ctx.send.text("查询超时，请稍后再试。", stream_id)
            return True, "", 1
        except Exception as exc:  # noqa: BLE001
            await self.ctx.send.text("查询失败，请稍后再试。", stream_id)
            return True, "", 1
        tags = "、".join(str(t) for t in detail["tags"][:8]) or "无"
        authors = "、".join(str(a) for a in detail["authors"][:4]) or "未知"
        await self.ctx.send.text(
            f"《{detail['name']}》\n编号：{detail['id']}\n页数：{detail['page_count']}\n作者：{authors}\n标签：{tags}",
            stream_id,
        )
        return True, "", 1

    @Command("jms", description="搜索 JM 本子：/jms 关键词", pattern=r"^/jms\s+(?P<keyword>.+)$")
    async def cmd_search(self, stream_id: str = "", user_id: str = "", matched_groups: Optional[Dict[str, str]] = None, **kwargs: Any) -> Tuple[bool, str, bool]:
        if not self.config.plugin.enabled:
            return True, "", 1
        user_id = user_id or self._resolve_user_id(kwargs)
        if not self._allowed(stream_id, user_id, kwargs):
            await self.ctx.send.text("你没有使用 JM 查询的权限。", stream_id)
            return True, "", 1
        keyword = str((matched_groups or {}).get("keyword") or "").strip()
        if not keyword:
            await self.ctx.send.text("用法：/jms 关键词", stream_id)
            return True, "", 1
        try:
            items = await self._search(keyword, self.config.query.max_results)
        except asyncio.TimeoutError:
            await self.ctx.send.text("搜索超时，请稍后再试。", stream_id)
            return True, "", 1
        except Exception as exc:  # noqa: BLE001
            await self.ctx.send.text("搜索失败，请稍后再试。", stream_id)
            return True, "", 1
        await self.ctx.send.text(self._format_list(f"搜索「{keyword}」", items), stream_id)
        return True, "", 1

    @Command("jmrank", description="JM 周榜/月榜：/jmrank week 1", pattern=r"^/jmrank(?:\s+(?P<args>.*))?$")
    async def cmd_rank(self, stream_id: str = "", user_id: str = "", matched_groups: Optional[Dict[str, str]] = None, **kwargs: Any) -> Tuple[bool, str, bool]:
        if not self.config.plugin.enabled:
            return True, "", 1
        user_id = user_id or self._resolve_user_id(kwargs)
        if not self._allowed(stream_id, user_id, kwargs):
            await self.ctx.send.text("你没有使用 JM 查询的权限。", stream_id)
            return True, "", 1
        raw = str((matched_groups or {}).get("args") or "").strip()
        kind = "week"
        page = 1
        for token in raw.split():
            lower = token.lower()
            if lower in ("week", "w", "周", "周榜"):
                kind = "week"
            elif lower in ("month", "m", "月", "月榜"):
                kind = "month"
            elif lower.isdigit():
                page = max(1, int(lower))
            else:
                await self.ctx.send.text(f"未知参数：{token}\n用法：/jmrank [week|month] [页码]", stream_id)
                return True, "", 1
        try:
            items = await self._ranking(kind, page, self.config.query.max_results)
        except asyncio.TimeoutError:
            await self.ctx.send.text("获取榜单超时，请稍后再试。", stream_id)
            return True, "", 1
        except Exception as exc:  # noqa: BLE001
            await self.ctx.send.text("获取榜单失败，请稍后再试。", stream_id)
            return True, "", 1
        title = f"JM {'周榜' if kind == 'week' else '月榜'} 第 {page} 页"
        await self.ctx.send.text(self._format_list(title, items), stream_id)
        return True, "", 1

    @Command("jmrec", description="JM 推荐：/jmrec [排序] [时间] [页码]", pattern=r"^/jmrec(?:\s+(?P<args>.*))?$")
    async def cmd_recommend(self, stream_id: str = "", user_id: str = "", matched_groups: Optional[Dict[str, str]] = None, **kwargs: Any) -> Tuple[bool, str, bool]:
        if not self.config.plugin.enabled:
            return True, "", 1
        user_id = user_id or self._resolve_user_id(kwargs)
        if not self._allowed(stream_id, user_id, kwargs):
            await self.ctx.send.text("你没有使用 JM 查询的权限。", stream_id)
            return True, "", 1
        raw = str((matched_groups or {}).get("args") or "").strip()
        order_map = {"latest": "mr", "mr": "mr", "view": "mv", "mv": "mv",
                     "picture": "mp", "mp": "mp", "like": "tf", "tf": "tf",
                     "score": "tr", "tr": "tr"}
        time_map = {"all": "a", "a": "a", "today": "t", "t": "t",
                    "week": "w", "w": "w", "month": "m", "m": "m"}
        order_by = "mr"
        time_range = "a"
        page = 1
        for token in raw.split():
            lower = token.lower()
            if lower in order_map:
                order_by = order_map[lower]
            elif lower in time_map:
                time_range = time_map[lower]
            elif lower.isdigit():
                page = max(1, int(lower))
            else:
                await self.ctx.send.text(
                    f"未知参数：{token}\n用法：/jmrec [latest|view|picture|like|score] [all|today|week|month] [页码]",
                    stream_id,
                )
                return True, "", 1
        try:
            items = await self._recommend(order_by, time_range, page, self.config.query.max_results)
        except asyncio.TimeoutError:
            await self.ctx.send.text("获取推荐超时，请稍后再试。", stream_id)
            return True, "", 1
        except Exception as exc:  # noqa: BLE001
            await self.ctx.send.text("获取推荐失败，请稍后再试。", stream_id)
            return True, "", 1
        order_name = {"mr": "最新", "mv": "最多观看", "mp": "最多图片", "tf": "最多喜欢", "tr": "最高评分"}.get(order_by, order_by)
        time_name = {"a": "全部时间", "t": "今天", "w": "本周", "m": "本月"}.get(time_range, time_range)
        await self.ctx.send.text(self._format_list(f"JM 推荐 · {time_name} · {order_name} 第 {page} 页", items), stream_id)
        return True, "", 1

    @Command("jmhelp", description="JM 元数据插件帮助", pattern=r"^/jmhelp\s*$")
    async def cmd_help(self, stream_id: str = "", **kwargs: Any) -> Tuple[bool, str, bool]:
        await self.ctx.send.text(
            "JM 元数据查询（不提供下载）\n"
            "/jmi 编号　查看详情\n"
            "/jms 关键词　搜索\n"
            "/jmrank [week|month] [页]　榜单\n"
            "/jmrec [排序] [时间] [页]　推荐\n"
            "/jmhelp　本帮助",
            stream_id,
        )
        return True, "", 1

    # ------------------------------------------------------------------ LLM 工具

    @Tool(
        "jm_search_albums",
        description="搜索 JM 漫画元数据，返回编号与标题。仅查询，不下载任何内容。",
        parameters={
            "type": "object",
            "properties": {"query": {"type": "string", "description": "搜索关键词"}},
            "required": ["query"],
        },
    )
    async def tool_search(self, query: str = "", **kwargs: Any) -> Dict[str, Any]:
        if not self.config.plugin.enabled:
            return {"success": False, "content": "插件未启用"}
        stream_id = str(kwargs.get("stream_id") or "").strip()
        user_id = self._resolve_user_id(kwargs)
        if not self._allowed(stream_id, user_id, kwargs):
            return {"success": False, "content": "当前会话未开放 JM 查询权限"}

        keyword = str(query or "").strip()
        if not keyword:
            return {"success": False, "content": "缺少关键词"}
        try:
            items = await self._search(keyword, min(6, self.config.query.max_results))
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "content": "搜索失败，请稍后再试"}
        if not items:
            return {"success": False, "content": "没有搜到结果"}
        return {"success": True, "content": "\n".join(f"[{i['id']}] {i['name']}" for i in items)}


def create_plugin() -> JMMetaPlugin:
    """宿主加载入口。"""

    return JMMetaPlugin()