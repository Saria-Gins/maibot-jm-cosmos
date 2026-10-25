# JM-Cosmos Metadata for MaiBot

JM 漫画**元数据查询**插件：搜索、详情、榜单、推荐。

> 本插件移植自 [GEMILUXVII/astrbot_plugin_jm_cosmos](https://github.com/GEMILUXVII/astrbot_plugin_jm_cosmos) 的查询部分，感谢原作者的开源工作。
>
> **本版本只做只读查询：不下载、不打包、不发送任何文件。** 下载功能属于另一个独立版本，不在本仓库、也不在插件中心分发。

> [!IMPORTANT]
> **默认环境下装上去会直接加载失败，不是某条命令不好使。**
> `jmcomic` 依赖的顶层包 `common` 与 MaiBot 的 `src/common` 同名，导入阶段就会抛 `ImportError: cannot import name 'time_stamp' from 'common'`。
> **安装前请先读下面的「依赖冲突说明」**，按其中的方案 1（独立 venv）处理。

## 功能

| 命令 | 说明 | 示例 |
| --- | --- | --- |
| `/jmi 编号` | 查看标题、页数、作者、标签 | `/jmi 1480638` |
| `/jms 关键词` | 搜索，返回编号与标题 | `/jms 关键词` |
| `/jmrank [week\|month] [页码]` | 周榜 / 月榜 | `/jmrank month 2` |
| `/jmrec [排序] [时间] [页码]` | 按排序与时间取推荐 | `/jmrec view week` |
| `/jmhelp` | 帮助 | `/jmhelp` |

`/jmrec` 参数（均可省略）：

- 排序：`latest` / `view` / `picture` / `like` / `score`（也接受 `mr` `mv` `mp` `tf` `tr`）
- 时间：`all` / `today` / `week` / `month`（也接受 `a` `t` `w` `m`）

另外提供 LLM 工具 `jm_search_albums`，只返回编号与标题。

## 安装

1. 把本仓库克隆或解压到 `MaiBot/plugins/maibot-jm-cosmos/`
2. 安装依赖：

```bash
pip install "jmcomic>=2.6.10,<3"
```

3. 重启 MaiBot。首次启动会按配置模型生成 `config.toml`。

## 配置

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `query.timeout_seconds` | 45 | 单次查询超时 |
| `query.max_results` | 8 | 每个列表最多返回条数 |
| `access.allowed_users` | 空 | 用户白名单；留空表示所有人 |
| `access.allowed_groups` | 空 | 群白名单；留空表示所有群 |
| `access.allow_groups` | **false** | 是否允许群聊使用；默认关闭，避免成人向标题直接进群 |

权限规则：用户白名单命中 → 群聊开关 → 群白名单命中。三层都通过才放行。

**默认只在私聊可用**：站点条目以成人向为主，返回到群聊会造成不必要的影响。需要群聊的部署者请自行开启 `allow_groups` 并确认适用范围与合规责任。

## ⚠️ 依赖冲突说明

> 这一步没做的话，插件在**加载阶段**就会失败，而不是运行到某条命令才报错。

`jmcomic` 依赖一个**顶层包 `common`**，而 MaiBot 自己也有 `src/common`。插件运行时 `src` 在 `sys.path` 里，`import common` 会解析到 MaiBot 的实现，报错：

```
ImportError: cannot import name 'time_stamp' from 'common'
```

`jmcomic` 在多处函数体内做懒加载，只是把 import 推迟并不能真正绕过名字冲突。
本插件已把 `import jmcomic` 改成懒加载，好处是**插件本身能正常加载**、失败时给出可读提示；但要真正查到数据，仍然需要按下面的方案之一处理。可选方案：

1. **推荐**：给 jmcomic 单独 venv，插件通过子进程调用
2. 修改 site-packages（本仓库 `scripts/fix_common_conflict.py`，**可能影响你以为无关的包**，**强烈建议优先选方案 1**）：**属于破坏性操作**，脚本默认只预演；`--apply` 才执行，会先检查是否还有其它包引用 `common`（含 `from common.xxx` 子包写法），并且**只把原目录改名为备份、不删除**，可随时回滚

升级或重装 jmcomic 后需要重新处理。

## 实现说明

- 所有网络访问只经 `jmcomic` 请求 JM 站点，不涉及聊天记录、用户 ID、群号或插件配置
- 阻塞调用放在线程池里并带超时，不阻塞事件循环
- 输出只包含标题、编号、页数、作者、标签等元数据

## 已知限制

- 目标站点连接不稳，`jmcomic` 会自动换域名重试
- 周榜接口目前经常返回空列表，属站点侧情况
- 站点内容以成人向为主；本插件默认只在私聊可用，是否在群聊展示、在什么范围展示，由部署者自行负责

## 致谢

- 原作者：[**GEMILUXVII**](https://github.com/GEMILUXVII)
- 原项目：[astrbot_plugin_jm_cosmos](https://github.com/GEMILUXVII/astrbot_plugin_jm_cosmos)
- 本移植版：[Saria-Gins/maibot-jm-cosmos](https://github.com/Saria-Gins/maibot-jm-cosmos)

## 许可证

AGPL-3.0-or-later，与原项目一致（原项目即为 AGPL-3.0）。详见 [LICENSE](LICENSE)。