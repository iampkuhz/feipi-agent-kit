#!/usr/bin/env python3
"""唯一业务入口：验证 brief、生成/检查源码、渲染并冻结可复核图包。"""
import argparse
import copy
import fcntl
import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

from model import ROOT, TYPES, Invalid, check_source, check_visible_text, generate, fingerprint, load, require, safe_relative, sha, validate
from package import CONTRACT, artifact_hashes, contract_hash, layout_issues, verify


def write(path, data):
    temp = path.with_suffix(path.suffix+'.tmp')
    temp.write_text(json.dumps(data,ensure_ascii=False,indent=2)+'\n')
    temp.replace(path)


def invoke(args, timeout=65):
    proc = subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,start_new_session=True)
    try:
        stdout,stderr = proc.communicate(timeout=timeout)
    except subprocess.TimeoutExpired:
        os.killpg(proc.pid,signal.SIGTERM)
        proc.communicate()
        raise Invalid('本地渲染超过 65 秒，已终止本次启动的进程组')
    if proc.returncode:
        raise Invalid((stderr or stdout)[-2000:])
    return json.loads(stdout.strip().splitlines()[-1])


def explain(b):
    lines = ['# '+b['title'],'',b['summary'],'']
    if b['diagram_type'] in ('architecture','component','deployment','activity'):
        lines += ['## 关系说明','']
        lines += [f"- {e['id']}：{e['from']} → {e['to']}；{e['description']}" for e in b['edges']]
    if b['diagram_type'] == 'deployment':
        lines += ['', '## 边界触发', '', *[f'- {k}：{v}' for k,v in b['boundary_triggers'].items()]]
    if b['diagram_type'] == 'mindmap':
        lines += ['', '布局：'+b['layout']['direction']+'；均衡用原生 mindmap，定向用 flowchart。']
    if b['diagram_type'] not in TYPES:
        lines += ['', '通用图型：仅验证语法、指定文字与图面；节点及关系语义需人工复核。']
    return '\n'.join(lines)+'\n'


def run(brief_path, folder, diagram=None, reuse=False, browser=None):
    start = time.monotonic()
    folder = Path(folder).absolute()
    require(not folder.is_symlink(), '输出目录不能是符号链接')
    folder = folder.resolve()
    folder.mkdir(parents=True,exist_ok=True)
    owned = {'validation.json','.lock', 'brief.json','diagram.mmd','diagram.svg','diagram.png','render-evidence.json','explanation.md','evidence'}
    require(all(p.name in owned for p in folder.iterdir()), '输出目录含不属于图包的文件，请使用独立目录')
    require(all(not p.is_symlink() for p in folder.iterdir()), '图包不能含符号链接')
    if (folder/'evidence').exists():
        require((folder/'evidence').is_dir() and all(p.name == 'overview.json' and not p.is_symlink() for p in (folder/'evidence').iterdir()), 'evidence 含未知文件或符号链接')
    with (folder/'.lock').open('w') as lock:
        try:
            fcntl.flock(lock,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Invalid('此图包正在被另一进程处理')
        return locked_run(Path(brief_path).resolve(),folder,diagram,reuse,browser,start)


def locked_run(brief_path,folder,diagram,reuse,browser,start):
    report_path = folder/'validation.json'
    old = json.loads(report_path.read_text()) if report_path.exists() else {}
    attempt = old.get('attempt_index',0)
    require(type(attempt) is int and 0 <= attempt <= 2, '历史渲染计数无效')
    render_ms = 0
    checks = {'brief':'pending','coverage':'pending','render':'pending','layout':'pending'}
    report = {'contract_version':CONTRACT,'contract_hash':contract_hash(),'final_status':'blocked',
              'failure_class':'brief','repairable':False,'issues':[], 'checks':checks,
              'attempt_index':attempt,'max_render_attempts':2,'attempts_remaining':2-attempt,
              'visual_review':{'status':'pending'},'artifacts':{},
              'last_render_fingerprint':old.get('last_render_fingerprint'),
              'last_render_status':old.get('last_render_status')}
    stage = 'brief'
    try:
        b = validate(load(brief_path),brief_path.parent)
        report.update(diagram_id=b['diagram_id'],diagram_type=b['diagram_type'])
        if old:
            require(old.get('diagram_id',b['diagram_id']) == b['diagram_id'], '不能用其他 diagram_id 重置当前图包')
        checks['brief']='passed'
        stage = 'coverage'
        source = Path(diagram).read_text() if diagram else generate(b)
        metrics = check_source(b,source)
        checks['coverage']='passed'
        parent = b.get('parent_ref')
        identity = fingerprint(b,source,report['contract_hash'])
        report.update(input_fingerprint=identity,source_sha256=sha(source.encode()),metrics=metrics)
        if reuse and old.get('input_fingerprint') == identity and old.get('final_status') == 'success':
            stage = 'contract'
            verify(folder)
            elapsed = (time.monotonic()-start)*1000
            old['last_run_timings']={'total_ms':elapsed,'static_ms':elapsed,'render_ms':0}
            old['last_run_counters']={'render_calls':0,'verifier_calls':2,'cache_hits':1}
            write(report_path,old)
            verify(folder)
            return old
        stage = 'retry_limit'
        require(attempt < 2, '已达到每图两次渲染上限；保留失败图包，不通过换目录重复尝试')
        if old.get('last_render_status') in ('started','failed'):
            require(old.get('last_render_fingerprint') != identity, '失败输入未修改，不重复渲染')
        # 先完成依赖/浏览器预检，不消耗图的渲染次数。
        stage = 'renderer'
        cmd = ['node',str(ROOT/'scripts/render.mjs')]
        if browser:
            cmd += ['--browser',str(Path(browser).resolve())]
        # 所有输入读完再覆盖包内源文件，支持已有包内的定点修改。
        packaged = copy.deepcopy(b)
        parent_bytes = safe_relative(brief_path.parent,parent['path']).read_bytes() if parent else None
        for name in ('diagram.svg','diagram.png','render-evidence.json'):
            (folder/name).unlink(missing_ok=True)
        if parent:
            (folder/'evidence').mkdir(exist_ok=True)
            (folder/'evidence/overview.json').write_bytes(parent_bytes)
            packaged['parent_ref']['path']='evidence/overview.json'
        elif (folder/'evidence/overview.json').exists():
            (folder/'evidence/overview.json').unlink()
        write(folder/'brief.json',packaged)
        (folder/'diagram.mmd').write_text(source)
        (folder/'explanation.md').write_text(explain(b))
        ready = invoke(cmd+['--check'],30)
        report['renderer']=ready['renderer']
        attempt += 1
        report.update(attempt_index=attempt,attempts_remaining=2-attempt)
        stage='render'
        # 渲染前持久化计数，中断也不能复位次数。
        report.update(failure_class=stage,issues=['渲染中断或尚未完成'],last_render_fingerprint=identity,last_render_status='started')
        write(report_path,report)
        render_start=time.monotonic()
        try:
            rendered=invoke(cmd+['--source',str(folder/'diagram.mmd'),'--brief',str(folder/'brief.json'),'--out-dir',str(folder)])
        finally:
            render_ms=(time.monotonic()-render_start)*1000
        report['renderer']=rendered['renderer']
        checks['render']='passed'
        stage='layout'
        evidence=json.loads((folder/'render-evidence.json').read_text())
        check_visible_text(b,evidence)
        issues=layout_issues(evidence)
        require(not issues, json.dumps(issues,ensure_ascii=False))
        checks['layout']='passed'
        report.update(last_render_status='passed',final_status='review_required',failure_class=None,repairable=False,issues=[],artifacts=artifact_hashes(folder))
        elapsed=(time.monotonic()-start)*1000
        report['timings']={'total_ms':elapsed,'render_ms':render_ms,'static_ms':elapsed-render_ms}
        report['last_run_timings']=dict(report['timings'])
        report['counters']={'render_calls':1,'verifier_calls':1,'cache_hits':0}
        report['last_run_counters']=dict(report['counters'])
        write(report_path,report)
        stage='contract'
        verify(folder,allow_pending=True)
        return report
    except Exception as exc:
        if stage in ('render','layout','contract') and report.get('last_render_status') == 'started':
            report['last_render_status']='failed'
        report.update(final_status='blocked',failure_class=stage,repairable=stage in ('coverage','render','layout') and attempt < 2,
                      issues=[str(exc)],attempt_index=attempt,attempts_remaining=2-attempt)
        checks[stage if stage in checks else 'render']='failed'
        # 失败永不附带可交付旧图，避免调用方误用成功历史。
        for name in ('diagram.svg','diagram.png','render-evidence.json'):
            (folder/name).unlink(missing_ok=True)
        report['artifacts']={}
        write(report_path,report)
        return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--brief',required=True)
    parser.add_argument('--out-dir',required=True)
    parser.add_argument('--diagram')
    parser.add_argument('--reuse',action='store_true')
    parser.add_argument('--browser',help='已安装 Chrome/Chromium 可执行文件路径')
    args=parser.parse_args()
    try:
        result=run(args.brief,args.out_dir,args.diagram,args.reuse,args.browser)
        print(json.dumps({'final_status':result['final_status'],'failure_class':result['failure_class'],
              'issues':result['issues'],'attempt_index':result['attempt_index'],
              'paths':{'package':str(Path(args.out_dir).resolve()),'preview':str(Path(args.out_dir).resolve()/'diagram.png')}},ensure_ascii=False))
        sys.exit(1 if result['final_status']=='blocked' else 0)
    except Exception as exc:
        parser.exit(1,str(exc)+'\n')
