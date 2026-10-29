#!/usr/bin/env python3
"""真实渲染矩阵：技术检查完成后保留 pending，留给 Agent 实际看图。"""
import argparse
import copy
import json
import sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from model import ROOT,TYPES,load,sha,generate,fingerprint
from run import run
from package import verify,contract_hash

# 每个已列入通用 schema 的语法至少有一个实际渲染用例。
NATIVE = {
 'flowchart':('flowchart TB\n A[Alpha] --> B[Beta]\n',['Alpha','Beta']),
 'graph':('graph LR\n A[Alpha] --> B[Beta]\n',['Alpha','Beta']),
 'sequenceDiagram':('sequenceDiagram\n participant Alice\n participant Bob\n Alice->>Bob: Hello\n',['Alice','Bob','Hello']),
 'mindmap':('mindmap\n root[Topic]\n  a[Alpha]\n  b[Beta]\n',['Topic','Alpha','Beta']),
 'classDiagram':('classDiagram\n class Order {\n +submit()\n }\n class Payment\n Order --> Payment\n',['Order','Payment','submit']),
 'stateDiagram-v2':('stateDiagram-v2\n [*] --> Idle\n Idle --> Active: start\n Active --> [*]\n',['Idle','Active','start']),
 'erDiagram':('erDiagram\n CUSTOMER ||--o{ ORDER : places\n CUSTOMER {\n int id PK\n }\n',['CUSTOMER','ORDER','places']),
 'gantt':('gantt\n title Schedule\n dateFormat YYYY-MM-DD\n section Delivery\n Design :a, 2026-01-01, 3d\n Build :after a, 4d\n',['Design','Build']),
 'pie':('pie title Budget\n "Research" : 30\n "Build" : 70\n',['Research','Build']),
 'journey':('journey\n title Purchase\n section Shop\n Select: 5: User\n Pay: 3: User\n',['Select','Pay']),
 'gitGraph':('gitGraph\n commit id: "initial"\n branch develop\n checkout develop\n commit id: "feature"\n',['initial','feature']),
 'quadrantChart':('quadrantChart\n title Priority\n x-axis Low --> High\n y-axis Slow --> Fast\n quadrant-1 Act\n quadrant-2 Plan\n quadrant-3 Drop\n quadrant-4 Check\n Alpha: [0.7,0.8]\n',['Alpha','Act']),
 'requirementDiagram':('requirementDiagram\n requirement req1 {\n id: 1\n text: "Verification"\n risk: low\n verifymethod: test\n }\n',['req1','Verification']),
 'timeline':('timeline\n title History\n 2025 : Start\n 2026 : Deliver\n',['Start','Deliver']),
 'sankey-beta':('sankey-beta\n\nSource,Target,10\n',['Source','Target']),
 'xychart-beta':('xychart-beta\n title "Revenue"\n x-axis [Jan, Feb, Mar]\n y-axis "Amount" 0 --> 100\n bar [30, 60, 80]\n',['Revenue','Jan']),
 'block-beta':('block-beta\n columns 2\n a["Alpha"] b["Beta"]\n a --> b\n',['Alpha','Beta']),
 'packet-beta':('packet-beta\n 0-7: "Header"\n 8-15: "Payload"\n',['Header','Payload']),
 'kanban':('kanban\n todo[Todo]\n  task[Build]\n done[Done]\n  check[Verify]\n',['Todo','Build','Done','Verify']),
 'architecture-beta':('architecture-beta\n group cloud(cloud)[Cloud]\n service api(server)[API] in cloud\n service db(database)[Data] in cloud\n api:R -- L:db\n',['Cloud','API','Data']),
 'C4Context':('C4Context\n title Context\n Person(user, "User")\n System(sys, "System")\n Rel(user,sys,"Uses")\n UpdateRelStyle(user,sys,$offsetY="-15")\n',['User','System','Uses']),
 'C4Container':('C4Container\n Person(user, "User")\n Container(api,"API","HTTP","Service")\n Rel(user,api,"Calls")\n UpdateRelStyle(user,api,$offsetY="-15")\n',['User','API','Calls']),
 'C4Component':('C4Component\n Component(api,"API","HTTP","Service")\n Component(db,"Data","SQL","Store")\n Rel(api,db,"Writes")\n UpdateRelStyle(api,db,$offsetY="-15")\n',['API','Data','Writes']),
 'C4Deployment':('C4Deployment\n Deployment_Node(node,"Host","Linux") {\n Container(api,"API","HTTP","Service")\n }\n',['Host','API']),
 'radar-beta':('radar-beta\n title Skills\n axis a["Design"], b["Build"], c["Test"]\n curve Team{80, 90, 70}\n max 100\n',['Design','Build','Test']),
 'treemap-beta':('treemap-beta\n "Work"\n  "Design": 30\n  "Build": 70\n',['Design','Build']),
}

def cases():
    matrix={t:(load(ROOT/'assets/examples'/f'{t}.json'),None) for t in TYPES}
    for direction in ('left','balanced'):
        b=copy.deepcopy(matrix['mindmap'][0]);b['layout']['direction']=direction
        matrix['mindmap-'+direction]=(b,None)
    for t in TYPES:
        b=copy.deepcopy(matrix[t][0]);nodes=b.get('nodes',b.get('participants'))
        nodes[0]['label']='中文 "引号" [方括号] <tag> & # ; `x` C:\\目录'
        if t=='sequence':
            b['messages'][0]['note']='说明含 ";" 与 <tag>，检查中文路径 C:\\目录，保留每个符号和换行\n下一行'
            b['numbering']='process_s'
            for i,m in enumerate(b['messages'],1):m['id']='S'+str(i)
        matrix[t+'-literal']=(b,None)
    b=copy.deepcopy(matrix['activity'][0])
    b['nodes'].append({'id':'S4.1','label':'保存审计记录','kind':'action'})
    b['narrative_step_ids'].append('S4.1')
    b['edges'][-1]['to']='S4.1'
    b['edges'].append({'id':'E6','from':'S4.1','to':'S6','description':'记录后完成'})
    matrix['activity-substep']=(b,None)
    b=copy.deepcopy(matrix['sequence'][0]);b['blocks'].append({'kind':'loop','label':'每笔订单','start':1,'end':5})
    matrix['sequence-nested']=(b,None)
    b=copy.deepcopy(matrix['sequence'][0]);b['blocks'].append({'kind':'opt','label':'需要通知','start':5,'end':5})
    matrix['sequence-else-nested']=(b,None)
    b=copy.deepcopy(matrix['deployment'][0]);b['nodes'].append({'id':'handoff','label':'人工交接点','kind':'human_handoff','group':'offline','mode':'offline','network_id':'isolated','chain_id':'chain_b'})
    b['edges'].append({'id':'E4','from':'hsm','to':'handoff','description':'跨链人工交接'})
    b['boundary_triggers'].update(cross_chain=True,manual_handoff=True)
    matrix['deployment-all-boundaries']=(b,None)
    b=copy.deepcopy(matrix['sequence'][0])
    b['messages'].append({'id':'M3','from':'User','to':'Order','label':'确认结束'})
    for m,arrow in zip(b['messages'],['->>','-->>','->','-->','-x','--x']):m['arrow']=arrow
    b['blocks'].append({'kind':'critical','label':'事务保护','start':1,'end':2})
    matrix['sequence-all-arrows']=(b,None)
    b=copy.deepcopy(matrix['mindmap'][0]);b['nodes']=[{'id':'root','parent':'','label':'完整规划'}]
    for i in range(6):
        b['nodes'].append({'id':f'b{i}','parent':'root','label':f'主题{i+1}'})
        for j in range(4):b['nodes'].append({'id':f'b{i}_{j}','parent':f'b{i}','label':f'子项{i+1}.{j+1}'})
    b['nodes'].append({'id':'deep','parent':'b0_0','label':'深层行动'})
    matrix['mindmap-budget32']=(b,None)
    b=copy.deepcopy(b);b['layout']['direction']='balanced';matrix['mindmap-budget32-balanced']=(b,None)
    for syntax,(source,texts) in NATIVE.items():
        b={'diagram_id':'D1','diagram_type':'native-'+syntax.lower(),'title':'原生语法验收','summary':'检查原生 Mermaid 语法渲染及文本保真','syntax':syntax,'expected_text':texts,'layout':{'direction':'TB','spacing':60}}
        matrix['native-'+syntax]=(b,source)
    return matrix

def main():
    p=argparse.ArgumentParser();p.add_argument('output');p.add_argument('--only',nargs='*');p.add_argument('--resume',action='store_true');a=p.parse_args()
    out=Path(a.output).resolve();out.mkdir(parents=True,exist_ok=True)
    inputs=out/'inputs';inputs.mkdir(exist_ok=True)
    matrix=cases()
    # 组件细化绑定真实 overview 文件。
    parent=inputs/'overview.json';parent.write_text(json.dumps(matrix['component'][0],ensure_ascii=False))
    detail=copy.deepcopy(matrix['component'][0]);detail['view']='module_detail';detail['diagram_id']='D2'
    detail['parent_ref']={'path':'overview.json','sha256':sha(parent.read_bytes()),'diagram_id':'D1','node_id':'orders'}
    detail['groups']=[{'id':'internal','label':'订单组件内部'}]
    detail['nodes']=[{'id':i,'label':label,'kind':'module','group':'internal'} for i,label in [('accept','接单模块'),('store','订单存储'),('notify','事件通知')]]
    detail['edges']=[{'id':'E1','from':'accept','to':'store','description':'保存订单'}, {'id':'E2','from':'store','to':'notify','description':'发送创建事件'}]
    matrix['component-detail']=(detail,None)
    results=[]
    for name,(b,source) in matrix.items():
        if a.only and name not in a.only:continue
        brief=inputs/(name+'.json');brief.write_text(json.dumps(b,ensure_ascii=False,indent=2))
        src=inputs/(name+'.mmd')
        if source:src.write_text(source)
        try:
            if a.resume and (out/name/'validation.json').exists():
                r=verify(out/name,allow_pending=True)
                assert r['input_fingerprint']==fingerprint(b,source or generate(b),contract_hash())
            else:
                r=run(brief,out/name,src if source else None)
            assert r['final_status'] in ('review_required','success'),json.dumps(r['issues'],ensure_ascii=False)
            verify(out/name,allow_pending=True)
            result={'case':name,'technical':'passed','visual':'pending'}
        except Exception as exc:
            result={'case':name,'technical':'failed','reason':str(exc)}
        results.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
        (out/'results.json').write_text(json.dumps(results,ensure_ascii=False,indent=2)+'\n')
    sys.exit(1 if any(r['technical']=='failed' for r in results) else 0)
if __name__=='__main__':main()
