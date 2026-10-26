"""Freeze existing SQLite records into an offline year-by-year publication."""
import argparse
import json
import os
from pathlib import Path

from bili_rank import ROOT, Store, now, search_state

FIELDS=('bvid','title','author','pubdate','published_at','duration','play','play_source','play_at','url')


def write_json(path,data):
    path.parent.mkdir(parents=True,exist_ok=True)
    staged=path.with_suffix('.tmp')
    staged.write_text(json.dumps(data,ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(staged,path)


def build(database=ROOT/'data'/'videos.sqlite3',output=ROOT/'output'/'static',last_year=None):
    from bili_rank import dt, TZ
    last_year=last_year or dt.datetime.now(TZ).year
    timestamp=now()
    progress_path=Path(database).resolve().parent/'static_preparation.json'
    progress=json.loads(progress_path.read_text(encoding='utf-8')) if progress_path.exists() else {}
    store=Store(Path(database))
    snapshots={}
    try:
        for year in range(2009,last_year+1):
            rows=store.rows(year)
            issue=search_state(database,year)
            status='snapshot' if rows else 'pending'
            notice='固定候选快照，播放量以条目采集时间为准。'
            if not rows:notice='这一年尚无可发布的数据，待一次性整理后更新静态榜单。'
            elif issue.get('paused'):notice+=' 此前年份采集遇到限制，已保留有效结果。'
            expected=len(progress.get('terms',[]))
            completed=sum(key.startswith(f'{year}:') for key in progress.get('completed',[]))
            if rows and year in progress.get('years',[]) and completed<expected:
                status='partial'
                notice+=' 本轮整理尚未全部完成，当前显示已保存的静态结果。'
            videos=[{**{k:r[k] for k in FIELDS},'rank':i,'cover':''} for i,r in enumerate(rows,1)]
            snapshots[str(year)]={'year':year,'status':status,'snapshot_at':timestamp,
                'latest':max((r['play_at'] for r in rows),default=None),'notice':notice,
                'candidate_count':len(videos),'sitewide_complete':False,'videos':videos}
    finally:store.close()
    manifest={'version':1,'mode':'static','snapshot_at':timestamp,'default_year':2018,
        'sitewide_complete':False,'years':[{'year':s['year'],'status':s['status'],
         'count':s['candidate_count'],'latest':s['latest']} for s in reversed(list(snapshots.values()))]}
    manifest['total_candidates']=sum(y['count'] for y in manifest['years'])
    manifest['preparation']={'phase':progress.get('phase','existing_data_only'),
        'completed':len(progress.get('completed',[])),
        'total':len(progress.get('terms',[]))*len(progress.get('years',[]))}
    output=Path(output)
    for year,snapshot in snapshots.items():write_json(output/f'{year}.json',snapshot)
    write_json(output/'manifest.json',manifest)
    # Inline data blocks work directly on file://, without fetch or a server.
    payload=json.dumps({'manifest':manifest,'years':snapshots},ensure_ascii=False).replace('<','\\u003c')
    query_source=(ROOT/'integration'/'snapshot_query.js').read_text(encoding='utf-8')
    renderer=(ROOT/'integration'/'renderer.js').read_text(encoding='utf-8')
    bootstrap="""
      window.__yearRankStandalone=true;
      const frozen=JSON.parse(document.getElementById('year-rank-data').textContent);
      window.biliBridgePc={callNative:async(method,data={})=>{
        if(method==='localYearRank:hello')return {mode:'static'};
        if(method==='localYearRank:catalog')return frozen.manifest;
        if(method==='localYearRank:list'){
          const year=yearRankQuery.integer(data.year,2018,2009,9999);
          if(!frozen.years[year])throw new Error('年份不在静态目录中');
          return yearRankQuery.query(frozen.years[year],data);
        }
        throw new Error('静态榜单仅支持浏览');
      }};
    """
    page='''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
      <meta name="viewport" content="width=device-width,initial-scale=1"><title>哔哩哔哩 · 历年视频榜</title>
      <style>body{margin:0;background:#f6f7f8}#bili-local-year-rank-entry{display:none!important}</style></head>
      <body><script id="year-rank-data" type="application/json">'''+payload+'''</script>
      <script>'''+query_source+'''</script><script>'''+bootstrap+'''</script><script>'''+renderer+'''
      window.__localYearRank.open();</script></body></html>'''
    staged=output/'index.tmp'
    staged.write_text(page,encoding='utf-8')
    os.replace(staged,output/'index.html')
    lines=['# 历年视频静态候选榜','',f'整理时间：{timestamp}',
           f'共 {len(manifest["years"])} 个年份，{manifest["total_candidates"]:,} 个候选。','',
           '按各视频标注采集时间的累计播放量排序；这是候选范围内的静态快照。少于 100 条的年份按实际数量展示。','',
           '| 发布年份 | 候选数 | 最近播放量采集时间 |','|---|---:|---|']
    for item in manifest['years']:
        lines.append(f'| {item["year"]} | {item["count"]:,} | {item["latest"] or "尚无数据"} |')
    if progress:
        lines+=['',f'一次性整理状态：{manifest["preparation"]["phase"]}；固定主题已处理 '
            f'{manifest["preparation"]["completed"]}/{manifest["preparation"]["total"]}。']
        lines+=progress.get('errors',[])
    (output/'coverage.md').write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return manifest


if __name__=='__main__':
    parser=argparse.ArgumentParser(description='仅从本地数据库生成各年静态榜单，不发网络请求')
    parser.add_argument('--database',type=Path,default=ROOT/'data'/'videos.sqlite3')
    parser.add_argument('--output',type=Path,default=ROOT/'output'/'static')
    args=parser.parse_args()
    if not args.database.is_file():
        parser.error('本地数据库不存在；直接浏览已发布页面无需运行生成命令')
    result=build(args.database,args.output)
    print(json.dumps(result,ensure_ascii=False,indent=2))
