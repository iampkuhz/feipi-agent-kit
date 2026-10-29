#!/usr/bin/env python3
"""对已人工验收的真实图包做缓存、篡改与失败路径验收。"""
import argparse
import copy
import json
import shutil
import sys
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from model import ROOT,load
from package import verify,artifact_hashes
from run import run
from review_package import review

p=argparse.ArgumentParser();p.add_argument('accepted_package');p.add_argument('original_brief');p.add_argument('output');a=p.parse_args()
source=Path(a.accepted_package).resolve();output=Path(a.output).resolve();output.mkdir(parents=True,exist_ok=True)
results=[]
def passed(name):
 results.append(name);print('PASS '+name,flush=True)

baseline=verify(source);before=artifact_hashes(source)
r=run(a.original_brief,source,reuse=True)
assert r['final_status']=='success' and r['last_run_counters']=={'render_calls':0,'verifier_calls':2,'cache_hits':1}
assert r['timings']==baseline['timings'] and artifact_hashes(source)==before
passed('verified-cache-no-render')

for field in ('source','svg','png','geometry','metrics','timing','counter','review','path','identity'):
 dest=output/('tamper-'+field);shutil.copytree(source,dest)
 report=json.loads((dest/'validation.json').read_text())
 if field=='source':(dest/'diagram.mmd').write_text('flowchart TB\n Evil[Injected]\n')
 elif field=='svg':(dest/'diagram.svg').write_text('<svg xmlns="http://www.w3.org/2000/svg"><text>Wrong</text></svg>')
 elif field=='png':(dest/'diagram.png').write_bytes(b'not an image')
 elif field=='geometry':
  ev=json.loads((dest/'render-evidence.json').read_text());ev['texts'][0]['rect'][0]=99999
  (dest/'render-evidence.json').write_text(json.dumps(ev));report['artifacts']=artifact_hashes(dest)
 elif field=='metrics':report['metrics']['nodes']+=1
 elif field=='timing':report['last_run_timings']['render_ms']=-1
 elif field=='counter':report['last_run_counters']['render_calls']=10
 elif field=='review':report['visual_review']['status']='pending'
 elif field=='path':report['artifacts']['../outside']='0'*64
 elif field=='identity':report['input_fingerprint']='0'*64
 (dest/'validation.json').write_text(json.dumps(report))
 try:verify(dest)
 except Exception:pass
 else:raise AssertionError(field+' 未拦截')
 with patch('run.invoke',side_effect=AssertionError('损坏缓存不能渲染')):
  r=run(a.original_brief,dest,reuse=True)
 assert r['final_status']=='blocked'
 passed('reject-'+field)

# 视觉拒绝与缺少通用语义复核都不能被当作完成。
dest=output/'review-failed';shutil.copytree(source,dest)
review(dest,'fail','门禁测试：模拟视觉检查拒绝')
try:verify(dest)
except Exception:pass
else:raise AssertionError('失败视觉结论被忽略')
passed('visual-rejection-blocks-success')
dest=output/'missing-semantic';shutil.copytree(source.parent/'native-classDiagram',dest)
r=json.loads((dest/'validation.json').read_text());r['final_status']='review_required';r['visual_review']={'status':'pending'}
(dest/'validation.json').write_text(json.dumps(r))
try:review(dest,'pass','门禁测试：尚未记录语义复核')
except Exception:pass
else:raise AssertionError('未核对语义也能通过')
passed('fallback-requires-semantic-review')

# 改动布局触发一次新的渲染，不能复用旧 SVG。
dest=output/'changed';shutil.copytree(source,dest)
b=load(a.original_brief);b['layout']['direction']='LR'
brief=output/'changed.json';brief.write_text(json.dumps(b,ensure_ascii=False))
r=run(brief,dest,reuse=True)
assert r['final_status']=='review_required' and r['attempt_index']==2 and r['last_run_counters']['render_calls']==1,r
assert r['artifacts']['diagram.svg']!=before['diagram.svg']
passed('changed-direction-renders-again')

# 原生思维导图的间距在本地布局调整中有确定的几何效果。
dest=output/'changed-spacing';shutil.copytree(source.parent/'mindmap-balanced',dest)
previous=verify(dest)
b=load(source.parent/'inputs/mindmap-balanced.json');b['layout']['spacing']=100
brief=output/'spacing.json';brief.write_text(json.dumps(b,ensure_ascii=False))
r=run(brief,dest,reuse=True)
assert r['final_status']=='review_required' and r['attempt_index']==2,r
assert r['artifacts']['diagram.svg']!=previous['artifacts']['diagram.svg']
passed('native-mindmap-spacing-changes-geometry')

# 真正缺少浏览器时保留源码并且不消耗图的次数。
r=run(a.original_brief,output/'missing-browser',browser=output/'no-browser')
assert r['final_status']=='blocked' and r['failure_class']=='renderer' and r['attempt_index']==0
assert (output/'missing-browser/diagram.mmd').exists()
passed('missing-browser-blocked-with-source')

# 真语法错误、未修改重复调用、一次修复与次数耗尽。
b={'diagram_id':'syntax','diagram_type':'generic','title':'错误语法验收','summary':'验证真实 Mermaid 失败与修复次数','syntax':'flowchart','expected_text':['Alpha'],'layout':{'direction':'TB'}}
brief=output/'syntax.json';brief.write_text(json.dumps(b))
mmd=output/'syntax.mmd';mmd.write_text('flowchart TB\n Alpha[broken\n')
dest=output/'syntax';r=run(brief,dest,mmd)
assert r['failure_class']=='render' and r['attempt_index']==1 and not (dest/'diagram.svg').exists(),r
passed('real-syntax-error')
for _ in range(3):
 with patch('run.invoke',side_effect=AssertionError('不能重试未修改输入')):r=run(brief,dest,mmd)
 assert r['failure_class']=='retry_limit' and r['attempt_index']==1
passed('unchanged-failure-never-retries')
mmd.write_text('flowchart TB\n Alpha["Alpha"]\n')
r=run(brief,dest,mmd);assert r['final_status']=='review_required' and r['attempt_index']==2,r
passed('one-targeted-repair')
b['summary']='图意再次变化';brief.write_text(json.dumps(b))
with patch('run.invoke',side_effect=AssertionError('不能执行第三次渲染')):r=run(brief,dest,mmd)
assert r['failure_class']=='retry_limit' and r['attempt_index']==2
passed('third-render-rejected')

# 参数通过 argv 传递，路径中的空格/引号不会触发 shell 解析。
r=run(a.original_brief,output/"quote's path")
assert r['final_status']=='review_required',r
passed('quoted-path-real-render')
(output/'results.json').write_text(json.dumps({'passed':results,'count':len(results)},ensure_ascii=False,indent=2)+'\n')
