# 向外看传播研究

围绕一条主线，用意图、设计、执行三层主文，给出有具体竞争对象、传播KM、demo和效果证据的报告。验证融入对应判断与可展开附录。默认重点渠道为X、HN、Reddit、公众号、视频号、小红书。

- `scripts/research.py init YYYY-MM-DD-slug --title '事件名称'` 建案。
- 填写case.json、原始证据、样本、计算与research-log.md。
- `validate`后生成`build <case-directory> --draft`检查；真实审读后填写绑定case哈希的qa.json，再正式`build`。
- 交付report.html，保留发布快照及图表。默认只本地交付，公开发布另需用户要求。

字段见docs/data-format.md，结论与图表约定见docs/communications-framework.md。
