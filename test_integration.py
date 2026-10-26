import hashlib
import importlib.util
import json
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).parent
sys.path.insert(0,str(ROOT/'integration'))
from patch_client import Archive,build_archive,integrity
import worker


def fixture(path):
    files={'package.json':json.dumps({'version':'1.19.0'}).encode(),
           'main/index.js':b'module.exports=()=>42;', 'render/index.html':'你好'.encode()}
    header={'files':{}}
    blobs=[]
    offset=0
    for name,data in files.items():
        node=header
        parts=name.split('/')
        for part in parts[:-1]:node=node['files'].setdefault(part,{'files':{}})
        node['files'][parts[-1]]={'size':len(data),'offset':str(offset),'integrity':integrity(data)}
        offset+=len(data);blobs.append(data)
    encoded=json.dumps(header,ensure_ascii=False,separators=(',',':')).encode()
    pad=(-(len(encoded)+4))%4
    payload=struct.pack('<II',len(encoded)+4+pad,len(encoded))+encoded+b'\0'*pad
    path.write_bytes(struct.pack('<II',4,len(payload))+payload+b''.join(blobs))


class IntegrationTests(unittest.TestCase):
    def test_archive_changes_only_requested_file(self):
        with tempfile.TemporaryDirectory() as directory:
            before,after=Path(directory)/'before.asar',Path(directory)/'after.asar'
            fixture(before)
            original=Archive(before)
            replacement=b'/* loader */\n'+original.read('main/index.js')
            result=build_archive(before,after,{'main/index.js':replacement})
            archive=Archive(after)
            self.assertEqual(result['changed_files'],['main/index.js'])
            self.assertEqual(archive.read('render/index.html'),'你好'.encode())
            self.assertEqual(archive.read('package.json'),original.read('package.json'))
            item=archive.header['files']['main']['files']['index.js']
            self.assertEqual(item['integrity']['hash'],hashlib.sha256(replacement).hexdigest())

    def test_worker_rejects_invalid_requests(self):
        for data in ({'year':True},{'year':2000},{'year':2018,'limit':-1},
                     {'year':2018,'minPlay':-1},{'year':2018,'sort':'DROP TABLE videos'}):
            with self.assertRaises(ValueError):worker.list_records(data)
        with self.assertRaises(ValueError):worker.dispatch('arbitrary-command',{})
        with self.assertRaises(ValueError):worker.dispatch('list',[])

    def test_real_index_query_and_json_line_protocol(self):
        requests=[{'id':1,'method':'list','data':{'year':2018,'limit':5}},
                  {'id':2,'method':'status','data':{}},
                  {'id':3,'method':'list','data':{'year':2018,'keyword':'赵本山','limit':10}},
                  {'id':4,'method':'plan','data':{'year':2011,'profile':'quick'}}]
        with tempfile.TemporaryDirectory() as directory:
            from bili_rank import Store,bounds
            fixture_root=Path(directory)
            store=Store(fixture_root/'data'/'videos.sqlite3')
            try:
                store.ingest([{'bvid':f'BV1{i:09d}','pubdate':bounds(2018)[0],
                    'play':1000-i,'title':f'视频 {i}','author':'赵本山' if i%2 else '作者'}
                    for i in range(1,7)],2018,'已有词')
            finally:store.close()
            bootstrap=f'import sys;sys.path.insert(0,{str(ROOT/"integration")!r});import worker;from pathlib import Path;worker.ROOT=Path({str(fixture_root)!r});worker.main()'
            output=subprocess.run([sys.executable,'-X','utf8','-c',bootstrap],
                  input=''.join(json.dumps(r)+'\n' for r in requests),capture_output=True,text=True,
                  encoding='utf-8',timeout=15,check=True)
        answers=[json.loads(line) for line in output.stdout.splitlines()]
        self.assertEqual([a['id'] for a in answers],[1,2,3,4])
        rows=answers[0]['result']['videos']
        self.assertEqual(len(rows),5)
        self.assertEqual([r['play'] for r in rows],sorted((r['play'] for r in rows),reverse=True))
        self.assertFalse(answers[0]['result']['sitewideComplete'])
        self.assertTrue(all('赵本山' in r['title']+r['author']+r['bvid'] for r in answers[2]['result']['videos']))
        self.assertEqual(answers[3]['result']['keywords'][0],'2011')
        self.assertNotIn('2018',answers[3]['result']['keywords'])


if __name__=='__main__':unittest.main()
