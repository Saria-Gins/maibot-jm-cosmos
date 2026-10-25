# Changelog

## 1.0.0

- 从 AstrBot 版 astrbot_plugin_jm_cosmos 移植首版
- 支持 /jm 下载并打包 PDF、/jmi 详情、/jms 搜索
- 提供 jm_search_albums LLM 工具
## 1.1.0

- 新增 `/jmrank`：周榜 / 月榜
- 新增 `/jmrec`：按排序与时间范围取推荐列表
- 抽出 `_page_items` / `_format_album_list` 复用列表解析与排版
## 1.1.2

- 发送成功后自动删除 PDF（`download.delete_pdf_after_send`，默认开启）；发送失败时保留文件便于排查
## 1.1.3

- 新增 `access.allowed_groups`：群白名单，留空表示所有群可用，私聊不受限制
- 抽出 `_resolve_group_id`，从 kwargs / message 结构 / stream_id 三路解析群号