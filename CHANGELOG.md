# Changelog

## 2.0.2

- LLM 工具 `jm_search_albums` 补上权限校验：先判 `plugin.enabled`，再过 `_check_permission`（用户白名单 + 群聊开关 + 群白名单），默认私聊承诺不再从模型调用路径漏出
- `scripts/fix_common_conflict.py` 扫描范围扩展到 `from common.xxx` 子包写法，避免"没有其他使用者"的结论偏乐观

## 2.0.1

- 许可证统一为 AGPL-3.0-or-later，与仓库中的 AGPL-3.0 LICENSE 正文一致
- `access.allow_groups` 默认改为 `false`，成人向标题不会直接进入群聊
- 移除 `@Tool` 上无效的 `activation_type` 参数与 `ActivationType` 导入
- Command 返回值第三项改为明确权重 `1`
- 新增用户 ID 兜底：`kwargs.user_id` 缺失时从 `message.message_info.user_info` 读取
- `plugin.enabled` 现在真实生效


## 2.0.0

重构为**只读元数据查询**插件，以符合插件中心的收录范围：

- 移除 `/jm` 下载、PDF 打包与文件发送，插件不再产生任何文件
- 保留 `/jmi`、`/jms`、`/jmrank`、`/jmrec`、`/jmhelp` 与 `jm_search_albums` 工具
- 能力声明收敛为 `send.text`
- 依赖仅保留 `jmcomic`，并加上上界 `<3`
- `on_config_update` 的 scope 判断兼容 `self`
- `i18n` 去掉不存在的 `locales_path`
- `plugin_type` 设为 `tool`

## 1.1.6 及更早

见 git 历史（下载版，已移出本仓库）。