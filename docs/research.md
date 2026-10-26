# 检索覆盖扩展研究

## 2026-10-26：完整增强客户端分发

用户要求完整原版功能加年度榜，目标电脑不需要预装哔哩哔哩、Python 或 Node.js。采用本机已验证的客户端运行文件、原版引导包 1.17.2、公共运行资源 1.19.0，加自有年度榜模块和静态数据。没有另写网页播放器或替换客户端 UI。

实际阅读：[Electron resourcesPath](https://www.electronjs.org/docs/latest/api/process#processresourcespath)、[Electron 22 的 app 路径文档](https://github.com/electron/electron/blob/v22.3.27/docs/api/app.md#appsetpathname-path)、[用户目录设置经验 issue #24536](https://github.com/electron/electron/issues/24536)、[Inno Setup 6.7.3 示例](https://github.com/jrsoftware/issrc/blob/is-6_7_3/Examples/Example1.iss)、[非管理员安装选项](https://jrsoftware.org/ishelp/topic_setup_privilegesrequired.htm)及[官方构建工具下载](https://jrsoftware.org/isdl.php)。文档说明 `userData` 与 `sessionData` 应在应用就绪前设置；历史 issue 说明仅修改一条目录配置不代表所有缓存都迁移，所以需要实测空用户目录启动。

只读分析原版引导层确认其原生支持 exe 旁的 `versions/` 作为固定资源目录。内置 1.19.0 ASAR、`.version`、`.biliapp` 和 `.bilijsc` 四个公共代码文件；不复制 AppData 中的其他文件。`.appInfo` 是 `app-update.yml` 创建时间的散列，在目标电脑启动时生成，不能直接复制本机值，否则原版可能重置资源版本。

引导层仅在 `index.js` 开头加载 `process.resourcesPath/year-rank/bootstrap.cjs`，热更新 ASAR 保持原始字节。所有自有模块和快照都放在资源目录，不含开发者绝对路径。增强版在就绪前设置独立的 `bili-year-rank-enhanced` 用户目录和 Chromium 会话目录，日志写入该目录。

安装器使用 Inno Setup 6.7.3，默认按用户安装到 LocalAppData，创建桌面和开始菜单入口，卸载只移除自身安装文件。构建器只复制指定客户端文件及公共资源，排除原版卸载器、开发环境、账户数据和本机配置。源码仓库继续排除第三方二进制和本地构建产物。

编译器未附带简体中文消息文件，按[官方源码中的社区翻译](https://github.com/jrsoftware/issrc/blob/is-6_7_3/Files/Languages/Unofficial/ChineseSimplified.isl)补充，保留作者说明，固定到与编译器一致的 tag。

### 官方更新检查及风险

完整包保留原 `app-update.yml` 和 `electron-updater 5.3.0`。在空白增强版用户目录中实际启动，官方 `UpdateService` 完成检查：热更新列表包含 1.19.0 / 1.18.0 / 1.17.9；本次整包更新接口返回 latest 1.9.0，安装版 1.17.2 不满足更新条件，因此无实际新整包可用于升级验证。该返回只代表此次设备 / 灰度请求，不能代表所有用户或未来更新。

读取本机 `electron-updater` 的 `NsisUpdater.doInstall` 和 `BaseUpdater` 确认整包更新会启动官方下载的 NSIS 安装器，不经过本项目的 Inno 安装器，不能声称会保留注入入口；资源热更新也可能改动 Vue 路由和布局。没有更改官方更新源、伪造更新结果或关闭其通知。

增加独立启动器核对引导文件 SHA-256 和已验证的资源版本；未知变更后提示获取适配增强包，也允许继续启动客户端。不自动回滚新官方文件，不对未知包重新打补丁。参考[微软编译器输出选项](https://learn.microsoft.com/en-us/dotnet/csharp/language-reference/compiler-options/output)和[进程启动文档](https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.processstartinfo.useshellexecute?view=netframework-4.8.1)，使用 Windows 自带 .NET Framework 编译普通 GUI 启动器，无命令行窗口。

### 完整包验证记录

- 25 项原有测试、渲染器 / 引导模块 JavaScript 语法及静态桥接检查通过。
- 133 个分发文件通过 SHA-256 清单校验，18 年 9,173 条候选及 HTTPS 封面齐全；包内没有账户文件、本机配置和开发者路径。
- 在含空格及中文的另一安装路径完成安装、卸载、重新安装和启动器检查；空白增强版用户目录完成客户端主窗口加载，官方更新服务正常检查。运行进程来自该独立目录；尚未在完全没有原版安装记录的另一台电脑验证。
- 在临时目录移动启动器及相关校验文件后检查成功；模拟资源版本改为 1.20.0 和引导包被官方文件覆盖时，启动器均报告不兼容。
- 本轮桌面进入锁屏，按 computer-use 规则停止 UI 输入。完整包中的年度榜点击和原生播放器端到端验证仍待解锁后继续；此前开发副本已验证主页面切换，不冒充完整安装包的播放验证。

## 2026-10-26：年度榜作为侧栏主页面

适用环境：安装版引导包 1.17.2、热更新资源 1.19.0，复用客户端现有 Vue 3 和 Vue Router，不安装或替换框架。只读检查当前热更新包，确认 `Page` 为主布局路由，`Home`、`Selected` 为其子路由；详情页通过 `meta.isSubPage` 区分。

实际阅读的来源：

- [Vue Router 动态路由](https://router.vuejs.org/guide/advanced/dynamic-routing.html)：`addRoute(parentName, route)` 注册嵌套路由；若当前 URL 已指向新路由，添加后需重新匹配。
- [Vue 应用全局属性](https://vuejs.org/api/application.html#app-config-globalproperties)：通过现有应用的 `$router` 复用路由。客户端把应用挂在 `#app.__vue_app__`，这是实测的内部入口，后续客户端更新可能变化。
- [Vue KeepAlive 生命周期](https://vuejs.org/guide/built-ins/keep-alive.html#lifecycle-of-cached-instance)：在挂载 / 激活时显示榜单，在停用 / 卸载时隐藏；路由离开后也由 `afterEach` 清理显示状态。

采用 `Page` 下的 `/page/local-year-rank` 路由，设置 `isSubPage:false`。主内容承载于 `.app_container`，入口复用 `.app_sidebar--pages-wrap` 的原生列表结构和选中样式。没有侧栏时不渲染入口，避免启动阶段出现左下角备用按钮。页面自身继续使用 Shadow DOM，独立静态 HTML 保留原来的布局。

验证：确认运行进程位于项目 `client/` 副本后，实际点击年度榜，观察 URL 为 `/page/local-year-rank`；榜单占主内容区，显示封面。点击首页后回到 `/page/home/recommends`，再次进入榜单正常；点击精选后回到 `/page/selected`，年度榜不再覆盖原页面。原生播放器未在本轮验证。

## 2026-10-26：静态榜单封面修复

静态导出曾把 `cover` 固定为空，渲染器只输出播放占位符，导致所有封面缺失。检查已有搜索缓存确认 9,173 个候选均含 `pic`，来源为 `i0/i1/i2.hdslb.com`，不需要重新调用搜索接口。

采用最新有效缓存中的封面链接，统一为 HTTPS；地址限定为上述 CDN 主机。页面恢复 `<img>`，按 [MDN img 文档](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/img)使用 `loading="lazy"`、显式宽高、异步解码及 `referrerpolicy="no-referrer"`。图片加载失败时隐藏图片层，保留原有播放占位符。封面在线加载，榜单元信息继续固定在本地快照内。

验证：9,173 条封面链接全部写入年度 JSON 及 HTML 内嵌数据，原视频信息、排序和播放量采集时间逐条保持一致。三个 CDN 主机各抽检一个封面，HEAD 均返回 HTTP 200 和图片 Content-Type。25 项测试、JavaScript 语法与静态查询桥接检查通过。

## 2026-10-26：从固定 24 个词改为分组、按年代扩展

目标是增加指定发布年份的高播放视频候选，不能把搜索采集包装为全站完整索引。运行环境为 Python 3.13、标准库采集器和现有 SQLite 索引；客户端安装版引导层 1.17.2，已发现热更新资源 1.19.0。

### 已实际打开阅读的来源

1. [LittleYang0531 的历史搜索接口文档](https://github.com/LittleYang0531/bilibili-api-collect/blob/master/docs/search/search_request.md)：关键词必需、`order=click`、分页，以及 `numResults` 最大 1000 的记载。内容包含 2020 年示例，是历史逆向资料，不视为当前官方承诺。参数以本机先前的真实请求验证为准。
2. [xingchui/bilibili-search 服务源码](https://github.com/xingchui/bilibili-search/blob/master/app/services/bilibili.py)：只请求第一页 30 条，在本地按播放量排序再截取 20。适合小型关键词查询，但不满足跨主题候选覆盖，且不能把局部排序解释为全局前列。复用本项目现有已验证采集器更合适。
3. [Pyserini Robust04 的维护者实验文档](https://github.com/castorini/pyserini/blob/master/docs/experiments-robust04.md)：展示使用有限反馈文档、有限扩展词的 RM3 查询扩展，以及用实际检索指标评价结果。本项目不引入其 Lucene 索引或声称实现 RM3；只借鉴“有限反馈扩展＋测量增益”的工程做法。
4. [dsh-bilibili README](https://github.com/moxingovo/dsh-bilibili/blob/main/README.md)：其 0.2.3 版本说明了匿名检索、缓存、分页及风控错误。它仍是关键词检索封装，不能作为无需关键词的完整全站索引。

Stanford IR 教材的搜索摘要也涉及查询扩展，但正文打开多次失败（超时 / TLS EOF），因此不以其未成功打开的正文作为本次已验证依据。

### 采用方案

- 复用现有 WBI 请求、缓存、年份校验和去重存储，不新增检索库或安装依赖。
- 人工词库按 16 类主题轮换，增加动画、知识、运动、数码、人文、动物等过去覆盖不足的主题；年份本身随用户选择变化。
- 按年代和目标年份增加题材词；2011 不再固定使用“2018”作为默认年份词。
- 从已收录公开视频标签和作者中取少量补词。每个 BV 只计一次，限制扩展数量，过滤链接、控制字符和明显晚于目标年代的年份词。它是启发式候选扩展，不代表扩展词必然有效。
- 各关键词先请求第一页，再进入第二页及之后；可选择按当前候选榜的第 K 名播放量阈值停止低收益深翻。该优化依赖搜索排序与索引稳定，仍不能证明没有遗漏，提供完整深翻选项。
- 保存新增唯一候选、各词增益、实际查询页数、未完成词及前 100 变化。用真实运行的增益判断策略价值，不声称测得全站召回率。
- 缓存响应保留原始采集时间，不能把重新读取缓存的时间显示为播放量更新时间。

### 验证基线

2018 年：1,248 个候选、24 个命中词、47 个已缓存搜索页；候选第 100 名搜索播放量为 7,971,000。数据库已通过 SQLite backup API 备份至 `evidence/keyword_expansion/before.sqlite3`。2011 年另有 123 条现存候选，需要保持兼容。

### 运行中的连接重置

第一轮在第 19 个词“热门”处遇到 WinError 10054，已完成部分带来 175 个新增候选和 11 个新发现的前 100 条目。继续修改前实际阅读了 [Microsoft Winsock 错误码原文](https://github.com/MicrosoftDocs/win32/blob/docs/desktop-src/WinSock/windows-sockets-error-codes-2.md)中的 WSAECONNRESET 条目，以及 [CPython 3.13 urllib.error 文档源码](https://github.com/python/cpython/blob/3.13/Doc/library/urllib.error.rst)。前者解释连接重置，不能据此断言具体服务端原因；后者明确了 `URLError.reason` 与 `HTTPError` 的区分。

工程选择：仅对明确的连接重置 / 超时在原会话中延迟至少 5 秒重试一次，不更换身份或网络，不对 403 / 412 / 429、业务风控错误或错误 JSON 重试。若仍失败，保留快照并停止。下一轮使用已完成页的缓存，不重复消耗网络请求。

### `code=0` 的非正常空响应

真实扩展过程中发现部分 `data` 只有 `v_voucher`，没有 `result` / `numResults`。旧采集器把这类响应当作零结果并缓存，是本项目的缺陷，不能作为关键词无效的证据。发现后停止了该轮网络进程，已提交的视频数据仍保存在 SQLite 中。

修正前实际阅读：

- [bili-sync issue #613](https://github.com/amtoaer/bili-sync/issues/613)：2026-01 的同形响应案例，程序识别风险控制并终止该轮。
- [yt-dlp Bilibili 提取器](https://github.com/yt-dlp/yt-dlp/blob/master/yt_dlp/extractor/bilibili.py)：在网页风险数据含 `v_voucher` 时报告限制，而不是继续当正常视频解析。
- [tamnd/bilibili-cli README](https://github.com/tamnd/bilibili-cli/blob/main/README.md)：明确区分服务拒绝与真实零结果，不把拒绝响应写入缓存；其自行测量的接口需求不直接作为本项目参数保证。

采用方案：先识别风控字段，再验证搜索结果列表；风控凭据响应和缺少结果列表的响应均不写入正常缓存。HTTP 200 / `code=0` 本身不再足以判断成功。补上仅缓存汇总模式，以及逐页的原子进度快照，便于中断后审计和恢复。本轮剩余请求暂停，不自动解决验证码或更换身份重试。

### 本轮结果与可追溯性

- 2018 年候选由 1,248 增至 2,851，新增 1,603（+128.4%）；36 个新发现视频进入当前候选前 100。2011 年原有的 123 个候选仍保留。
- 中断后从基线备份及正常缓存离线回放，恢复出的候选数与已提交数据库一致。96 个关键词拥有至少一页有效缓存，包含基线已有缓存；不能解释为 96 个本轮新增联网查询。实际网络请求总数未完整恢复，报告将其设为 `null`。逐词增益受回放顺序影响，只衡量候选增长。
- 清除了 57 条含风控字段的无效搜索页缓存，仅保存去除凭据的元数据记录至 `evidence/keyword_expansion/discarded_invalid_cache.json`。有效视频数据保留；最终离线检查未发现正常缓存中残留无效响应。
- 最终本机 2018 广覆盖计划为 192 个词、20 组（16 类主题、年代、年度题材、标签、作者），快速方案为 56 个词。192 个计划词不等于已执行 192 次查询；当前导出元数据还有 96 个词没有有效处理页。动态补词随数据库增长可能变化。
- 桌面增强版的关键词入口通过 `plan` IPC 生成，支持手工编辑和按年更新，默认 5 秒间隔、80 个联网搜索页预算。外部模块在客户端启动时加载，更新后需重启增强版。
- 风控暂停状态按年份原子保存。仅在该年份明确执行在线采集、有实际联网搜索成功且该轮正常结束后清除；离线汇总、纯缓存命中及导出保留原提示。离线模式始终跳过统计请求。

输出榜单及覆盖对比在 `output/bilibili_2018_candidates.html` 和 `output/keyword_coverage_2018.md`。所有数字均针对候选集合，未解决全站索引完整性；每条播放量仍是各自采集时间的快照。

## 2026-10-26：按用户要求收敛为静态年度榜

用户明确停止扩词，要求提前整理各年份，先完成可浏览和播放的功能。本次不再扩充词库；一次性补数据只使用原有 16 个首轮主题词。

### 实际读过的补充来源

- [Electron IPC 文档](https://www.electronjs.org/docs/latest/tutorial/ipc)：采用已有的渲染进程到主进程请求 / 返回模式；只暴露 `catalog`、`list` 和 `hello`，主进程读取本地静态 JSON，移除采集、计划与后台进度通道。文档当前示例是 Electron 45，未升级本机 Electron，仅复用客户端中原先已经验证的 `ipcMain.handle` 桥接。
- [MDN script type](https://developer.mozilla.org/en-US/docs/Web/HTML/Reference/Elements/script/type)：非 JavaScript MIME 类型可作为数据块。独立 HTML 内嵌 `application/json`，把 `<` 转义成 Unicode，避免视频标题形成脚本结束标签，也避免 file 协议下再 fetch JSON 的限制。
- [Zixuan-Wang1215/Bilibili_Dataset README](https://github.com/Zixuan-Wang1215/Bilibili_Dataset/blob/main/README.md)：2024-08 的说明，保存每日前 100 热榜数据，不是按发布年份的当前累计播放榜，不能直接补全目标。
- [littlePING-221/bilibili-data-visualization README](https://github.com/littlePING-221/bilibili-data-visualization/blob/master/README.md)：采集的是 2022-01-18 至 2022-02-18、14 分区排行榜快照。其静态数据展示方式有参考价值，但这些旧统计不能冒充当前播放量，因此不混入本地当前榜。

### 实现及限制

`build_static.py` 从本地已收录数据生成 2009 年至今年的年度 JSON、年度目录以及一个可独立打开的 HTML。客户端运行时不再创建 Python 子进程或读取数据库，页面只保留年份、排序、显示数量、本地筛选和播放。过滤后的名次仍指向固定候选榜的原始名次。

`prepare_static.py` 是与运行时分离的一次性整理器。词表固定为已有首轮 16 个主题，各年轮流搜索，复用正常缓存，保存断点；任何服务器风控使整个批次停止，保留有效结果。生成空文件的年份必须标为 `pending`，不能把建立了目录解释为数据已经整理完成。

内置浏览器的自动预览拒绝了 `file://` 协议；没有用其他浏览器表面或临时服务绕过该限制。离线文件生成、过滤与桥接路径通过本地测试核对，视觉及原生播放端到端操作尚待验证。

### 早期年份的真实零结果响应

一次性整理在 2009 年“动画”处因缺少 `result` 列表停止。先检索并重新阅读了 [分类搜索字段说明](https://github.com/LittleYang0531/bilibili-api-collect/blob/master/docs/search/search_request.md)，其中 `numResults` 和 `numPages` 分别表示总条数与总页数。随后只读检查实际响应结构：`code=0`，两个计数均为整数 0，其他搜索元数据齐全，没有风控凭据，但省略了 `result`。脱敏结构已保存到 `evidence/static_empty_response_shape.json`。

仅对“两个计数均明确为整数 0 且缺少结果字段”的响应规范化为空列表；风控字段仍优先停止，缺计数、非零计数或不明格式仍停止。此处是本机实测支持的兼容修正，历史文档没有保证所有服务端版本都省略空列表。

### 静态版最终交付状态

- 发布 2009—2026 年的 18 个年度 JSON、年度目录、独立 HTML 与年度数量说明，共 9,173 个有效候选。2017 年先前的采集正常结束，保留 1,958 个；2018 年保留 2,851 个；2011 年保留 123 个。
- 固定主题一次性整理完成 223/240 项，在 2025 年“时尚”处出现 `v_voucher` 风控后立即停止，剩余 17 项未继续。没有缓存该风控响应，没有自动重试，也没有更换身份。
- 2009、2010、2012、2013 年分别为 10、62、69、73 条，仍不足 100。原计划在固定主题整理结束后对稀疏年份补翻已有查询的后续页，因本轮风控尚未执行；词表未增加。不能将“18 年均有快照”解释为所有年份数据完整。
- 年度目录标记未完成年份为 `partial`，界面显示“部分”并说明只展示已保存的结果；总进度及风控暂停写入目录和 `coverage.md`。客户端只读静态文件，没有采集 / 扩词 / 轮询通道，也不启动 Python。数据包缺失时只在榜单内提示，避免影响客户端启动。
- 最终 24 项单元 / 集成测试通过，桥接检查验证静态目录、筛选后原始排名、来源校验、重复加载、数据包缺失处理与无采集 IPC；JavaScript 语法检查通过。界面与原生播放操作因未做自动 UI 验证仍属验证缺口。
