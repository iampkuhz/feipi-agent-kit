"""依赖生命周期：固定版本、跨安装复用、失败隔离和并发首次准备。"""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import shutil
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'scripts'))
import prepare_runtime as runtime


class Dependencies(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.skill=self.root/'skill';self.skill.mkdir()
        self.cache=self.root/'cache';self.calls=[]
        self.node={'version':'26.11.1','abi':'149','platform':'darwin','arch':'arm64'}
        self.packages={'ajv':'8.20.0','pptxgenjs':'3.12.0','jszip':'3.10.1'}
        (self.skill/'package.json').write_text(json.dumps({'dependencies':self.packages}))
        (self.skill/'package-lock.json').write_text(json.dumps({'packages':{'node_modules/'+n:{'version':v} for n,v in self.packages.items()}}))
        for name,value in [('cache_root',lambda:self.cache),('command',self.command)]:
            p=patch.object(runtime,name,value);p.start();self.addCleanup(p.stop)

    def command(self,args,**kwargs):
        if args[0]=='node':return json.dumps(self.node)
        self.assertEqual(args,['npm','ci','--ignore-scripts','--no-audit','--no-fund','--prefer-offline'])
        self.assertEqual(kwargs['env']['PUPPETEER_SKIP_DOWNLOAD'],'true')
        self.calls.append(args)
        time.sleep(.02)
        for name,version in self.packages.items():
            path=Path(kwargs['cwd'])/'node_modules'/name
            path.mkdir(parents=True)
            (path/'package.json').write_text(json.dumps({'version':version}))
        return ''

    def test_first_use_installs_once_and_does_not_modify_skill(self):
        before={p.name:p.read_bytes() for p in self.skill.iterdir()}
        first=runtime.ensure_runtime(self.skill);second=runtime.ensure_runtime(self.skill)
        self.assertFalse(first['reused']);self.assertTrue(second['reused'])
        self.assertEqual(first['path'],second['path']);self.assertEqual(len(self.calls),1)
        self.assertEqual(before,{p.name:p.read_bytes() for p in self.skill.iterdir()})

    def test_identical_installation_uses_same_cache(self):
        other=self.root/'another client';shutil.copytree(self.skill,other)
        first=runtime.ensure_runtime(self.skill);second=runtime.ensure_runtime(other)
        self.assertEqual(first['path'],second['path']);self.assertEqual(len(self.calls),1)

    def test_lock_change_and_node_abi_get_distinct_caches(self):
        first=runtime.ensure_runtime(self.skill)
        path=self.skill/'package-lock.json';path.write_text(path.read_text()+'\n')
        second=runtime.ensure_runtime(self.skill)
        self.node['abi']='150';third=runtime.ensure_runtime(self.skill)
        self.assertEqual(len({v['path'] for v in [first,second,third]}),3)
        self.assertTrue(all(Path(v['path']).is_dir() for v in [first,second,third]))

    def test_check_missing_cache_is_read_only(self):
        with self.assertRaisesRegex(RuntimeError,'尚未准备'):
            runtime.ensure_runtime(self.skill,check=True)
        self.assertFalse(self.cache.exists());self.assertEqual(self.calls,[])

    def test_failed_npm_does_not_publish_or_leave_partial_build(self):
        def fail(args,**kwargs):
            if args[0]=='node':return json.dumps(self.node)
            raise RuntimeError('offline registry')
        with patch.object(runtime,'command',side_effect=fail):
            with self.assertRaisesRegex(RuntimeError,'offline registry'):
                runtime.ensure_runtime(self.skill)
        self.assertEqual([p for p in self.cache.iterdir() if p.is_dir()],[])

    def test_missing_or_wrong_dependency_is_not_accepted(self):
        first=runtime.ensure_runtime(self.skill)
        path=Path(first['path'])/'node_modules/ajv/package.json'
        path.write_text('{"version":"wrong"}')
        self.assertFalse(runtime.ensure_runtime(self.skill)['reused'])
        self.assertEqual(len(self.calls),2)

    def test_concurrent_first_use_only_installs_once(self):
        with ThreadPoolExecutor(max_workers=2) as pool:
            results=list(pool.map(runtime.ensure_runtime,[self.skill,self.skill]))
        self.assertEqual(len(self.calls),1)
        self.assertEqual(sorted(v['reused'] for v in results),[False,True])

    def test_old_node_is_rejected_without_install(self):
        self.node['version']='17.9.0'
        with self.assertRaisesRegex(RuntimeError,'18'):
            runtime.ensure_runtime(self.skill)
        self.assertFalse(self.cache.exists())


if __name__=='__main__':unittest.main()
