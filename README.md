# JM-Cosmos for MaiBot

把 [JM-Cosmos](https://github.com/GEMILUXVII/astrbot_plugin_jm_cosmos)（AstrBot 版）移植到 **MaiBot** 的插件：搜索、榜单、推荐、下载单行本并打包成 PDF 发送。

> 本插件是 [GEMILUXVII/astrbot_plugin_jm_cosmos](https://github.com/GEMILUXVII/astrbot_plugin_jm_cosmos) 的移植版本，功能与命令设计均来自原作者。感谢 GEMILUXVII 的开源工作。

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

### 方式一：插件市场

MaiBot WebUI → 插件 → 市场，搜索 `JM-Cosmos`。

### 方式二：手动

1. 把本仓库克隆或解压到 `MaiBot/plugins/maibot-jm-cosmos/`
2. 安装依赖：

```bash
pip install "jmcomic>=2.6.10" pymupdf
```

3. 重启 MaiBot

## ⚠️ 必须处理的环境冲突

`jmcomic` 依赖一个顶层包 `common`，而 MaiBot 自己也有 `src/common`。插件运行时 `src` 在 `sys.path` 里，会把 `common` 抢过去，导致：

```
ImportError: cannot import name 'time_stamp' from 'common'
```

解决办法：把 site-packages 里的 `common` 重命名为 `jmcommon`，并改写 `jmcomic` 与 `jmcommon` 内部的 `from common import ...` 引用（约 21 个文件），然后删除原 `common` 目录。

**升级或重装 jmcomic 后需要重新处理一次。**

## 配置

`config.toml`：

```toml
[plugin]
enabled = true

[download]
base_dir = "data/plugins/gemiluxvii.jm-cosmos/downloads"
max_pages = 300              # 单本页数上限
timeout_seconds = 600        # 单次下载超时
keep_images = false          # 打包后是否保留原图
pdf_max_mb = 60              # 超过该体积只回路径不发送
delete_pdf_after_send = true # 发送成功后自动删除 PDF

[access]
allowed_users = []    # 用户白名单，留空 = 所有人
allowed_groups = []   # 群白名单，留空 = 所有群；私聊不受限
```

权限判定是两层独立过滤：`allowed_users` 管人，`allowed_groups` 管群。

## 实现说明

- 下载走 `jmcomic`，PDF 用 `pymupdf` 生成；由于 MuPDF 不认 webp，先用 Pillow 转 JPEG 再插入页面
- 每个会话一把 `asyncio.Lock`，重复命令会被拒绝而不是并行覆盖目录
- 文件通过 `send.custom("file", ...)` 以 `file:///` URI 交给适配器；平台不支持文件时回退成文本路径
- 下载和打包都在线程池里跑，不阻塞事件循环

## 已知限制

- JM 站点连接不稳，`jmcomic` 会自动换域名重试；网络差时一次下载可能较慢
- 周榜接口目前经常返回空列表，属站点侧情况，插件会提示"没有取到内容"
- 文件发送能力依赖适配器实现（SnowLuma / NapCat 的 `upload_private_file`）

## 致谢

- 原作者：[**GEMILUXVII**](https://github.com/GEMILUXVII)
- 原项目：[astrbot_plugin_jm_cosmos](https://github.com/GEMILUXVII/astrbot_plugin_jm_cosmos)
- 本移植版：[Saria-Gins/maibot-jm-cosmos](https://github.com/Saria-Gins/maibot-jm-cosmos)

命令设计、功能范围与交互文案均继承自原项目，移植仅替换了宿主框架相关的部分（AstrBot Star API → MaiBot plugin SDK）。

## 许可证

GPL-3.0-or-later，与原项目保持一致。详见 [LICENSE](LICENSE)。