"""Offline-only recovery after the interrupted keyword-expansion experiment."""
import datetime as dt
import json
from pathlib import Path
import sqlite3
import tempfile
import threading

import bili_rank
from keyword_plan import build_plan

ROOT=Path(__file__).parent


def main():
    baseline=ROOT/'evidence'/'keyword_expansion'/'before.sqlite3'
    source=sqlite3.connect(ROOT/'data'/'videos.sqlite3')
    with tempfile.TemporaryDirectory() as directory:
        replay_path=Path(directory)/'replay.sqlite3'
        before=sqlite3.connect(baseline)
        replay=sqlite3.connect(replay_path)
        before.backup(replay);before.close()
        valid_pages=[]
        for row in source.execute('SELECT year,keyword,page,page_size,fetched_at,payload FROM pages WHERE year=2018'):
            bili_rank.validate_search_page(json.loads(row[-1]))
            replay.execute('INSERT OR REPLACE INTO pages VALUES(?,?,?,?,?,?)',row)
            valid_pages.append(row)
        replay.commit();replay.close()
        store=bili_rank.Store(replay_path)
        plan=build_plan(2018,'broad',store)
        terms=[p['keyword'] for p in plan]
        for row in valid_pages:
            if row[1] not in terms:terms.append(row[1])
        class OfflineOnly:
            cancel=threading.Event()
            def search(self,*args):raise AssertionError('Recovery must not access the network')
        meta=bili_rank.collect(OfflineOnly(),store,2018,terms,3,30,float('inf'),lambda _:None,
                              cache_only=True,plan=plan)
        bili_rank.coverage_summary(store,2018,meta)
        meta['cache_replay_finished_at']=meta.pop('finished_at')
        meta.update({'paused_reason':'risk_control','stopped_at':bili_rank.now(),
                     'errors':['服务器返回 v_voucher 风控响应，在线采集已暂停；剩余关键词尚未完成'],
                     'provenance':'reconstructed_from_valid_cache','network_search_requests':None,
                     'note':'中途停止的在线进程未保存完整请求计数；本次仅从基线与有效缓存回放候选增益，不估计全站召回率。'})
        store.close()
    source.close()
    current=bili_rank.Store(ROOT/'data'/'videos.sqlite3')
    try:
        # The replay must recover the same candidate set as committed real responses.
        if meta['candidate_count']!=len(current.rows(2018)):
            raise ValueError('缓存回放与已提交候选数不一致，停止导出')
        paths=bili_rank.export(current,2018,100,meta,ROOT/'output')
        stamp=dt.datetime.now(bili_rank.TZ).strftime('%Y%m%d_%H%M%S_%f')
        (ROOT/'data'/'coverage_runs'/f'2018_{stamp}_recovered.json').write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        print(json.dumps({k:meta[k] for k in ['baseline_candidates','candidate_count','new_candidates','newly_discovered_top100','queried_keywords','paused_reason']},ensure_ascii=False,indent=2))
    finally:current.close()


if __name__=='__main__':main()
