# Changelog

## 2.1.0

- 内置查询桥接：新增 `scripts/jm_bridge.py`，jmcomic 在独立子进程运行，彻底绕开 `common` 与 `src/common` 的包名冲突；默认安装后即可查询，不需要改宿主 site-packages
- 插件进程不再 `import jmcomic`
- README 重写依赖说明，`fix_common_conflict.py` 降级为历史参考
- 保留 fail-closed 会话判定与群聊默认关闭


## 2.0.5

- 权限改为 fail-closed：新增 `_resolve_scope()` 判定 private / group / unknown，只有确认是私聊才放行，认不出来的会话一律拒绝并打 warning
- 移除按 stream_id 猜群号的 `_resolve_group_id`，命令与 LLM 工具统一走 `_allowed()`
- README 按 2.0.4 的真实行为重写：「插件能加载、查询会失败」；方案 1 明确说明需要自建桥接进程、本仓库未提供
- `scripts/fix_common_conflict.py` 删除残留的 `rmtree`，预演文案与实际行为一致

## 2.0.4

- `import jmcomic` 改为懒加载：`common` 包名冲突不再导致插件加载失败，首次调用时给出可读错误；`on_load` 增加依赖预检与 warning
- `scripts/fix_common_conflict.py` 预演输出与实际行为对齐（改名备份，不删除）
- 移除 `_looks_like_group` 上重复的 `@staticmethod`
- README 顶部新增加粗提示：默认环境会加载失败，安装前先读依赖冲突说明

## 2.0.3

- 群号解析失败不再当成私聊放行：新增 `_looks_like_group()`，识别到群聊但拿不到群号时拒绝并打 warning
- `scripts/fix_common_conflict.py` 不再删除原 `common` 目录，改为改名备份，可随时回滚；`read_text` 增加容错
- README 明确提示脚本可能影响无关包，独立 venv 优先

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