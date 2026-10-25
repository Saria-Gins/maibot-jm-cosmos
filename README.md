# JM-Cosmos for MaiBot

把 [JM-Cosmos](https://github.com/GEMILUXVII/astrbot_plugin_jm_cosmos)（AstrBot 版）移植到 **MaiBot** 的插件：搜索、榜单、推荐、下载单行本并打包成 PDF 发送。

> 本插件是 [GEMILUXVII/astrbot_plugin_jm_cosmos](https://github.com/GEMILUXVII/astrbot_plugin_jm_cosmos) 的移植版本，功能与命令设计均来自原作者。感谢 GEMILUXVII 的开源工作。

## ⚠️ 内容分级与使用范围

**请在使用前阅读。**

- 本插件访问的第三方站点以成人向（R18）内容为主，且内容多为未授权转载。插件本身不托管、不上传、不传播任何内容，只做"用户主动发起 → 下载到本机"的动作。
- **默认只在私聊可用**（`allow_groups = false`）。群聊必须由部署者显式开启并自行确认合规，插件不会主动往任何群聊推送内容。
- 是否使用、在什么范围使用、是否需要年龄限制，由部署者自行负责。请遵守你所在地区的法律法规。
- 如果你只是想在个人环境里使用，保持默认配置即可；不要在没有确认合规的前提下把它接到公开群。

## 功能

| 命令 | 说明 | 示例 |
| --- | --- | --- |
| `/jm 编号` | 下载整本 → 打包 PDF → 发送 | `/jm 1480638` |
| `/jmi 编号` | 查看标题、页数、作者、标签 | `/jmi 1480638` |
| `/jms 关键词` | 搜索本子 | `/jms 关键词` |
| `/jmrank [week\|month] [页码]` | 周榜 / 月榜 | `/jmrank month 2` |
| `/jmrec [排序] [时间] [页码]` | 按排序与时间取推荐 | `/jmrec view week` |
| `/jmhelp` | 帮助 | `/jmhelp` |

`/jmrec` 参数（均可省略，顺序随意）：

- 排序：`latest` / `view` / `picture` / `like` / `score`（也接受 `mr` `mv` `mp` `tf` `tr`）
- 时间：`all` / `today` / `week` / `month`（也接受 `a` `t` `w` `m`）

另外提供一个 LLM 工具 `jm_search_albums`，只做搜索、不触发下载。

## 安装

1. 把本仓库克隆或解压到 `MaiBot/plugins/maibot-jm-cosmos/`
2. 安装依赖：

```bash
pip install "jmcomic>=2.6.10" pymupdf
```

3. 重启 MaiBot。首次启动时插件会按配置模型生成 `config.toml`。

## ⚠️ 依赖冲突说明（重要）

`jmcomic` 依赖一个**顶层包 `common`**，而 MaiBot 自己也有 `src/common`。插件运行时 `src` 在 `sys.path` 里，`import common` 会解析到 MaiBot 的实现，导致：

```
ImportError: cannot import name 'time_stamp' from 'common'
```

这不是本插件能绕过的：`jmcomic` 在多处函数体内做 `from common import ...` 懒加载，运行时仍会命中同一个名字。

**可选方案（按推荐顺序）：**

1. **给 jmcomic 单独虚拟环境**：另建 venv 跑一个下载小工具，插件用子进程调用它。对主环境零侵入，但要自己维护第二条依赖链。
2. **修改 site-packages（本仓库 `scripts/fix_common_conflict.py` 提供）**：把 `common` 重命名为 `jmcommon` 并改写引用。**这是对用户环境的破坏性操作**——虽然本仓库实测当前环境中只有 `jmcomic` 引用 `common`，但其他插件或库如果将来引入同名依赖，会受影响。脚本默认只打印计划，需要 `--apply` 才执行，并在执行前自动备份与二次检查。

无论选哪种，都请先备份环境。**升级或重装 jmcomic 后需要重新处理。**

## 配置

`config.toml` 由插件运行时生成，字段如下：

| 字段 | 默认 | 说明 |
| --- | --- | --- |
| `download.base_dir` | 空 | 留空使用插件数据目录下的 `downloads`；也可填绝对路径 |
| `download.max_pages` | 300 | 单本页数上限，超过直接拒绝 |
| `download.timeout_seconds` | 600 | 单次下载超时 |
| `download.keep_images` | false | 打包后是否保留原图 |
| `download.pdf_max_mb` | 60 | PDF 超过该体积只回路径不发送 |
| `download.delete_pdf_after_send` | true | 发送成功后自动删除 PDF |
| `access.allowed_users` | 空 | 用户白名单；留空表示所有人 |
| `access.allowed_groups` | 空 | 群白名单；`allow_groups` 开启后生效 |
| `access.allow_groups` | **false** | **是否允许群聊使用；默认关闭** |

### 权限规则

1. 群聊且 `allow_groups = false` → 拒绝（默认行为）
2. `allowed_users` 非空时，调用者必须在其中
3. `allowed_groups` 非空时，群号必须在其中

## 实现说明

- 下载走 `jmcomic`，PDF 用 `pymupdf` 生成；由于 MuPDF 不认 webp，先用 Pillow 转 JPEG 再插入页面
- 每个会话一把 `asyncio.Lock`，重复命令会被拒绝而不是并行覆盖目录
- 拼接下载目录后校验仍在根目录内，避免路径穿越
- 文件通过 `send.custom("file", ...)` 以 `file:///` URI 交给适配器；平台不支持文件时回退成文本路径
- 下载和打包都在线程池里跑，不阻塞事件循环

## 已知限制

- 目标站点连接不稳，`jmcomic` 会自动换域名重试；网络差时一次下载可能较慢
- 周榜接口目前经常返回空列表，属站点侧情况
- 文件发送能力依赖适配器实现（SnowLuma / NapCat 的 `upload_private_file`）

## 致谢

- 原作者：[**GEMILUXVII**](https://github.com/GEMILUXVII)
- 原项目：[astrbot_plugin_jm_cosmos](https://github.com/GEMILUXVII/astrbot_plugin_jm_cosmos)
- 本移植版：[Saria-Gins/maibot-jm-cosmos](https://github.com/Saria-Gins/maibot-jm-cosmos)

命令设计、功能范围与交互文案均继承自原项目，移植仅替换了宿主框架相关的部分（AstrBot Star API → MaiBot plugin SDK）。

## 许可证

GPL-3.0-or-later，与原项目保持一致。详见 [LICENSE](LICENSE)。