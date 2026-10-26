"""One-time preparation of missing years using an immutable set of existing terms.

Not used by the desktop client. Stops the whole batch on service risk control.
"""
import json
from pathlib import Path

import bili_rank
from build_static import build, write_json

# Existing first-round themes only; never add feedback tags/authors or new words.
TERMS=('{year}','动画','游戏','音乐','舞蹈','鬼畜','电影','综艺',
       '学习','科技','美食','动物','旅行','体育','时尚','娱乐')


def prepare(log=print,*,last_year=None):
    database=bili_rank.ROOT/'data'/'videos.sqlite3'
    state_path=bili_rank.ROOT/'data'/'static_preparation.json'
    last_year=last_year or bili_rank.dt.datetime.now(bili_rank.TZ).year
    store=bili_rank.Store(database)
    if state_path.exists():
        state=json.loads(state_path.read_text(encoding='utf-8'))
        if state['terms']!=list(TERMS):raise ValueError('固定词表不匹配，拒绝自动扩词')
    else:
        years=[y for y in range(2009,last_year+1) if not store.rows(y)]
        state={'started_at':bili_rank.now(),'terms':list(TERMS),'years':years,
               'completed':[],'network_search_requests':0,'errors':[]}
    completed=set(state['completed'])
    client=bili_rank.Client(interval=5)
    state['phase']='running'
    state['errors']=[]
    meta={}
    year=None
    try:
        # Give each year a first page before moving to the next topic.
        for template in TERMS:
            for year in state['years']:
                term=template.format(year=year)
                key=f'{year}:{term}'
                if key in completed:continue
                state['current']={'year':year,'keyword':term}
                write_json(state_path,state)
                meta={}
                try:
                    bili_rank.collect(client,store,year,[term],1,30,87600,
                                      log,meta,request_budget=1)
                finally:
                    state['network_search_requests']+=meta.get('network_search_requests',0)
                completed.add(key)
                state['completed']=sorted(completed)
                state['updated_at']=bili_rank.now()
                bili_rank.update_search_state(database,year,meta)
                write_json(state_path,state)
                log(f'已整理 {year} 年：{len(store.rows(year))} 个候选；进度 {len(completed)}/{len(TERMS)*len(state["years"])}',flush=True)
            build(database)
        # Sparse years may need more pages of an already-used query. Keep the
        # word list fixed; never invent rows to reach a round number.
        state.setdefault('deeper_completed',[])
        for year in state['years']:
            for template in TERMS:
                if len(store.rows(year))>=100:break
                term=template.format(year=year)
                key=f'{year}:{term}'
                if key in state['deeper_completed']:continue
                first=store.cached_page(year,term,1,30,87600)
                available=(bili_rank.count(first.get('numPages')) or 1) if first else 1
                if available<=1:continue
                state['current']={'year':year,'keyword':term,'phase':'deepen_existing_query'}
                write_json(state_path,state)
                meta={}
                try:
                    bili_rank.collect(client,store,year,[term],min(4,available),30,87600,
                                      log,meta,request_budget=3)
                finally:
                    state['network_search_requests']+=meta.get('network_search_requests',0)
                state['deeper_completed'].append(key)
                bili_rank.update_search_state(database,year,meta)
                state['updated_at']=bili_rank.now()
                write_json(state_path,state)
                log(f'补翻已有查询：{year} 年现有 {len(store.rows(year))} 个候选',flush=True)
                build(database)
        state['phase']='completed'
        state['finished_at']=bili_rank.now()
    except (bili_rank.ApiError,bili_rank.Cancelled,KeyboardInterrupt) as error:
        state['phase']='paused'
        state['errors']=[str(error) or '用户中断']
        state['stopped_at']=bili_rank.now()
        if isinstance(error,bili_rank.RiskStop):
            meta['paused_reason']='risk_control'
            bili_rank.update_search_state(database,year,meta)
        log('批次已停止并保留结果：'+state['errors'][0],flush=True)
    finally:
        store.close()
        write_json(state_path,state)
        build(database)
    return state


if __name__=='__main__':
    prepare()
