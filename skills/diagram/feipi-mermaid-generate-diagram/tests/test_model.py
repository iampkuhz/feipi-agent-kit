"""跨图型反例与质量门禁回归，不依赖浏览器。"""
import copy
import json
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
from model import *
from package import layout_issues
from run import run

class ModelTests(unittest.TestCase):
    def fixture(self,name): return load(ROOT/'assets/examples'/f'{name}.json')
    def invalid(self,b):
        with self.assertRaises((Invalid,ValueError)):
            validate(b,ROOT/'assets/examples')
    def test_all_examples(self):
        for t in TYPES:
            with self.subTest(t=t):
                b=self.fixture(t);validate(b,ROOT/'assets/examples');check_source(b,generate(b))
    def test_missing_fields_and_unknown_fields(self):
        for t in TYPES:
            with self.subTest(t=t):
                b=self.fixture(t);b.pop('title');self.invalid(b)
                b=self.fixture(t);b['invented']=1;self.invalid(b)
    def test_duplicate_id(self):
        for t in TYPES:
            with self.subTest(t=t):
                b=self.fixture(t);items=b.get('nodes',b.get('participants'));items[1]['id']=items[0]['id'];self.invalid(b)
    def test_mutated_source_rejected(self):
        for t in TYPES:
            with self.subTest(t=t):
                b=self.fixture(t);s=generate(b)
                with self.assertRaises(Invalid):check_source(b,s+'evil --> hidden\n')
                with self.assertRaises(Invalid):check_source(b,'\n'.join(s.splitlines()[:-1]))
                check_source(b,'%% 普通注释\n'+s)
    def test_control_and_injection(self):
        b=self.fixture('component');b['nodes'][0]['label']='坏\x00文本';self.invalid(b)
        b=self.fixture('component');s=generate(b)
        for extra in ('%%{init:{}}%%\n','click foo "javascript:evil"\n','---\n'):
            with self.assertRaises(Invalid):check_source(b,extra+s)
    def test_missing_endpoint_and_orphan(self):
        b=self.fixture('component');b['edges'][0]['to']='absent';self.invalid(b)
        b=self.fixture('component');b['edges'].pop(0);self.invalid(b)
    def test_architecture_budget(self):
        b=self.fixture('architecture');b['groups'].pop();self.invalid(b)
        b=self.fixture('architecture');b['layout']['direction']='LR';self.invalid(b)
    def test_component_overview_modules(self):
        b=self.fixture('component');b['nodes'][0]['kind']='module';self.invalid(b)
    def test_component_parent_binding(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);parent=tmp/'parent.json';parent.write_text(json.dumps(self.fixture('component')))
            b=self.fixture('component');b['view']='module_detail';b['parent_ref']={'path':'parent.json','sha256':sha(parent.read_bytes()),'diagram_id':'D1','node_id':'orders'}
            validate(b,tmp)
            for key,bad in [('path','../parent.json'),('sha256','0'*64),('node_id','ghost'),('diagram_id','D9')]:
                x=copy.deepcopy(b);x['parent_ref'][key]=bad
                with self.assertRaises(Invalid):validate(x,tmp)
    def test_sequence_message_order(self):
        b=self.fixture('sequence');original=generate(b);b['messages'][0],b['messages'][1]=b['messages'][1],b['messages'][0]
        with self.assertRaises(Invalid):check_source(b,original)
    def test_sequence_order_preserved(self):
        s=generate(self.fixture('sequence'));self.assertLess(s.index('participant User'),s.index('participant Order'))
    def test_sequence_numbering(self):
        b=self.fixture('sequence');b['messages'][0]['id']='S1';self.invalid(b)
        b['numbering']='process_s'
        for i,m in enumerate(b['messages'],1):m['id']='S'+str(i)
        validate(b,ROOT)
    def test_sequence_blocks(self):
        for extra in ({'kind':'loop','label':'循环','start':2,'end':4},{'kind':'loop','label':'循环','start':3,'end':5}):
            b=self.fixture('sequence');b['blocks'].append(extra);self.invalid(b)
        b=self.fixture('sequence');b['blocks'][0].pop('else_at');self.invalid(b)
    def test_sequence_nested_valid(self):
        b=self.fixture('sequence');b['blocks'].append({'kind':'loop','label':'重试','start':1,'end':5});validate(b,ROOT)
    def test_nested_block_at_else_starts_after_branch_switch(self):
        b=self.fixture('sequence');b['blocks'].append({'kind':'opt','label':'需要通知','start':5,'end':5});validate(b,ROOT)
        source=generate(b);self.assertLess(source.index('else '),source.index('opt '))
    def test_sequence_group_cannot_reorder(self):
        b=self.fixture('sequence');b['participants'][0]['group']='backend';b['participants'][1].pop('group');self.invalid(b)
    def test_activity_missing_branch(self):
        b=self.fixture('activity');b['edges']=[e for e in b['edges'] if e['to']!='S5'];self.invalid(b)
    def test_activity_stop_fallthrough(self):
        b=self.fixture('activity');b['edges'].append({'id':'E6','from':'S5','to':'S6','description':'错误顺序边'});self.invalid(b)
    def test_activity_narrative_and_ids(self):
        b=self.fixture('activity');b['narrative_step_ids'].pop();self.invalid(b)
        b=self.fixture('activity');b['nodes'][0]['id']='S9';self.invalid(b)
    def test_deployment_triggers(self):
        for key in self.fixture('deployment')['boundary_triggers']:
            b=self.fixture('deployment');b['boundary_triggers'][key]=not b['boundary_triggers'][key];self.invalid(b)
    def test_mindmap_tree_errors(self):
        for change in ('cycle','two_roots','missing','duplicate_label'):
            b=self.fixture('mindmap')
            if change=='cycle':b['nodes'][0]['parent']='research'
            elif change=='two_roots':b['nodes'][1]['parent']=''
            elif change=='missing':b['nodes'][1]['parent']='ghost'
            else:b['nodes'][2]['label']=b['nodes'][1]['label']
            self.invalid(b)
    def test_mindmap_depth(self):
        b=self.fixture('mindmap');b['nodes']=[{'id':f'n{i}','parent':f'n{i-1}' if i else '', 'label':str(i)} for i in range(5)];self.invalid(b)
    def test_fallback_preserves_type(self):
        b=self.fixture('class');validate(b,ROOT);self.assertEqual(b['diagram_type'],'class')
        with self.assertRaises(Invalid):check_source(b,'classDiagram\nclass Missing\n')
    def test_yaml_ambiguity(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'b.yaml'
            for text in ('title: one\ntitle: two\n','node: &x [*x]\n'):
                p.write_text(text)
                with self.assertRaises(Invalid):load(p)
    def test_rendered_text_is_not_entity_codes(self):
        b=self.fixture('mindmap')
        with self.assertRaises(Invalid):check_visible_text(b,{'texts':[{'text':''.join(f'&#{ord(c)};' for c in n['label'])} for n in b['nodes']]})
        check_visible_text(b,{'texts':[{'text':n['label']} for n in b['nodes']]})
    def test_geometry_detects_real_defects(self):
        ev={'view_box':[0,0,100,100],'texts':[{'text':'标签','rect':[10,10,30,20]}],'edges':[{'id':'e','points':[[15,15]]}]}
        self.assertEqual(layout_issues(ev)[0]['kind'],'edge_crosses_text')
        ev['edges']=[];ev['texts'].append({'text':'覆盖','rect':[20,10,30,20]});self.assertTrue(layout_issues(ev))
        ev['texts']=[{'text':'截断','rect':[95,95,30,20]}];self.assertEqual(layout_issues(ev)[0]['kind'],'clipped_text')
    def test_mindmap_edge_cannot_pass_through_third_node(self):
        ev={'view_box':[0,0,100,100],'texts':[{'text':'字','rect':[40,40,10,10]}],
            'nodes':[{'id':'other','rect':[10,10,30,20]}],
            'edges':[{'id':'edge','points':[[15,15]],'masked_endpoints':['source','target']}]}
        self.assertEqual(layout_issues(ev)[0]['kind'],'edge_crosses_node')
        ev['nodes'][0]['id']='source';self.assertEqual(layout_issues(ev),[])
    def test_invalid_input_never_renders(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);p=tmp/'bad.json';p.write_text('{}')
            r=run(p,tmp/'out');self.assertEqual(r['attempt_index'],0);self.assertEqual(r['failure_class'],'brief')
    def test_unknown_output_file_protected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);(tmp/'user.txt').write_text('keep')
            with self.assertRaises(Invalid):run(ROOT/'assets/examples/mindmap.json',tmp)
            self.assertEqual((tmp/'user.txt').read_text(),'keep')
    def test_output_symlink_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp=Path(tmp);(tmp/'real').mkdir();(tmp/'link').symlink_to(tmp/'real',target_is_directory=True)
            with self.assertRaises(Invalid):run(ROOT/'assets/examples/mindmap.json',tmp/'link')

if __name__=='__main__':unittest.main()
