import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import bili_rank
import prepare_static
from bili_rank import RiskStop, Store, bounds
from build_static import build


class StaticTests(unittest.TestCase):
    def test_frozen_year_files_and_safe_standalone_data(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            store=Store(root/'videos.sqlite3')
            item={'bvid':'BV14b411w7zx','pubdate':bounds(2018)[0],
                  'play':200,'title':'&lt;/script&gt;&lt;script&gt;alert(1)&lt;/script&gt;','author':'UP'}
            store.ingest([item],2018,'已有词')
            (root/'static_preparation.json').write_text(json.dumps({'years':[2018],
                'terms':['2018','动画'],'completed':['2018:2018'],'phase':'paused'}),encoding='utf-8')
            manifest=build(root/'videos.sqlite3',root/'static',2018)
            year_file=root/'static'/'2018.json'
            before=year_file.read_bytes()
            snapshot=json.loads(before)
            self.assertEqual(snapshot['videos'][0]['rank'],1)
            self.assertEqual(snapshot['videos'][0]['play'],200)
            self.assertEqual(snapshot['status'],'partial')
            self.assertIn('尚未全部完成',snapshot['notice'])
            self.assertEqual(len(manifest['years']),10)
            self.assertEqual(json.loads((root/'static'/'2009.json').read_text())['status'],'pending')
            html=(root/'static'/'index.html').read_text(encoding='utf-8')
            self.assertNotIn('</script><script>alert(1)',html)
            self.assertIn('\\u003c/script>',html)
            self.assertNotIn("call('start'",html)
            store.ingest([{**item,'play':300}],2018,'已有词')
            self.assertEqual(year_file.read_bytes(),before)
            store.close()

    def test_preparation_stops_batch_on_risk_and_resumes_fixed_tasks(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            calls=[]
            def collect(_client,_store,year,terms,*_args,**kwargs):
                calls.append((year,terms[0]))
                kwargs_meta=_args[-1]
                kwargs_meta.update({'network_search_requests':1,'run_mode':'online'})
                if len(calls)==2:raise RiskStop('HTTP 412')
                kwargs_meta['finished_at']='2026-10-26T17:00:00+08:00'
            with patch.object(bili_rank,'ROOT',root),patch.object(bili_rank,'now',return_value='2026-10-26T17:00:00+08:00'),\
                 patch.object(bili_rank,'Client'),\
                 patch.object(bili_rank,'collect',side_effect=collect),patch.object(prepare_static,'build'):
                first=prepare_static.prepare(lambda *_args,**_kwargs:None,last_year=2010)
                self.assertEqual(first['phase'],'paused')
                self.assertEqual(len(calls),2)
                self.assertEqual(len(first['completed']),1)
                second=prepare_static.prepare(lambda *_args,**_kwargs:None,last_year=2010)
                self.assertEqual(second['phase'],'completed')
                self.assertEqual(len(second['completed']),32)
                self.assertEqual(calls.count((2009,'2009')),1)
                self.assertEqual(second['terms'],list(prepare_static.TERMS))

    def test_sparse_years_deepen_existing_terms_without_adding_words(self):
        with tempfile.TemporaryDirectory() as directory:
            root=Path(directory)
            calls=[]
            class FakeClient:
                cancel=threading.Event()
                def __init__(self,**_):pass
                def search(self,term,year,page,size):
                    calls.append((year,term,page))
                    return {'numPages':4,'result':[{'bvid':f'BV1{year*100000+page*100+i:09d}',
                        'pubdate':bounds(year)[0],'play':1000-page*30-i,'title':'视频','author':'UP'}
                        for i in range(30)]}
            with patch.object(bili_rank,'ROOT',root),patch.object(bili_rank,'Client',FakeClient),\
                 patch.object(prepare_static,'build'):
                state=prepare_static.prepare(lambda *_args,**_kwargs:None,last_year=2010)
            store=Store(root/'data'/'videos.sqlite3')
            try:
                self.assertEqual(len(store.rows(2009)),120)
                self.assertEqual(len(store.rows(2010)),120)
                self.assertEqual(len(state['completed']),32)
                self.assertEqual(len(calls),38)
                self.assertEqual({term for year,term,page in calls if page>1},{'2009','2010'})
            finally:store.close()


if __name__=='__main__':unittest.main()
