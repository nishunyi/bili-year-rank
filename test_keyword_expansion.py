import io
import json
from pathlib import Path
import tempfile
import threading
import unittest
import urllib.error
from unittest.mock import patch

import bili_rank
from bili_rank import ApiError, Client, RiskStop, Store, bounds, collect, coverage_summary,validate_search_page
from keyword_plan import build_plan, canonical, discovered_terms


class ExpansionTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.store=Store(Path(self.temp.name)/'test.sqlite3')
        self.start=bounds(2018)[0]

    def tearDown(self):
        self.store.close();self.temp.cleanup()

    def item(self,index,plays):
        return {'bvid':f'BV1{index:09d}','pubdate':self.start,'play':plays,'title':f'视频 {index}','author':'作者'}

    def fake(self,results):
        class Fake:
            cancel=threading.Event()
            def __init__(fake):fake.calls=[]
            def search(fake,keyword,year,page,size):
                fake.calls.append((keyword,page))
                return {'result':results[(keyword,page)],'numPages':3}
        return Fake()

    def test_year_aware_dedup_and_balanced_frontier(self):
        older=build_plan(2011)
        newer=build_plan(2018)
        self.assertEqual(older[0]['keyword'],'2011')
        self.assertNotIn('2018',[r['keyword'] for r in older])
        self.assertIn('千本樱',[r['keyword'] for r in older])
        self.assertIn('改革春风吹满地',[r['keyword'] for r in newer])
        self.assertNotIn('原神',[r['keyword'] for r in newer])
        self.assertEqual(len(newer),len({canonical(r['keyword']) for r in newer}))
        self.assertEqual(len({r['group'] for r in newer[:16]}),16)
        self.assertLess(len(build_plan(2018,'quick')),len(newer))
        self.assertLessEqual(len(newer)+20,250)

    def test_feedback_counts_each_bv_once_and_filters_bad_terms(self):
        item=self.item(1,1000000)
        item['tag']='新题材,https://example.com,2026教程,另一个题材'
        self.store.ingest([item],2018,'种子')
        self.store.save_page(2018,'种子',1,30,{'result':[item,item]})
        terms=[r['keyword'] for r in discovered_terms(self.store,2018)]
        self.assertIn('新题材',terms)
        self.assertNotIn('2026教程',terms)
        self.assertNotIn('https://example.com',terms)
        self.assertEqual(len(terms),len(set(terms)))

    def test_all_first_pages_before_deepening(self):
        fake=self.fake({('甲',1):[self.item(1,500)],('乙',1):[self.item(2,400)],
                        ('甲',2):[self.item(3,300)],('乙',2):[self.item(4,200)]})
        meta=collect(fake,self.store,2018,['甲','乙'],2,30,6,lambda _:None)
        self.assertEqual(fake.calls,[('甲',1),('乙',1),('甲',2),('乙',2)])
        self.assertEqual(coverage_summary(self.store,2018,meta)['new_candidates'],4)

    def test_threshold_deepens_promising_queries_only(self):
        self.store.ingest([self.item(1,1000),self.item(2,900),self.item(3,800)],2018,'已有')
        fake=self.fake({('低',1):[self.item(4,700),self.item(5,600)],
                        ('高',1):[self.item(6,2000),self.item(7,1900)],
                        ('高',2):[self.item(8,1800),self.item(9,1700)]})
        meta=collect(fake,self.store,2018,['低','高'],3,30,6,lambda _:None,adaptive=True,top_k=3)
        self.assertEqual(fake.calls,[('低',1),('高',1),('高',2)])
        self.assertEqual(meta['keyword_stats']['低']['stop_reason'],'below_top_k_threshold')

    def test_unordered_results_disable_threshold_pruning(self):
        self.store.ingest([self.item(1,1000)],2018,'已有')
        fake=self.fake({('乱序',1):[self.item(2,100),self.item(3,200)],
                        ('乱序',2):[self.item(4,50)]})
        collect(fake,self.store,2018,['乱序'],2,30,6,lambda _:None,adaptive=True,top_k=1)
        self.assertEqual(len(fake.calls),2)

    def test_cached_pages_do_not_spend_network_budget(self):
        self.store.save_page(2018,'缓存',1,30,{'result':[self.item(1,100)],'numPages':1})
        fake=self.fake({('联网',1):[self.item(2,90)]})
        meta=collect(fake,self.store,2018,['缓存','联网','待查询'],1,30,6,lambda _:None,request_budget=1)
        coverage_summary(self.store,2018,meta)
        self.assertEqual(fake.calls,[('联网',1)])
        self.assertEqual(meta['unsearched_keywords'],['待查询'])

    def test_old_cache_cannot_refresh_timestamp_or_replace_newer_count(self):
        self.store.ingest([self.item(1,200)],2018,'新','2026-10-26T13:00:00+08:00')
        self.store.ingest([self.item(1,100)],2018,'旧','2026-10-26T12:00:00+08:00')
        row=self.store.rows(2018)[0]
        self.assertEqual(row['play'],200)
        self.assertEqual(row['play_at'],'2026-10-26T13:00:00+08:00')
        self.assertIn('旧',row['keywords'])

    def test_one_transport_retry_and_no_retry_for_risk_status(self):
        class NoWait:
            def wait(self,_):return False
        class Opener:
            def __init__(fake,first):fake.first=first;fake.calls=0
            def open(fake,*args,**kwargs):
                fake.calls+=1
                if fake.calls==1:raise fake.first
                return io.BytesIO(b'{"code":0,"data":{}}')
        client=Client(cancel=NoWait())
        client.opener=Opener(urllib.error.URLError(ConnectionResetError(10054,'reset')))
        self.assertEqual(client.get('/test')['code'],0)
        self.assertEqual(client.opener.calls,2)
        self.assertEqual(client.transport_retries,1)
        client.opener=Opener(urllib.error.HTTPError('https://example.com',412,'blocked',{},None))
        with self.assertRaises(RiskStop):client.get('/test')
        self.assertEqual(client.opener.calls,1)

    def test_code_zero_voucher_is_risk_not_an_empty_page(self):
        class NoWait:
            def wait(self,_):return False
        class Opener:
            calls=0
            def open(fake,*args,**kwargs):
                fake.calls+=1
                return io.BytesIO(b'{"code":0,"data":{"v_voucher":"test-only"}}')
        client=Client(cancel=NoWait());client.opener=Opener()
        with self.assertRaises(RiskStop):client.get('/test')
        self.assertEqual(client.opener.calls,1)
        with self.assertRaises(RiskStop):self.store.save_page(2018,'词',1,30,{'v_voucher':'test-only'})
        self.assertEqual(self.store.db.execute('select count(*) from pages').fetchone()[0],0)
        self.assertEqual(validate_search_page({'result':[],'numResults':0})['result'],[])

    def test_explicit_zero_counters_can_omit_result_but_risk_cannot(self):
        empty={'numResults':0,'numPages':0,'page':1}
        self.assertEqual(validate_search_page(empty)['result'],[])
        self.store.save_page(2018,'空',1,30,empty)
        self.assertEqual(self.store.cached_page(2018,'空',1,30,6)['result'],[])
        with self.assertRaises(RiskStop):validate_search_page({**empty,'v_voucher':'test-only'})
        for data in ({},{'numResults':0},{'numResults':30,'numPages':1},
                     {'numResults':False,'numPages':False}):
            with self.assertRaises(ApiError):validate_search_page(data)

    def test_cache_only_never_requests_missing_pages(self):
        self.store.save_page(2018,'已有',1,30,{'result':[self.item(1,100)],'numPages':1})
        fake=self.fake({})
        meta=collect(fake,self.store,2018,['已有','待恢复'],2,30,6,lambda _:None,cache_only=True)
        coverage_summary(self.store,2018,meta)
        self.assertEqual(fake.calls,[])
        self.assertEqual(meta['unsearched_keywords'],['待恢复'])

    def test_pause_survives_offline_work_until_successful_network_run(self):
        root=Path(self.temp.name)
        args=bili_rank.parser().parse_args(['--database',str(root/'test.sqlite3'),
              '--output',str(root/'output'),'--keywords','词','--pages','1','--cache-hours','0'])
        fake=self.fake({})
        fake.search=lambda *args:(_ for _ in ()).throw(RiskStop('HTTP 412'))
        def execute():
            with patch.object(bili_rank,'ROOT',root),patch.object(bili_rank,'Client',return_value=fake):
                _,html_path=bili_rank.run(args,lambda _:None)
            return json.loads(html_path.with_suffix('.json').read_text(encoding='utf-8'))['metadata']
        execute()
        self.assertTrue(bili_rank.search_state(args.database,2018)['paused'])
        args.export_only=True
        self.assertEqual(execute()['paused_reason'],'risk_control')
        args.export_only=False;args.cache_only=True;args.refresh_stats=True
        self.assertEqual(execute()['paused_reason'],'risk_control')
        args.cache_only=False;args.refresh_stats=False;args.cache_hours=6
        self.store.save_page(2018,'词',1,30,{'result':[],'numPages':1})
        self.assertEqual(execute()['paused_reason'],'risk_control')
        # Clearing a different year's pause must not erase the 2018 notice.
        bili_rank.update_search_state(args.database,2011,{'paused_reason':'risk_control'})
        args.cache_hours=0
        fake.search=lambda *args:{'result':[],'numPages':1}
        execute()
        self.assertFalse(bili_rank.search_state(args.database,2018)['paused'])
        self.assertTrue(bili_rank.search_state(args.database,2011)['paused'])


if __name__=='__main__':unittest.main()
