"""JM-Cosmos (Metadata) for MaiBot.

只做元数据查询：搜索、详情、榜单、推荐。不下载、不打包、不发送文件。
移植自 AstrBot 插件 astrbot_plugin_jm_cosmos 的查询部分。
"""

from __future__ import annotations

import asyncio
import re
from typing import Any, Dict, List, Optional, Tuple

import jmcomic

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


class JMMetaConfig(PluginConfigBase):
    """JM 元数据插件总配置。"""

    plugin: PluginSection = Field(default_factory=PluginSection)
    query: QuerySection = Field(default_factory=QuerySection)
    access: AccessSection = Field(default_factory=AccessSection)


class JMMetaPlugin(MaiBotPlugin):
    """JM 元数据查询插件。"""

    config_model = JMMetaConfig

    async def on_load(self) -> None:
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

    @staticmethod
    def _page_items(page: Any, limit: int) -> List[Dict[str, str]]:
        """把 JmSearchPage 的 content 统一成 {id, name, author} 列表。"""

        items: List[Dict[str, str]] = []
        for item in list(getattr(page, "content", []) or [])[:limit]:
            album_id, info = item
            items.append({
                "id": str(album_id),
                "name": str((info or {}).get("name") or ""),
                "author": str((info or {}).get("author") or ""),
            })
        return items

    def _client(self) -> Any:
        """构造 jmcomic 客户端。"""

        return jmcomic.JmOption.default().build_jm_client()

    def _fetch_detail(self, album_id: str) -> Dict[str, Any]:
        """读取专辑详情。"""

        detail = self._client().get_album_detail(album_id)
        return {
            "id": str(getattr(detail, "album_id", album_id)),
            "name": str(getattr(detail, "name", "") or ""),
            "page_count": int(getattr(detail, "page_count", 0) or 0),
            "authors": list(getattr(detail, "authors", []) or []),
            "tags": list(getattr(detail, "tags", []) or []),
        }

    def _search(self, keyword: str, limit: int) -> List[Dict[str, str]]:
        """按关键词搜索。"""

        return self._page_items(self._client().search_site(keyword, 1), limit)

    def _ranking(self, kind: str, page: int, limit: int) -> List[Dict[str, str]]:
        """获取周榜 / 月榜。"""

        client = self._client()
        fetch = client.week_ranking if kind == "week" else client.month_ranking
        return self._page_items(fetch(page), limit)

    def _recommend(self, order_by: str, time_range: str, page: int, limit: int) -> List[Dict[str, str]]:
        """按排序与时间范围获取推荐。"""

        return self._page_items(self._client().categories_filter(page, time_range, "0", order_by), limit)

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
    @staticmethod
    def _looks_like_group(stream_id: str, kwargs: Dict[str, Any]) -> bool:
        """判断当前会话是否像群聊：有 group_info，或 stream_id 带 group 标记。"""

        message = kwargs.get("message")
        if isinstance(message, dict):
            info = message.get("message_info") or {}
            if isinstance(info, dict) and isinstance(info.get("group_info"), dict):
                return True
        return bool(re.search(r"(?:group|群)", str(stream_id or "")))

    def _check_permission(self, user_id: str, group_id: str = "", is_group: bool = False) -> bool:
        """用户白名单 + 群聊开关 + 群白名单；群号解析不出来时按群聊拒绝。"""

        allowed_users = [str(x).strip() for x in self.config.access.allowed_users if str(x).strip()]
        if allowed_users and str(user_id).strip() not in allowed_users:
            return False
        group = str(group_id or "").strip()
        if not group:
            if is_group:
                # 看起来是群聊却拿不到群号：不能当成私聊放过
                self.ctx.logger.warning("[JM] 群号解析失败，按群聊拒绝本次调用")
                return False
            return True
        if not self.config.access.allow_groups:
            return False
        allowed_groups = [str(x).strip() for x in self.config.access.allowed_groups if str(x).strip()]
        if allowed_groups and group not in allowed_groups:
            return False
        return True

    @staticmethod
    def _resolve_group_id(stream_id: str, kwargs: Dict[str, Any]) -> str:
        """从 kwargs 或 stream_id 解析群号；私聊返回空串。"""

        for key in ("group_id", "group", "gid"):
            value = str(kwargs.get(key) or "").strip()
            if value.isdigit():
                return value
        message = kwargs.get("message")
        if isinstance(message, dict):
            info = message.get("message_info") or {}
            if isinstance(info, dict):
                group_info = info.get("group_info") or {}
                if isinstance(group_info, dict):
                    value = str(group_info.get("group_id") or "").strip()
                    if value.isdigit():
                        return value
        matched = re.search(r"(?:group|群)[:：_\-]?(\d{5,})", str(stream_id or ""))
        return matched.group(1) if matched else ""


    async def _run(self, func: Any, *args: Any) -> Any:
        """带超时地在线程池里执行阻塞查询。"""

        return await asyncio.wait_for(
            asyncio.to_thread(func, *args),
            timeout=self.config.query.timeout_seconds,
        )

    # ------------------------------------------------------------------ 命令

    @Command("jmi", description="查看 JM 本子详情：/jmi 123456", pattern=r"^/jmi\s+(?P<album_id>\d+)")
    async def cmd_info(self, stream_id: str = "", user_id: str = "", matched_groups: Optional[Dict[str, str]] = None, **kwargs: Any) -> Tuple[bool, str, bool]:
        if not self.config.plugin.enabled:
            return True, "", 1
        user_id = user_id or self._resolve_user_id(kwargs)
        if not self._check_permission(user_id, self._resolve_group_id(stream_id, kwargs), self._looks_like_group(stream_id, kwargs)):
            await self.ctx.send.text("你没有使用 JM 查询的权限。", stream_id)
            return True, "", 1
        album_id = str((matched_groups or {}).get("album_id") or "").strip()
        try:
            detail = await self._run(self._fetch_detail, album_id)
        except asyncio.TimeoutError:
            await self.ctx.send.text("查询超时，请稍后再试。", stream_id)
            return True, "", 1
        except Exception as exc:  # noqa: BLE001
            await self.ctx.send.text(f"查询失败：{exc}", stream_id)
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
        if not self._check_permission(user_id, self._resolve_group_id(stream_id, kwargs), self._looks_like_group(stream_id, kwargs)):
            await self.ctx.send.text("你没有使用 JM 查询的权限。", stream_id)
            return True, "", 1
        keyword = str((matched_groups or {}).get("keyword") or "").strip()
        if not keyword:
            await self.ctx.send.text("用法：/jms 关键词", stream_id)
            return True, "", 1
        try:
            items = await self._run(self._search, keyword, self.config.query.max_results)
        except asyncio.TimeoutError:
            await self.ctx.send.text("搜索超时，请稍后再试。", stream_id)
            return True, "", 1
        except Exception as exc:  # noqa: BLE001
            await self.ctx.send.text(f"搜索失败：{exc}", stream_id)
            return True, "", 1
        await self.ctx.send.text(self._format_list(f"搜索「{keyword}」", items), stream_id)
        return True, "", 1

    @Command("jmrank", description="JM 周榜/月榜：/jmrank week 1", pattern=r"^/jmrank(?:\s+(?P<args>.*))?$")
    async def cmd_rank(self, stream_id: str = "", user_id: str = "", matched_groups: Optional[Dict[str, str]] = None, **kwargs: Any) -> Tuple[bool, str, bool]:
        if not self.config.plugin.enabled:
            return True, "", 1
        user_id = user_id or self._resolve_user_id(kwargs)
        if not self._check_permission(user_id, self._resolve_group_id(stream_id, kwargs), self._looks_like_group(stream_id, kwargs)):
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
            items = await self._run(self._ranking, kind, page, self.config.query.max_results)
        except asyncio.TimeoutError:
            await self.ctx.send.text("获取榜单超时，请稍后再试。", stream_id)
            return True, "", 1
        except Exception as exc:  # noqa: BLE001
            await self.ctx.send.text(f"获取榜单失败：{exc}", stream_id)
            return True, "", 1
        title = f"JM {'周榜' if kind == 'week' else '月榜'} 第 {page} 页"
        await self.ctx.send.text(self._format_list(title, items), stream_id)
        return True, "", 1

    @Command("jmrec", description="JM 推荐：/jmrec [排序] [时间] [页码]", pattern=r"^/jmrec(?:\s+(?P<args>.*))?$")
    async def cmd_recommend(self, stream_id: str = "", user_id: str = "", matched_groups: Optional[Dict[str, str]] = None, **kwargs: Any) -> Tuple[bool, str, bool]:
        if not self.config.plugin.enabled:
            return True, "", 1
        user_id = user_id or self._resolve_user_id(kwargs)
        if not self._check_permission(user_id, self._resolve_group_id(stream_id, kwargs), self._looks_like_group(stream_id, kwargs)):
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
            items = await self._run(self._recommend, order_by, time_range, page, self.config.query.max_results)
        except asyncio.TimeoutError:
            await self.ctx.send.text("获取推荐超时，请稍后再试。", stream_id)
            return True, "", 1
        except Exception as exc:  # noqa: BLE001
            await self.ctx.send.text(f"获取推荐失败：{exc}", stream_id)
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
        group_id = self._resolve_group_id(stream_id, kwargs)
        if not self._check_permission(user_id, group_id, self._looks_like_group(stream_id, kwargs)):
            return {"success": False, "content": "当前会话未开放 JM 查询权限"}

        keyword = str(query or "").strip()
        if not keyword:
            return {"success": False, "content": "缺少关键词"}
        try:
            items = await self._run(self._search, keyword, min(6, self.config.query.max_results))
        except Exception as exc:  # noqa: BLE001
            return {"success": False, "content": f"搜索失败：{exc}"}
        if not items:
            return {"success": False, "content": "没有搜到结果"}
        return {"success": True, "content": "\n".join(f"[{i['id']}] {i['name']}" for i in items)}


def create_plugin() -> JMMetaPlugin:
    """宿主加载入口。"""

    return JMMetaPlugin()