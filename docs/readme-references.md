# README 与发布说明参考

查阅日期：2026-10-26。以下 10 份 README 均实际打开，读取了项目介绍、功能、安装或发布入口等相关段落。采用通用的文档结构，不复制原项目文案。

| 项目 | 阅读来源 | 采用的组织方式 |
|---|---|---|
| Bilibili Evolved | [README](https://github.com/the1812/Bilibili-Evolved/blob/master/README.md) | 功能入口、安装、设置与兼容性分别说明 |
| PiliPala | [README](https://github.com/guozhigq/pilipala/blob/main/README.md) | 一句话简介、功能清单、下载与致谢 |
| PiliPlus | [README](https://github.com/bggRGjQaUbCoE/PiliPlus/blob/main/README.md) | 平台范围与已实现功能明确列出 |
| 哔哩助理 | [README](https://github.com/Richasy/Bili.Copilot/blob/master/README.md) | 安装与开发分开，写明 Windows 环境和使用入口 |
| biliup | [README](https://github.com/biliup/biliup/blob/master/README.md) | 快速开始按平台列步骤，单列首次使用 |
| RSSHub | [README](https://github.com/DIYgod/RSSHub/blob/master/README.md) | README 保留概览，详细部署说明放入独立文档 |
| 哔哩哔哩 API 收集整理 | [README](https://github.com/LittleYang0531/bilibili-api-collect/blob/master/README.md) | 写清项目范围、目录与参考来源 |
| B 站视频搜索工具 | [README](https://github.com/xingchui/bilibili-search/blob/master/README.md) | 功能特性、快速开始、测试、项目结构 |
| BewlyBewly | [README](https://github.com/BewlyBewly/BewlyBewly/blob/main/README.md) | 使用安装包与参与开发分别说明，列出适配范围 |
| yt-dlp | [README](https://github.com/yt-dlp/yt-dlp/blob/master/README.md) | 下载入口、Release 文件说明与源码安装分开 |

另外检查了 BBDown 和 downkyi 的当前 README，发现默认内容已改为归档 / 停止维护通知，因此没有把它们用作功能介绍模板。

## 本项目的发布组织

- 仓库：源码、测试、文档和公开静态榜单。
- Release：独立静态页面包、校验和与版本说明。
- 桌面集成：源码仓库提供自有集成与打包脚本；完整增强分发包另含客户端运行文件，保留第三方权利说明。官方程序副本、原始响应、账户缓存和本机配置不提交到 Git。
- README：简介、功能、快速开始、数据、开发、项目结构、致谢与许可。
- CHANGELOG：功能、数据状态、已知问题。

GitHub 官方说明也已阅读：[导入本地代码](https://docs.github.com/en/migrations/importing-source-code/using-the-command-line-to-import-source-code/adding-locally-hosted-code-to-github)、[大文件说明](https://docs.github.com/en/repositories/working-with-files/managing-large-files/about-large-files-on-github)、[仓库创建命令](https://cli.github.com/manual/gh_repo_create)。采用先在本地提交、再创建空仓库并推送的流程，避免自动生成 README 导致初始提交冲突。
