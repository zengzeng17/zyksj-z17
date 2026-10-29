#!/usr/bin/env python3
"""Stage a public static report by allowlist; never copy raw/ or credentials."""
import argparse,copy,csv,hashlib,html,importlib.util,json,re,shutil
from collections import Counter
from pathlib import Path
from html.parser import HTMLParser

def write_json(p,d):p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def stage(project,case,out,origin=''):
 project=project.resolve();case=case.resolve();out=out.resolve()
 if out==case or out in case.parents:raise ValueError('Public staging must be separate from the evidence case')
 spec=importlib.util.spec_from_file_location('report_author',project/'scripts/research.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
 d=json.loads((case/'case.json').read_text());errors,warnings=m.validate(d);errors+=m.validate_files(case,d)+m.qa_errors(case)
 if errors:raise ValueError('Only a validated, QA-bound case can be staged: '+'; '.join(errors))
 out.mkdir(parents=True,exist_ok=True)
 if any(out.iterdir()):raise ValueError('Use an empty public staging directory; preserve an existing release')
 d=copy.deepcopy(d);case_hash=hashlib.sha256((case/'case.json').read_bytes()).hexdigest()
 def note(v):
  # Keep interpretation boundaries; omit internal provenance file names.
  v=re.sub(r'(?:原始响应|原始文件)[:：][^。；]*[。；]?','',v)
  v=re.sub(r'raw/[A-Za-z0-9_.\-/]+','',v)
  v=re.sub(r'(?<![A-Za-z0-9])(?:[A-Za-z0-9_-]+\.(?:py|jsonl?|csv|txt|html|webp|jpg))(?:\s*与\s*txt)?','',v)
  return v.strip('；。 ，')
 for s in d['sources']:
  s['note']=note(s['note'])
  if s['kind']=='本次采集计算':s['note']='本报告的公开样本索引或标签记录；用于复核本次计数，不代表平台全量。'
  if '图像未做原始文件签名认证' in s['note'] or '截图转引' in s['kind']:
   s['note']='已读正文及公开转引截图。图片文字可读；原始文件、签发、授权与实际执行未经独立认证。'
 for c in d['claims']:
  for ev in c['evidence']:
   if '统计依据' in ev['excerpt']:ev['excerpt']='本报告公开附件中的逐条样本、发布时间或标签明细支持相应统计；分母与口径见图注。'
   ev['locator']=note(ev['locator']) or '所列来源相应段落'
 d['method_notes']=[
  '观察窗口、截止时点和各渠道读取深度见报告范围及图注。只按内容发布时间纳入；互动是采集时的公开快照，不能相加为独立触达。',
  '计数单位为平台内容ID，跨库同一内容去重；评论另列。转载可以计为一次发布，但同源转载不构成多个独立证据。渠道采集强度不同，不据数量推算全网份额。',
  '只取得日期或区间时不补时分秒；不完整日不与完整日直接比较。样本发布日期分布不能直接当成全网热度或半衰期。',
  '重要判断区分事实、信源主张、推断和未知；官方主张不直接等同能力与公众认可。原始帖子、明确引用关系和具体任务是主要判断依据。',
  '正文信息提及采用所列词表；多标签可重叠，提及不等于赞同、受众记忆或满意度。完整正文未取得的内容不用于全文态度判断。',
  '公开附件提供样本索引、计数和标签明细；原文通过原始链接查阅。测试条件、利益关系与重要结论边界保留在来源和结论附录。']
 d['analysis_files']=[{'label':'筛选浏览样本','file':'samples.html'},{'label':'样本索引CSV','file':'samples.csv'},{'label':'各渠道计数与读取深度','file':'statistics.json'},{'label':'信息标签与词表','file':'message-coding.json'}]
 for metric in d['metrics']:metric.update(raw_file='samples.csv',calculation_file='')
 d['change_note']='公开分享版；结论、观测截止与研究版一致。'
 for section in d['sections']:
  for b in section['blocks']:
   demo=b.get('demo')
   if demo:
    for key in ['poster_file','video_file']:
     if not demo.get(key):continue
     p=(case/demo[key]).resolve()
     if not p.is_relative_to(case) or not p.is_file():raise ValueError('Missing/unsafe demo file')
     q=out/demo[key];q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
   f=b.get('figure')
   if not f:continue
   for key in ['image_file','data_file']:
    p=(case/f[key]).resolve()
    if not p.is_relative_to(case) or not p.is_file():raise ValueError('Missing/unsafe figure')
    q=out/f[key];q.parent.mkdir(parents=True,exist_ok=True);shutil.copy2(p,q)
 have_samples=(case/'samples.json').is_file()
 a=json.loads((case/'samples.json').read_text()) if have_samples else [];meta=[]
 for x in a:
  row={k:x.get(k) for k in ['sample_id','platform','url','author','published_at','published_interval','time_precision','title','depth']}
  row['body_characters']=len(x.get('text',''));row['text']='读取深度：'+str(x['depth'])+'。已取得文字长度：'+str(row['body_characters'])+'字符。原文请点击标题访问。';meta.append(row)
 if have_samples:
  write_json(out/'samples.json',meta)
  with (out/'samples.csv').open('w',encoding='utf-8-sig',newline='') as f:
   fields=[k for k in meta[0] if k!='text'] if meta else ['sample_id','platform','url','published_at','depth']
   w=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore');w.writeheader();w.writerows(meta)
  if (case/'samples.html').is_file():
   viewer=(case/'samples.html').read_text();payload=json.dumps(meta,ensure_ascii=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
   viewer=re.sub(r'(<script type="application/json" id="data">).*?(</script>)',lambda ma:ma[1]+payload+ma[2],viewer,flags=re.S)
   viewer=viewer.replace('查看读取记录与原始文件索引','查看读取说明').replace("+'\\n原始文件：'+(x.raw_files||[]).join(', ')",'')
  else:
   rows=''.join('<p>'+html.escape(str(x['platform']))+' · <a href="'+html.escape(str(x['url']),quote=True)+'">'+html.escape(str(x['title'] or x['sample_id']))+'</a></p>' for x in meta)
   viewer='<meta charset="utf-8"><a href="index.html">返回报告</a><h1>公开样本索引</h1>'+rows
  (out/'samples.html').write_text(viewer)
 if (case/'statistics.json').is_file():write_json(out/'statistics.json',json.loads((case/'statistics.json').read_text()))
 if (case/'message-coding.json').is_file():
  coding=json.loads((case/'message-coding.json').read_text());coding['rows']=[{k:v for k,v in r.items() if k in ['sample_id','label','match','url']} for r in coding['rows']];write_json(out/'message-coding.json',coding)
 d['analysis_files']=[x for x in d['analysis_files'] if (out/x['file']).is_file()]
 if not have_samples:
  d['method_notes']=[x for x in d['method_notes'] if '词表' not in x and '公开附件' not in x]
  d['method_notes'].append('本案未形成可公开的定量样本表，采用有具体来源的定性证据，不补造数量或比例。')
  for metric in d['metrics']:metric.update(raw_file='',calculation_file='')
 page=m.render(d,folder=case)
 if origin:
  page=page.replace('</head>','<link rel="canonical" href="'+html.escape(origin,quote=True)+'/"><meta property="og:title" content="'+html.escape(d['title'],quote=True)+'"><meta property="og:description" content="'+html.escape(d['subtitle'],quote=True)+'"></head>')
 (out/'index.html').write_text(page);(out/'report.html').write_text(page)
 # Only generated allowlisted files enter the deployment, never a recursive case copy.
 forbidden=['/Users/','TIKHUB_API_KEY','REDFOX_API_KEY','redfox.env','balance-start','balance-end','calls.jsonl']
 for p in out.rglob('*'):
  if p.is_file() and p.suffix in ['.html','.json','.svg','.csv']:
   s=p.read_text(encoding='utf-8-sig')
   bad=[x for x in forbidden if x in s]
   if bad:raise ValueError('Private material in public file '+p.name+': '+','.join(bad))
 class Links(HTMLParser):
  def __init__(self):super().__init__();self.links=[]
  def handle_starttag(self,t,a):
   for k,v in a:
    if k in ['href','src'] and v and not re.match(r'^(?:https?:|data:|#|mailto:)',v):self.links.append(v)
 for p in out.glob('*.html'):
  pa=Links();pa.feed(p.read_text())
  for u in pa.links:
   target=(p.parent/u.split('#')[0].split('?')[0]).resolve()
   if not target.is_relative_to(out) or not target.is_file():raise ValueError('Broken public local link '+u)
 manifest={'case_id':d['id'],'revision':d['revision'],'as_of':d['as_of'],'source_case_sha256':case_hash,'sample_count':len(meta) if have_samples else None,'channel_counts':dict(Counter(x['platform'] for x in meta)) if have_samples else None,'files':{str(p.relative_to(out)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(out.rglob('*')) if p.is_file()},'private_records_included':False}
 write_json(out/'public-manifest.json',manifest);return manifest
if __name__=='__main__':
 p=argparse.ArgumentParser(description=__doc__);p.add_argument('--project',type=Path,required=True);p.add_argument('--case',type=Path,required=True);p.add_argument('--output',type=Path,required=True);p.add_argument('--origin',default='');a=p.parse_args();r=stage(a.project,a.case,a.output,a.origin);print(json.dumps({'sample_count':r['sample_count'],'files':len(r['files']),'private_records_included':False}))
