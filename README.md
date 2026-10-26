# bili-year-rank

按发布年份整理的哔哩哔哩视频静态候选榜，支持离线浏览和 Windows 桌面客户端集成。

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

[快速开始](#快速开始) · [数据说明](#数据说明) · [安装文档](docs/installation.md) · [更新日志](CHANGELOG.md)

## 功能

- [x] 按视频发布年份浏览，提供 2009—2026 年的静态数据
- [x] 按累计播放量或发布时间排序
- [x] 按标题、UP 主、BV 号和最低播放量筛选
- [x] 筛选后保留原榜名次
- [x] 视频封面在线加载，支持懒加载与失败占位
- [x] 单文件 HTML，打开即可使用
- [x] Windows 桌面客户端侧栏入口（实验性）
- [x] Windows x64 完整增强版安装包与免安装包

## 快速开始

### 完整增强版（Windows）

从 [Releases](https://github.com/nishunyi/bili-year-rank/releases) 下载 `bili-year-rank-full-setup-v0.2.0-x64.exe`，按向导安装。也可下载 `full-portable` ZIP，完整解压后打开 `年度榜增强版.exe`。

包含原客户端运行文件和年度榜，**无需预装哔哩哔哩、Python 或 Node.js**。支持 Windows 10 / 11 x64。年度榜与首页、精选同级，点击其他侧栏页面即可切换。

使用独立用户目录，分发包不含作者账户。保留官方更新检查；官方后续升级可能覆盖增强入口或改变页面结构，启动器检测到变更会提示获取适配版本。详见[安装与更新说明](docs/installation.md)。

### 独立页面

1. 从 [Releases](https://github.com/nishunyi/bili-year-rank/releases) 下载静态榜单包并解压。
2. 打开 `index.html`。
3. 选择发布年份，点击视频标题或播放按钮打开视频网页。

也可下载本仓库，直接打开 [output/static/index.html](output/static/index.html)。浏览榜单不需要 Python、Node.js 或本地服务器。榜单文字数据可离线浏览，封面加载和视频播放需要联网。

### Windows 桌面集成

安装 Python 3.10+ 和兼容版本的哔哩哔哩客户端，退出客户端后运行 `安装增强入口.cmd`。从桌面的“哔哩哔哩（年度榜增强版）”进入侧栏“年度榜”。

目前适配 **1.17.2 引导包 + 1.19.0 热更新资源**，安装时检查文件哈希；仓库不附带官方客户端。完整步骤、版本要求和恢复方法见 [安装文档](docs/installation.md)。

## 数据说明

| 项目 | 当前数据 |
|---|---|
| 快照日期 | 2026-10-26 |
| 发布年份 | 2009—2026，共 18 年 |
| 候选总数 | 9,173 |
| 2018 年候选 | 2,851 |
| 2017 年候选 | 1,958 |
| 固定主题预整理 | 223/240 项 |

榜单按已收录候选的累计播放量排序，**不代表全站完整前 100**。播放量以每条视频标注的采集时间为准，不随页面打开自动更新。

预整理在服务端返回风控响应后暂停，剩余 17 项未完成。2009、2010、2012、2013 年分别收录 10、62、69、73 条，按实际数量显示；未完成年份在界面标为“部分”。各年明细见 [数据清单](output/static/coverage.md)。

静态数据仅包含公开视频元信息，不含视频文件、账户信息或 Cookie。

## 开发

Python 3.10+；JavaScript 桥接测试另需 Node.js。

```shell
git clone https://github.com/nishunyi/bili-year-rank.git
cd bili-year-rank
python -X utf8 -m unittest -v
node integration/test_bridge.cjs
```

从已有本地数据库重新生成静态页面：

```shell
python -X utf8 build_static.py
```

此命令需要已有的 `data/videos.sqlite3`。数据库、原始响应和本机配置不随仓库分发；直接使用已发布榜单无需重新生成。

一次性整理工具为 `prepare_static.py`，使用固定主题和缓存保存进度，遇到限制停止。桌面运行时只读取静态 JSON，不启动 Python 或执行采集任务。

## 项目结构

```text
bili-year-rank/
├── output/static/          # 年度 JSON、数据清单和独立页面
├── integration/            # 桌面入口、查询模块、安装与恢复脚本
├── packaging/              # 完整增强版构建、安装器与更新兼容性检查
├── docs/                   # 安装、研究记录和发布参考
├── bili_rank.py            # 搜索协议、缓存、年份校验与候选存储
├── build_static.py         # 离线生成静态榜单
├── prepare_static.py       # 固定范围一次性预整理
└── test_*.py               # 测试
```

## 当前状态

静态文件生成、数据一致性和桥接路径已通过本地测试。完整包已在独立安装位置和空白用户目录完成启动及官方更新检查；未知官方版本和其他电脑的运行环境仍需反馈验证。

完整包的原生播放器尚未完成端到端验证，预览版本不保证后续官方升级兼容。

## 致谢

- [bilibili API collect](https://github.com/LittleYang0531/bilibili-api-collect)：公开接口资料
- [Electron](https://github.com/electron/electron)：桌面集成所用 IPC 机制
- [README 与发布说明参考](docs/readme-references.md)：10 个项目的文档组织方式

## 许可

自有源码采用 [MIT License](LICENSE)。视频标题、UP 主信息等第三方元数据及哔哩哔哩客户端的权利归各自权利人所有。
