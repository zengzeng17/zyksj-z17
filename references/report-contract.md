# 案例数据格式 v1

工具只处理本地 JSON 和 HTML，不抓取、生成或核验外部事实。所有原文字段用纯文本；不嵌 HTML/Markdown，渲染时自动转义。正文段落通过 claim_ids 关联结论，再关联原文。下面的占位说明不是可交付的研究数据。

## 案例元信息

`case.json` 骨架见 templates/case.json。必填 schema_version=1、id（与案例目录名一致）、title、revision、status、as_of、change_note。as_of 是研究截止时点，含时区，例如 `2026-10-23T15:00:00+08:00`；不能把生成时间当成观察窗覆盖终点。

scope 的 object、question、window、coverage、limitations 均为文本；timezone 固定 Asia/Shanghai。时间窗可用自然语言写清不完整日。status 从 researching 改到 ready，表示内容整理完成；正式 build 仍要求当前版本的人工核验记录。

summary_claim_ids 是核心结论 ID 列表。正文 sections 可零到多个，每节 `{title, blocks: [{text, claim_ids: [结论ID]}]}`。分析结构按案例选；结论、来源、时间线、机制启发保持可追溯。

## 来源 sources

每项字段：

| 字段 | 含义 |
| --- | --- |
| id | 如 S1，字母开头，仅字母数字下划线连字符 |
| title / publisher / url | 原始标题、主体、具体原文 http(s) URL；不使用检索页替代原文 |
| kind | 官方发布、独立报道、合作方、用户原帖等，按实际填写 |
| family | 来源族；同一通稿/采访/视频衍生的转载应使用同一族 |
| published_at | 原始发布时间；只有日期就保留日期，未知写明未知及原因 |
| captured_at | 本次读取/采集时点，必须含时区 |
| access | full 已读正文 / partial 部分正文 / unavailable 正文不可得 / search_only 只有搜索线索 |
| note | 可支撑什么、不可支撑什么、替代来源/存档路径和访问限制 |

来源可以是现有用户附件中的引用，但要注明「转引，未独立读原文」，不能改标 full。

## 结论 claims

共同字段：id、text、kind、boundary、evidence。kind 取 fact / reported / inference / unknown。evidence 是 `{source_id, excerpt, locator}` 的列表；excerpt 保存短原话或明确标记的忠实摘要，locator 写段落、标题、视频时码或帖文位置。合理控制引文长度，遵守来源与工具规定的引用限额。

- fact：已核验的可观察事实，证据至少读到 full/partial；局部正文只能支撑局部事实。
- reported：某来源所作主张；句子明确归属该来源，不把主张写成客观已证实。
- inference：补充 reasoning、confidence（高/中/低）、alternatives（最强替代解释及区分理由）、falsifier（改变判断的新证据）。单一来源族会有警告，警告不能代替内容审慎。
- unknown：补充 reason；允许 evidence 为空，但要写为何未知、影响什么，而不是删除问题。

## 时间线 timeline

可选 `timeline_placement="appendix"` 将完整节点表放在主文分析之后；正文的关键时序仍需可视化。

每项 `{time, time_basis, actor, action, observation, source_ids}`。time 按北京时间升序人工排好；time_basis 说明是发生时间、发布时间还是粗略区间。action 和 observation 写可观察事实，策略功能写到推断结论里。没有反应数据就明说未观察到/无法判断，不填自创互动。

## 效果图与数据附件（可选扩展）

正文 block 可附 `figure`：title、caption、image_file、data_file。image_file为案例内SVG/PNG，data_file为案例内样本CSV或图表依据JSON；均须存在且不得越出案例目录。图像嵌入HTML，数据保留相对链接便于核查。图注交代窗口、单位、分母、实际采集时点及边界；定性图注明关系依据，不暗示未经测量的规模。

顶层可附 `method_notes`（文字列表）与 `analysis_files`（`{label,file}`列表）；程序在附录显示方法和数据下载。数据附件路径同样须在案例目录内。


## 指标 metrics（无可用数据时留空）

字段 name、value（数值或 null）、unit、definition、sample、method、captured_at、boundary、source_ids 必填。缺失 value=null 时加 missing_reason；不能把未知当成 0。百分比 unit=`%`，另填 numerator 与 denominator；工具核对计算值，允许四舍五入至约一位小数。

method=`source_reported` 表示转述来源的数字，需来源和明确归属；否则是自行统计，必须给案例目录内实际存在的 raw_file 与 calculation_file。原始样本、计算程序、可复核口径同时保留。公式、采样、去重、缺失与截断等放在 definition/sample/boundary 或研究日志；程序只核对字段与文件，不声称重算了复杂统计。

## 启发 lessons 与缺口 gaps

lessons 每项 `{mechanism, conditions, resources, cost, avoid, test, claim_ids}`：机制、适用条件、资源、代价、不适用情形、低成本验证、依据结论。

gaps 每项 `{item, reason, impact, next_step, requires_user}`。requires_user 必须为布尔值；只有非用户无法补齐且影响关键结论的事项才标 true。数据不可得一般不需要向用户提问。

## 质量记录 qa.json

四项 evidence / numbers / alternatives / render，每项 `{status, checked_at, notes}`。完成后 status=passed，checked_at 写含时区时点，notes 写实际检查对象、方法、发现和改动；没有统计也要写数字检查为何不适用。顶层 case_sha256 绑定最终 case.json 的 SHA-256。

先填好最终 case.json，再以 `build --draft` 查看报告；检查并记录桌面、窄屏及打印布局。随后完成 qa.json，运行正式 build。修改 case.json 后必须重做受影响的核验并更新绑定，不可直接复用旧检查。

正式生成写入 publication.json、published-case.json、published-qa.json；报告有实质变化时，旧报告及旧发布数据归档到 versions/。索引只收录状态就绪、质量记录通过且三个文件哈希匹配的案例。

### 本地采集计算来源（2026-10-26）

本研究自己的数量与词表统计应直接引用本地样本/计算记录，不借官方发布链接充当统计证据。`sources`允许`kind="本次采集计算"`、`url="samples.html"`等案例内相对文件；必须无协议、无绝对路径、无`..`，且`validate_files`确认文件存在、解析后不越出案例目录。其余原始事件来源仍须具体http(s)原文。本地统计来源只证明本次计算，不能认证平台总体数量或外部事件真实性。

## 封版阅读模式与demo（2026-10-28）

默认 `reading_mode="focused"`、`timeline_placement="appendix"`、`evidence_display="collapsed"`、`citation_style="named"`。summary_claim_ids优先关联一条主线；sections默认意图、设计、执行三节，由作者给各节清楚结论。模板不强制捏造内容以凑三层。

正文block可附 `demo`：`title`、`poster_file`、`caption`、`source_id`、`verification`必填；另有可选`video_url`（安全http(s)）或`video_file`（案例内MP4/WebM），两者至多一个。无视频时显示静态图。poster_file为案例内PNG/JPG/WebP/SVG，来源与核验说明必须如实写。视频默认不预加载、不自动播放，失败时保留封面、说明与原文入口。官方演示不当独立测试，整理流程图不当真实产品截图。

封版记录在项目内保存验收时点、用户验收说明、报告/数据/QA/构建文件的哈希快照；后续修改保留封版。验收与公开部署分别授权。
