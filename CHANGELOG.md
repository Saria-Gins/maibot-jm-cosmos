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
## 1.1.4

- 修正 `_manifest.json` 的 `sdk` 版本范围：`2.16.0 ~ 2.17.99`（插件市场校验不允许第一、第二位为 99）
## 1.1.5

- 仓库不再提交 `config.toml`，并加入 `.gitignore`；配置由运行时生成
- 移除空转字段 `admin_bypass`，改为真实生效的 `access.allow_groups`（默认 false，仅私聊可用）
- `download.base_dir` 默认留空，回落到插件数据目录（`ctx.paths.data_dir`）
- 下载前校验目标目录仍在下载根目录内，防止路径穿越
- `_manifest.json` 增加 `plugin_type: tool`
- README 增加内容分级与使用范围说明；依赖冲突章节改为风险提示，并附 `scripts/fix_common_conflict.py`（默认只预演）
## 1.1.6

- 修正 `_manifest.json` 的 `id` 为 `github.saria-gins.maibot-jm-cosmos`，与插件中心登记一致