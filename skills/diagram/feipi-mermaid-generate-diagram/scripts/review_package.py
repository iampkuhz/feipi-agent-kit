#!/usr/bin/env python3
"""在真实查看 PNG/SVG 后记录视觉结论；不以声明替代图面检查。"""
import argparse
import json
from pathlib import Path
from model import TYPES, require
from package import verify


def review(folder, decision, notes, semantic=False):
    folder = Path(folder)
    r = verify(folder, allow_pending=True)
    require(notes.strip(), '必须记录具体视觉检查结论')
    if r['diagram_type'] not in TYPES and decision == 'pass':
        require(semantic, '通用图型必须核对节点、关系与用户需求，再传 --semantic-reviewed')
    r['visual_review'] = {'status':'passed' if decision == 'pass' else 'failed', 'notes':notes,
                          'svg_sha256':r['artifacts']['diagram.svg'], 'semantic_review':'passed' if semantic else 'typed'}
    r['final_status'] = 'success' if decision == 'pass' else 'blocked'
    if decision != 'pass':
        r.update(last_render_status='failed',failure_class='visual_review',repairable=False,issues=[notes])
    (folder/'validation.json').write_text(json.dumps(r,ensure_ascii=False,indent=2)+'\n')
    if decision == 'pass':
        verify(folder)
    return r


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('package')
    p.add_argument('--decision',choices=['pass','fail'],required=True)
    p.add_argument('--notes',required=True)
    p.add_argument('--semantic-reviewed',action='store_true')
    a = p.parse_args()
    try:
        r = review(a.package,a.decision,a.notes,a.semantic_reviewed)
        print(json.dumps({'final_status':r['final_status']},ensure_ascii=False))
    except Exception as e:
        p.exit(1,str(e)+'\n')
