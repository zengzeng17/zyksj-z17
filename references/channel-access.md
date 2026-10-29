# 六渠道访问与排查

以下为2026-10-26实测经验，不保证接口长期不变。首次使用先查当前官方文档/本机SDK，做一个低成本请求，核对业务码和正文/列表字段，再展开。工具优先级由当前实际可用能力决定；TikHub/红狐不是唯一允许的数据源。

## 共同约定

- 复用当前会话安全认证；Key通过环境变量或用户已保存的私密配置文件读取，不输出、不进案例/Skill/网站。未授权的计费范围先确认，已有授权不重复索取。
- 先核验余额和成本，设单轮预算。给采集代码有界的页数/费用/重试守卫，失败/空页/重复游标/无新ID就停，保留实际停止原因。未知是否扣费时用余额差核验，不仅凭标价相加。
- 保存原始请求参数、HTTP与业务状态、请求/采集时间、来源字段。200不等于成功，成功不等于正文完整。
- 平台总命中、取回候选、唯一ID、窗内相关记录、正文深读、评论分别报数。正文/标题/摘要/口播/画面读取状态不得混称。
- 显式本地过滤用户给出的时间窗。查询带日期也要复核实际发布时间，末日与区间记录另标。

## X · TikHub web

- `/api/v1/twitter/web/fetch_search_timeline`：keyword、search_type、cursor。主对象名/常用写法加日期检索；返回`data.timeline`和`next_cursor`，按tweet_id去重。Latest不保证严格倒序，不因一个旧日期提前终止。
- `/fetch_tweet_detail`：tweet_id。读text、created_at、entities、quoted等实际结构，不用搜索摘要替代帖文。`quoted.tweet_id`可证明引用关系；浏览数是展示计数，不是独立人。
- `/fetch_post_comments`：tweet_id/cursor。实测评论在`data.thread`；不要把根帖重复计入评论。公开网页403时，已授权API仍可能成功。
- 核心截图取不到，可找公开转引并注明替代路径；可读到截图文字不等于认证原始文件/签发者。未经取得的媒体画面不写“已观看”。

## Hacker News · 免费Algolia

- `https://hn.algolia.com/api/v1/search_by_date`：query、tags=story、numericFilters（Unix窗口）、restrictSearchableAttributes=title,url,story_text、typoTolerance=false、hitsPerPage/page。
- 不关闭拼写纠错时“Kimi”可命中“similar”，须对象筛选。nbHits不是已经审读的相关样本量。
- `/api/v1/items/{id}`可取主帖及评论树；递归保留parent/id，排除根帖、删除/无正文及窗外节点。支持数/评论数为采集快照，不是用户采用量。

## Reddit · TikHub＋公开原帖降级

- `/api/v1/reddit/app/fetch_dynamic_search`：query、search_type=post、sort（例如NEW/RELEVANCE）、time_range、need_format、after。数据常在children[].post，正文content.markdown，游标pageInfo.endCursor/hasNextPage。
- 主帖ID的`t3_`要求以当前接口文档为准；参数验证422与上游400分开记。实测首屏成功而游标/其他查询400，不能推没有讨论。
- 控制一次默认参数/已知对象查询后若仍失败，不盲重试。尝试已授权公开网页、官方接口或可读搜索服务原帖；只能读搜索摘要则只作线索。
- 相对时间有缓存风险，不能凭“11h ago”加减出精确日期。有证据能确定在窗内但日期不精确时，可入相关内容总数、单列区间，不补入逐日序列。

## 微信公众号 · 红狐搜索＋TikHub正文

- 红狐POST `/story/api/gzhData/searchArticle`（优质库）与`/story/api/gzh/data/searchArticle`（广域库）：keyword、offset。实测20条一页，广域offset上限1000曾返回code3203；本轮适用性需核对，不能提前排队超过已知限制。
- data.list/total，workUrl、workUuid、title、author、publishTime、summary、readCount等。多词检索可能泛化，不能先假设AND语义；对照词和对象过滤均留档。
- 按URL中`__biz+mid+idx`规范化，跨库同一文章合并。相同标题不同账号是不同发布，但不当独立原创证据。阅读100001等可能是显示上限，不强行当精确人次。
- TikHub POST `/api/v1/wechat_mp/v2/fetch_article_detail_h5`：url、raw=false。只有实际存在`data.content.content_text`才记全文；HTTP200但只有错误提示或空内容仍不算正文成功。
- 不在读正文前仅因标题不带模型名排除可能相关稿；无法取得正文则明确仅标题/摘要，不做全文情绪编码。

## 视频号 · 红狐元数据＋原生分享链接＋按需口播

- 红狐POST `/story/api/sphAllData/searchWork`：keyword/page/size。按videoId去重，本地时间筛选；描述不当视频全文。未知播放量不填0、不把点赞当播放。
- TikHub POST `/api/v1/wechat_channels/v2/fetch_video_detail`：export_id、raw=false，取得真实object id；再`fetch_video_share_url`（object_id）取得真实分享URL，不编作品链接。
- 有授权和必要性时红狐`/story/api/parseWork/sphSubtitle/submit`（url）取taskId，`.../result`读状态和text/stampSents；有界轮询，不重复提交同一任务。口播可贵，优先关键正反案例，不全量ASR。
- ASR会误听模型名。读完转写不等于看完画面，更不等于复跑测试；引用需保留这一区别。

## 小红书 · TikHub App v2

- `/api/v1/xiaohongshu/app_v2/search_notes`：keyword/page/sort_type/time_filter，第一页search_id/search_session_id固定给后续分页。即便有一周内筛选，也做精确本地时间过滤。
- 图片/视频详情分别`get_image_note_detail`、`get_video_note_detail`（note_id）。图片实测为data.data[0].note_list[0]，视频可为data.data[0]；先检查两种结构，不因解析器只认识一种就写抓取失败。
- desc全文属于完整文案，不代表已OCR图文或看过视频。搜索desc通常只有片段。
- `get_note_comments`可带note_id及分页参数。Kimi案带index/sort_strategy返回400，移除可选参数默认请求成功；先单请求验证再批量。根评论和自动附带子回复去重，并过滤每条发布时间。

## 失败说明怎么写

写具体平台、接口/参数组合、HTTP/业务响应、是否有收费说明、已尝试替代路径、尚缺什么。明确区分“没取到”“取到了但没正文”“有正文但没核验测试”。不要写没有内容、没有传播或工具不支持整个渠道，除非证据真的覆盖该判断。
