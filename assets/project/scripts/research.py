#!/usr/bin/env python3
"""Project-local authoring helpers. No network calls or automated research claims."""
import argparse
import base64
import copy
import hashlib
import html
import json
import math
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from string import Template
from urllib.parse import quote, urlsplit
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]
REF = '自然意志Natura-1_传播策略反推_1010-1014.html'
KINDS = {'fact': '事实', 'reported': '信源主张', 'inference': '推断', 'unknown': '未知'}
ACCESS = {'full': '已读正文', 'partial': '仅部分正文', 'unavailable': '正文不可得', 'search_only': '仅搜索线索'}
CHECKS = ('evidence', 'numbers', 'alternatives', 'render')


def read_json(path):
    return json.loads(Path(path).read_text(encoding='utf-8'))


def write_json(path, data):
    Path(path).write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def esc(value):
    return html.escape(str(value), quote=True)


def present(value):
    return isinstance(value, str) and bool(value.strip())


def valid_url(value):
    try:
        p = urlsplit(value)
        return (p.scheme in ('http', 'https') and bool(p.hostname)
                and not p.username and not p.password and not re.search(r'[\s<>"\x00-\x1f]', value))
    except (TypeError, ValueError):
        return False


def valid_time(value):
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).utcoffset() is not None
    except (AttributeError, TypeError, ValueError):
        return False


def local_dataset(source):
    """Only explicitly identified, case-local calculations may use relative links."""
    value = source.get('url', '')
    return (source.get('kind') == '本次采集计算' and isinstance(value, str)
            and bool(re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_./-]*', value))
            and '..' not in Path(value).parts and not Path(value).is_absolute())


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def case_dir(value):
    path = Path(value)
    if not path.is_absolute():
        path = ROOT / path
    path = path.resolve()
    if path.parent != (ROOT / 'cases').resolve():
        raise ValueError('案例必须位于本项目 cases/ 的直接子目录')
    return path


def validate(data):
    """Structural checks only; returns (errors, warnings). Never verifies source truth."""
    errors, warnings = [], []

    def require(obj, fields, label):
        for key in fields:
            if not present(obj.get(key)):
                errors.append(f'{label}: 缺少文本字段 {key}')

    if not isinstance(data, dict):
        return ['case.json 顶层必须是对象'], []
    require(data, ('id', 'title', 'revision', 'as_of', 'change_note'), '案例')
    if data.get('schema_version') != 1:
        errors.append('schema_version 必须为 1')
    if not re.fullmatch(r'[a-zA-Z0-9][a-zA-Z0-9_-]*', data.get('id', '')):
        errors.append('id 仅接受英文字母、数字、下划线和连字符')
    if data.get('status') not in ('researching', 'ready'):
        errors.append('status 必须为 researching 或 ready')
    if not valid_time(data.get('as_of')):
        errors.append('as_of 必须是含时区的 ISO 截止时点')
    scope = data.get('scope', {})
    if not isinstance(scope, dict):
        errors.append('scope 必须是对象')
        scope = {}
    require(scope, ('object', 'question', 'window', 'timezone', 'coverage', 'limitations'), '研究范围')
    if scope.get('timezone') != 'Asia/Shanghai':
        errors.append('展示时区必须为 Asia/Shanghai')
    lists = ('sources', 'claims', 'timeline', 'sections', 'metrics', 'lessons', 'gaps', 'summary_claim_ids')
    clean = {}
    for key in lists:
        value = data.get(key)
        if not isinstance(value, list):
            errors.append(f'{key} 必须是列表')
            value = []
        if key != 'summary_claim_ids' and any(not isinstance(x, dict) for x in value):
            errors.append(f'{key} 的条目必须是对象')
            value = [x for x in value if isinstance(x, dict)]
        clean[key] = value

    def id_map(items, label):
        mapped = {}
        for item in items:
            ident = item.get('id')
            if not isinstance(ident, str) or not re.fullmatch(r'[A-Za-z][A-Za-z0-9_-]*', ident):
                errors.append(f'{label} ID 无效: {ident!r}')
            elif ident in mapped:
                errors.append(f'{label} ID 重复: {ident}')
            else:
                mapped[ident] = item
        return mapped

    sources = id_map(clean['sources'], '来源')
    claims = id_map(clean['claims'], '结论')

    def refs(values, mapping, label, required=True):
        if not isinstance(values, list) or any(not isinstance(x, str) for x in values):
            errors.append(f'{label}: 引用必须是字符串列表')
            return
        if required and not values:
            errors.append(f'{label}: 缺少引用')
        for value in values:
            if value not in mapping:
                errors.append(f'{label}: 引用不存在 {value}')

    for sid, source in sources.items():
        require(source, ('title', 'publisher', 'url', 'kind', 'family', 'published_at', 'captured_at', 'access', 'note'), sid)
        if not valid_url(source.get('url')) and not local_dataset(source):
            errors.append(f'{sid}: 必须有安全的 http(s) 具体原文链接')
        if source.get('access') not in ACCESS:
            errors.append(f'{sid}: access 无效')
        if not valid_time(source.get('captured_at')):
            errors.append(f'{sid}: captured_at 必须含时区')
        if source.get('access') in ('unavailable', 'search_only'):
            warnings.append(f'{sid}: 原文未读，不能据此认定事件事实')
    if not sources:
        errors.append('至少需要一个真实来源')
    for cid, claim in claims.items():
        require(claim, ('text', 'kind', 'boundary'), cid)
        kind = claim.get('kind')
        if kind not in KINDS:
            errors.append(f'{cid}: kind 无效')
        evidence = claim.get('evidence')
        if not isinstance(evidence, list):
            errors.append(f'{cid}: evidence 必须是列表')
            evidence = []
        if kind != 'unknown' and not evidence:
            errors.append(f'{cid}: 重要判断必须有具体原文证据')
        for ev in evidence:
            if not isinstance(ev, dict):
                errors.append(f'{cid}: evidence 条目必须是对象')
                continue
            require(ev, ('source_id', 'excerpt', 'locator'), cid + ' 证据')
            source = sources.get(ev.get('source_id', ''), {})
            if not source:
                errors.append(f'{cid}: 证据来源不存在')
            if kind == 'fact' and source.get('access') not in ('full', 'partial'):
                errors.append(f'{cid}: 事实不能仅由未读原文的线索支撑')
        if kind == 'inference':
            require(claim, ('reasoning', 'alternatives', 'falsifier', 'confidence'), cid)
            if claim.get('confidence') not in ('高', '中', '低'):
                errors.append(f'{cid}: 推断置信度仅为 高/中/低')
            families = {sources.get(ev.get('source_id'), {}).get('family') for ev in evidence if isinstance(ev, dict)}
            if len(families - {None}) < 2:
                warnings.append(f'{cid}: 推断少于两个来源族，需谨慎限定')
        if kind == 'unknown':
            require(claim, ('reason',), cid)
    refs(clean['summary_claim_ids'], claims, '核心发现')
    if not clean['timeline']:
        errors.append('至少需要一个有出处的时间线节点')
    for i, event in enumerate(clean['timeline']):
        label = f'时间线 {i + 1}'
        require(event, ('time', 'time_basis', 'actor', 'action', 'observation'), label)
        refs(event.get('source_ids'), sources, label)
    for section in clean['sections']:
        require(section, ('title',), '分析章节')
        blocks = section.get('blocks')
        if not isinstance(blocks, list) or not blocks:
            errors.append('分析章节需要 blocks')
            continue
        for block in blocks:
            if not isinstance(block, dict):
                errors.append('blocks 条目必须是对象')
                continue
            require(block, ('text',), '正文')
            refs(block.get('claim_ids'), claims, '正文', required=True)
            demo = block.get('demo')
            if demo is not None:
                if not isinstance(demo, dict):
                    errors.append('demo必须为对象')
                else:
                    require(demo, ('title', 'poster_file', 'caption', 'source_id', 'verification'), 'demo')
                    if demo.get('source_id') not in sources:
                        errors.append('demo来源不存在')
                    if demo.get('video_url') and not valid_url(demo['video_url']):
                        errors.append('demo视频URL必须为安全http(s)链接')
                    if demo.get('video_url') and demo.get('video_file'):
                        errors.append('demo不能同时指定远程和本地视频')

    for i, metric in enumerate(clean['metrics']):
        label = f'指标 {i + 1}'
        require(metric, ('name', 'unit', 'definition', 'sample', 'method', 'captured_at', 'boundary'), label)
        refs(metric.get('source_ids'), sources, label)
        if not valid_time(metric.get('captured_at')):
            errors.append(label + ': 采集时点必须含时区')
        if metric.get('value') is None:
            require(metric, ('missing_reason',), label)
        elif not isinstance(metric['value'], (int, float)) or isinstance(metric['value'], bool) or not math.isfinite(metric['value']):
            errors.append(label + ': value 只能为有限数值或 null')
        if metric.get('method') != 'source_reported':
            require(metric, ('calculation_file', 'raw_file'), label)
        if metric.get('unit') == '%':
            n, d = metric.get('numerator'), metric.get('denominator')
            if not all(isinstance(x, (int, float)) and not isinstance(x, bool) and math.isfinite(x) for x in (n, d)) or d <= 0 or n < 0 or n > d:
                errors.append(label + ': 比例必须提供有效分子分母')
            elif metric.get('value') is not None and isinstance(metric['value'], (int, float)) and abs(metric['value'] - 100 * n / d) > .11:
                errors.append(label + ': 百分比与分子分母不一致')
    if not clean['lessons']:
        errors.append('至少需要一条带适用条件和代价的机制启发')
    for lesson in clean['lessons']:
        require(lesson, ('mechanism', 'conditions', 'resources', 'cost', 'avoid', 'test'), '迁移机制')
        refs(lesson.get('claim_ids'), claims, '迁移机制')
    for gap in clean['gaps']:
        require(gap, ('item', 'reason', 'impact', 'next_step'), '缺失项')
        if not isinstance(gap.get('requires_user'), bool):
            errors.append('缺失项 requires_user 必须为布尔值')
    return errors, warnings


def validate_files(folder, data):
    errors = []
    for source in data.get('sources', []):
        if local_dataset(source):
            p = (folder / source['url']).resolve()
            if not p.is_relative_to(folder.resolve()) or not p.is_file():
                errors.append('本地计算来源不存在或越界: ' + source['url'])
    for item in data.get('analysis_files', []):
        value = item.get('file')
        if not value or not present(item.get('label')):
            errors.append('数据附件缺少名称或路径')
            continue
        p = (folder / value).resolve()
        if not p.is_relative_to(folder.resolve()) or not p.is_file():
            errors.append('数据附件不存在或越界: ' + value)
    for section in data.get('sections', []):
        for block in section.get('blocks', []):
            demo = block.get('demo')
            if isinstance(demo, dict):
                for key in ('poster_file', 'video_file'):
                    value = demo.get(key)
                    if not value:
                        continue
                    p = (folder / value).resolve()
                    suffixes = ('.png', '.jpg', '.jpeg', '.webp', '.svg') if key == 'poster_file' else ('.mp4', '.webm')
                    if not p.is_relative_to(folder.resolve()) or not p.is_file() or p.suffix.lower() not in suffixes:
                        errors.append('demo文件缺失、类型无效或越界: ' + value)
            figure = block.get('figure')
            if not figure:
                continue
            for key in ('title', 'caption', 'image_file', 'data_file'):
                if not present(figure.get(key)):
                    errors.append('图表缺少 ' + key)
            for key in ('image_file', 'data_file'):
                value = figure.get(key)
                if value:
                    p = (folder / value).resolve()
                    if not p.is_relative_to(folder.resolve()) or not p.is_file():
                        errors.append('图表文件不存在或越界: ' + value)
            if figure.get('image_file') and Path(figure['image_file']).suffix.lower() not in ('.svg', '.png'):
                errors.append('图表仅接受本地 SVG/PNG')
    for metric in data.get('metrics', []):
        for key in ('raw_file', 'calculation_file'):
            if metric.get(key):
                p = (folder / metric[key]).resolve()
                if not p.is_relative_to(folder.resolve()) or not p.is_file():
                    errors.append(f'指标文件不存在或越界: {metric[key]}')
    if data.get('id') != folder.name:
        errors.append('case.id 必须与案例目录名一致')
    return errors


def qa_errors(folder):
    try:
        qa = read_json(folder / 'qa.json')
    except (OSError, ValueError):
        return ['缺少可读取的 qa.json']
    if not isinstance(qa, dict):
        return ['qa.json 必须是对象']
    errors = []
    if qa.get('case_sha256') != digest(folder / 'case.json'):
        errors.append('质量检查尚未绑定当前 case.json SHA-256')
    for key in CHECKS:
        check = qa.get(key, {})
        if not isinstance(check, dict) or check.get('status') != 'passed' or not present(check.get('notes')) or not valid_time(check.get('checked_at')):
            errors.append(f'质量检查 {key} 尚未完成或无具体记录')
    if not (folder / 'research-log.md').is_file():
        errors.append('缺少研究日志')
    return errors


def link(url, label):
    return f'<a href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(label)}</a>'


def paragraph(text):
    return '<p>' + esc(text).replace('\n', '<br>') + '</p>'


def definition(items):
    return '<dl>' + ''.join(f'<dt>{esc(k)}</dt><dd>{esc(v)}</dd>' for k, v in items if v) + '</dl>'


def table(headers, rows):
    return ('<div class="table-wrap"><table><thead><tr>' + ''.join(f'<th>{esc(x)}</th>' for x in headers)
            + '</tr></thead><tbody>' + ''.join('<tr>' + ''.join(f'<td>{x}</td>' for x in row) + '</tr>' for row in rows) + '</tbody></table></div>')


def page(title, subtitle, eyebrow, meta, sections, footer, focused=False):
    appendix_ids = ('claims', 'metrics', 'sources', 'method', 'timeline', 'lessons', 'gaps')
    primary = [x for x in sections if not focused or x[0] not in appendix_ids]
    nav = ''.join(f'<a href="#{esc(sid)}">{esc(label.split(chr(65372), 1)[0] if focused else label)}</a>' for sid, label, content in primary)
    if focused:
        nav += '<a href="#evidence-appendix">证据与方法</a>'
    body = ''
    appendix = ''
    for i, (sid, label, content) in enumerate(sections, 1):
        if sid in appendix_ids:
            item = f'<details class="appendix-details" id="{esc(sid)}"><summary>{esc(label)}</summary>{content}</details>'
            if focused:
                appendix += item
            else:
                body += item
        else:
            body += f'<section class="section" id="{esc(sid)}"><div class="section-number">{i:02d}</div><h2>{esc(label)}</h2>{content}</section>'
    if focused:
        body += '<section class="section" id="evidence-appendix"><h2>证据与方法</h2>' + appendix + '</section>'
    return Template((ROOT / 'templates/report.html').read_text()).substitute(
        title=esc(title), subtitle=esc(subtitle), eyebrow=esc(eyebrow), meta=meta, nav=nav,
        body=body, css=(ROOT / 'templates/report.css').read_text(), footer=esc(footer),
        page_class='focused' if focused else '')


def render(data, draft=False, folder=None):
    sources = {s['id']: s for s in data['sources']}
    claims = {c['id']: c for c in data['claims']}

    def source_links(ids):
        if data.get('citation_style') == 'named':
            return ' · '.join(link(sources[s]['url'], sources[s]['title']) for s in dict.fromkeys(ids))
        if data.get('citation_style') == 'compact':
            return ' · '.join(
                f'<a href="{esc(sources[s]["url"])}" title="{esc(sources[s]["title"])}" target="_blank" rel="noopener noreferrer">[{esc(s)}]</a>'
                for s in dict.fromkeys(ids))
        return ' · '.join(link(sources[s]['url'], f"{s} {sources[s]['title']}") for s in ids)

    def claim_links(ids):
        return ' · '.join(f'<a href="#claim-{esc(cid)}">{esc(cid)} 证据与边界</a>' for cid in ids)

    def evidence_links(claim):
        ids = list(dict.fromkeys(ev['source_id'] for ev in claim.get('evidence', [])))
        return source_links(ids)

    scope = data['scope']
    summary = '<ol class="summary-list">'
    for cid in data['summary_claim_ids']:
        c = claims[cid]
        summary += f'<li><span class="badge {esc(c["kind"])}">{KINDS[c["kind"]]}</span> {esc(c["text"])}<div class="evidence">{evidence_links(c)} · {claim_links([cid])}</div></li>'
    summary += '</ol>'
    if draft:
        summary = '<div class="notice draft"><p>草稿 · 未完成正式发布检查，不作为最终报告。</p></div>' + summary
    summary += '<details class="scope-details"><summary>观察范围与数据说明</summary>' + definition([('分析问题', scope['question']), ('对象与观察窗', scope['object'] + '｜' + scope['window']), ('实际覆盖', scope['coverage']), ('结论边界', scope['limitations'])]) + '</details>'
    sections = [('summary', data.get('summary_title', '核心发现与研究范围'), summary)]
    rows = [[esc(x['time']) + '<br><span class="small">' + esc(x['time_basis']) + '</span>', esc(x['actor']), esc(x['action']), esc(x['observation']), source_links(x['source_ids'])] for x in data['timeline']]
    timeline_section = ('timeline', '完整传播时间线', table(['时间（北京时间）', '主体', '动作', '观察到的反应', '原文'], rows))
    if data.get('timeline_placement') != 'appendix':
        sections.append(timeline_section)
    for i, section in enumerate(data['sections'], 1):
        content = ''
        for b in section['blocks']:
            if b.get('heading'):
                content += '<h3>' + esc(b['heading']) + '</h3>'
            source_ids = list(dict.fromkeys(ev['source_id'] for cid in b['claim_ids'] for ev in claims[cid].get('evidence', [])))
            evidence = f'<p class="evidence">{claim_links(b["claim_ids"])}'
            if source_ids:
                evidence += '<br>原文：' + source_links(source_ids[:4])
                if len(source_ids) > 4:
                    evidence += ' · 完整来源见上方证据链接'
            evidence += '</p>'
            content += ('<p class="lede">' + esc(b['text']) + '</p>' if b.get('lead') else paragraph(b['text']))
            if data.get('evidence_display') == 'collapsed':
                content += '<details class="block-evidence"><summary>查看依据与判断边界</summary>' + evidence + '</details>'
            else:
                content += evidence
            figure = b.get('figure')
            if figure:
                if folder is None:
                    raise ValueError('包含图表的报告需要案例目录')
                image_path = (folder / figure['image_file']).resolve()
                if not image_path.is_relative_to(folder.resolve()):
                    raise ValueError('图表路径越界')
                mime = 'image/svg+xml' if image_path.suffix == '.svg' else 'image/png'
                encoded = base64.b64encode(image_path.read_bytes()).decode('ascii')
                content += '<figure class="research-figure"><h3>' + esc(figure['title']) + '</h3><div class="figure-viewport"><a href="' + esc(figure['image_file']) + '"><img src="data:' + mime + ';base64,' + encoded + '" alt="' + esc(figure['caption']) + '"></a></div><figcaption>' + esc(figure['caption']) + '</figcaption><p class="small">窄屏可横向滑动图表，点击查看大图。<a href="' + esc(figure['data_file']) + '">查看逐条数据 / 图表依据 ↗</a></p></figure>'
            demo = b.get('demo')
            if demo:
                if folder is None:
                    raise ValueError('demo需要案例目录')
                poster_path = (folder / demo['poster_file']).resolve()
                if not poster_path.is_relative_to(folder.resolve()):
                    raise ValueError('demo封面越界')
                mime = {'.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.webp': 'image/webp'}[poster_path.suffix.lower()]
                poster = 'data:' + mime + ';base64,' + base64.b64encode(poster_path.read_bytes()).decode('ascii')
                video = demo.get('video_url') or demo.get('video_file')
                content += '<figure class="demo"><h3>' + esc(demo['title']) + '</h3>'
                if video:
                    content += '<video controls playsinline preload="none" poster="' + poster + '" aria-label="' + esc(demo['title']) + '"><source src="' + esc(video) + '"></video>'
                    content += '<p class="demo-error small" hidden>视频暂时无法加载；可查看封面，或通过下方链接打开原文与视频。</p>'
                else:
                    content += '<img src="' + poster + '" alt="' + esc(demo['title']) + '">'
                content += '<figcaption>' + esc(demo['caption']) + '<p class="small">' + esc(demo['verification']) + ' · ' + source_links([demo['source_id']])
                if video:
                    content += ' · ' + link(video, '单独打开视频')
                content += '</p></figcaption></figure>'
        sections.append((f'analysis-{i}', section['title'], content))
    if data.get('timeline_placement') == 'appendix':
        sections.append(timeline_section)
    if data.get('method_notes'):
        content = ''.join(paragraph(note) for note in data['method_notes'])
        content += '<p class="links">' + ' '.join('<a href="' + esc(item['file']) + '">' + esc(item['label']) + ' ↗</a>' for item in data.get('analysis_files', [])) + '</p>'
        sections.append(('method', '样本与方法：这份报告如何读', content))
    content = ''
    for c in data['claims']:
        confidence = (' · 置信度' + c['confidence']) if c['kind'] == 'inference' else ''
        content += f'<article class="claim" id="claim-{esc(c["id"])}"><div class="claim-head"><h3>{esc(c["id"])} · {esc(c["text"])}</h3><span class="badge {esc(c["kind"])}">{KINDS[c["kind"]]}{confidence}</span></div>'
        for ev in c.get('evidence', []):
            s = sources[ev['source_id']]
            content += f'<blockquote>{esc(ev["excerpt"])}</blockquote><p class="evidence">{link(s["url"], ev["source_id"] + " " + s["title"])} · {esc(ev["locator"])} · {ACCESS[s["access"]]}</p>'
        content += definition([('推理与机制', c.get('reasoning')), ('最强替代解释及如何区分', c.get('alternatives')), ('改变判断的证据', c.get('falsifier')), ('未知原因', c.get('reason')), ('判断边界', c['boundary'])]) + '</article>'
    sections.append(('claims', '结论与证据核验', content))
    content = ''
    for lesson in data['lessons']:
        content += '<article class="lesson"><h3>' + esc(lesson['mechanism']) + '</h3>' + definition([
            ('适用条件', lesson['conditions']), ('资源要求', lesson['resources']), ('代价与副作用', lesson['cost']), ('何时不照搬', lesson['avoid']), ('可先做的验证', lesson['test'])]) + f'<p class="evidence">{claim_links(lesson["claim_ids"])}</p></article>'
    sections.append(('lessons', '可借鉴的机制与代价', content))
    if data['metrics']:
        content = ''
        for m in data['metrics']:
            value = '未知：' + m['missing_reason'] if m.get('value') is None else str(m['value']) + ' ' + m['unit']
            content += '<article class="claim"><h3>' + esc(m['name'] + ' · ' + value) + '</h3>' + definition([
                ('定义与样本', m['definition'] + '；' + m['sample']), ('方法', m['method']), ('采集时点', m['captured_at']),
                ('分子 / 分母', f"{m.get('numerator')} / {m.get('denominator')}" if m.get('denominator') is not None else ''),
                ('原始文件', m.get('raw_file')), ('计算文件', m.get('calculation_file')), ('边界', m['boundary'])]) + '<p class="evidence">' + source_links(m['source_ids']) + '</p></article>'
        sections.append(('metrics', '数据口径与可复算记录', content))
    if data['gaps']:
        rows = [[esc(g['item']), esc(g['reason']), esc(g['impact']), esc(g['next_step']) + ('<br><strong>需要用户补充</strong>' if g['requires_user'] else '')] for g in data['gaps']]
        sections.append(('gaps', '尚不能回答什么', table(['缺失项', '原因', '对结论的影响', '可行补齐方式'], rows)))
    content = ''
    for s in data['sources']:
        content += f'<article class="source" id="source-{esc(s["id"])}"><h3>{esc(s["id"])} · {link(s["url"], s["title"])}</h3>'
        content += paragraph(f"{s['publisher']}｜{s['kind']}｜来源族：{s['family']}｜{ACCESS[s['access']]}")
        content += paragraph(f"原始发布：{s['published_at']}；采集：{s['captured_at']}") + paragraph(s['note']) + '</article>'
    sections.append(('sources', '来源台账', content))
    meta = '<div class="meta"><span>观察窗 ' + esc(scope['window']) + '</span><span>截止 ' + esc(data['as_of']) + '</span><span>' + esc(data['revision']) + ' · Asia/Shanghai</span></div>'
    return page(data['title'], data.get('subtitle', ''), '传播研究 / ' + ('DRAFT' if draft else 'CASE STUDY'), meta, sections, data['revision'] + '｜' + data['change_note'], focused=data.get('reading_mode') == 'focused')


def initialize(slug, title):
    if not re.fullmatch(r'\d{4}-\d{2}-\d{2}-[a-zA-Z0-9][a-zA-Z0-9_-]*', slug):
        raise ValueError('案例名格式为 YYYY-MM-DD-slug')
    folder = case_dir('cases/' + slug)
    folder.mkdir(parents=True, exist_ok=False)
    (folder / 'raw').mkdir()
    data = copy.deepcopy(read_json(ROOT / 'templates/case.json'))
    data.update(id=slug, title=title)
    write_json(folder / 'case.json', data)
    qa = {'case_sha256': '', **{k: {'status': 'pending', 'checked_at': '', 'notes': ''} for k in CHECKS}}
    write_json(folder / 'qa.json', qa)
    (folder / 'research-log.md').write_text('# 研究日志\n\n## 范围与消歧\n\n## 检索记录\n\n时间｜工具｜查询词/URL｜窗口/分页｜所得材料｜未覆盖/失败原因\n\n## 来源读取与源族判断\n\n## 样本与计算（有数据时）\n\n## 关键推断、反证与修改\n\n## 交付版本\n', encoding='utf-8')
    return folder


def build(folder, draft=False):
    data = read_json(folder / 'case.json')
    errors, warnings = validate(data)
    if not errors:
        errors += validate_files(folder, data)
    if errors:
        raise ValueError('\n'.join(errors))
    if not draft:
        if data.get('status') != 'ready':
            errors.append('正式生成需要 status=ready')
        errors += qa_errors(folder)
    if errors:
        raise ValueError('\n'.join(errors))
    output = folder / ('report.draft.html' if draft else 'report.html')
    rendered = render(data, draft, folder)
    if not draft and output.exists() and output.read_text() != rendered:
        stamp = datetime.now(ZoneInfo('Asia/Shanghai')).strftime('%Y%m%dT%H%M%S%f')
        archive = folder / 'versions' / stamp
        archive.mkdir(parents=True)
        shutil.copy2(output, archive / 'report.html')
        for old in ('published-case.json', 'published-qa.json', 'publication.json'):
            if (folder / old).exists():
                shutil.copy2(folder / old, archive / old)
    output.write_text(rendered, encoding='utf-8')
    if not draft:
        shutil.copy2(folder / 'case.json', folder / 'published-case.json')
        shutil.copy2(folder / 'qa.json', folder / 'published-qa.json')
        write_json(folder / 'publication.json', {'case_sha256': digest(folder / 'case.json'), 'html_sha256': digest(output), 'qa_sha256': digest(folder / 'qa.json'), 'published_at': datetime.now(ZoneInfo('Asia/Shanghai')).isoformat(timespec='seconds')})
        make_index()
    return output, warnings


def make_index():
    entries = []
    for folder in sorted((ROOT / 'cases').glob('*'), reverse=True):
        if not folder.is_dir() or not (folder / 'publication.json').exists():
            continue
        try:
            d, p = read_json(folder / 'case.json'), read_json(folder / 'publication.json')
            if d.get('status') != 'ready' or p['case_sha256'] != digest(folder / 'case.json') or p['html_sha256'] != digest(folder / 'report.html') or p['qa_sha256'] != digest(folder / 'qa.json') or qa_errors(folder):
                continue
            href = 'cases/' + quote(folder.name) + '/report.html'
            entries.append(f'<article class="catalog-item"><a href="{href}">{esc(d["title"])}</a>{paragraph(d.get("subtitle", ""))}<p class="small">{esc(d["scope"]["window"])} · {esc(d["revision"])}</p></article>')
        except (OSError, ValueError, KeyError, TypeError):
            continue
    cases = ''.join(entries) or '<div class="notice"><p>项目已就绪，尚无新案例。下一次给一个传播事件，即可开始研究并在这里归档最终报告。</p></div>'
    sections = [
        ('start', '从一个传播事件开始', '<p class="lead">看清对方的选择，积累自己的判断。</p><p>给一个名称、链接或事件描述。研究将自行完成检索、时间线、策略反推、核验与 HTML 报告。</p><p class="links"><a href="启动说明.html">阅读项目约定 ↗</a><a href="README.md">文件与工具说明 ↗</a></p>'),
        ('cases', f'案例归档 · {len(entries):02d}', cases),
        ('reference', '报告阅读方式', '<p>正文按意图、设计、执行、验证四层给出结论；数据和图表直接解释传播意义。具体原文、口径与反证保留在附录。</p>'),
        ('method', '意图—设计—执行', '<p>主文三层连接传播目标、关键选择、实际扩散与效果证据，验证融入对应判断与附录。以声量、信息传递、渠道、时序、路径和反馈呈现结果；区分事实、信源主张、推断和未知，交代替代解释与边界。</p><p class="links"><a href="docs/research-playbook.md">研究方法</a><a href="docs/source-access.md">数据与来源边界</a><a href="AGENTS.md">长期工作规则</a></p>')]
    output = ROOT / 'index.html'
    output.write_text(page('向外看', '传播研究项目 · 从公开动作反推关键选择，以证据约束结论。', '持续积累 / COMMUNICATIONS RESEARCH', '<div class="meta"><span>建立于 2026-10-23</span><span>按需研究 · HTML 交付</span></div>', sections, '项目入口｜正式案例通过结构检查并记录人工核验后进入目录'), encoding='utf-8')
    return output


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest='command', required=True)
    init = commands.add_parser('init'); init.add_argument('slug'); init.add_argument('--title', required=True)
    for command in ('validate', 'build'):
        sub = commands.add_parser(command); sub.add_argument('case')
        if command == 'build':
            sub.add_argument('--draft', action='store_true')
    commands.add_parser('index')
    args = parser.parse_args()
    try:
        if args.command == 'init':
            print(initialize(args.slug, args.title))
        elif args.command == 'index':
            print(make_index())
        else:
            folder = case_dir(args.case)
            if args.command == 'build':
                output, warnings = build(folder, args.draft)
                print(output)
            else:
                data = read_json(folder / 'case.json')
                errors, warnings = validate(data)
                if not errors:
                    errors += validate_files(folder, data)
                for error in errors:
                    print('ERROR: ' + error)
                if errors:
                    return 1
                print('结构检查通过；尚不代表原文、数字或因果结论已核验。')
            for warning in warnings:
                print('WARN: ' + warning)
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
