"""Compare candidate discovery before/after an expansion run; no global-recall claims."""
import argparse
import datetime as dt
import json
from pathlib import Path
import sqlite3

ROOT=Path(__file__).parent


def records(path,year):
    db=sqlite3.connect(path)
    db.row_factory=sqlite3.Row
    try:
        rows=db.execute('''SELECT *,CASE WHEN verified_at>=collected_at THEN verified_play ELSE search_play END AS play
             FROM videos WHERE year=? ORDER BY play DESC,bvid''',(year,)).fetchall()
        return [dict(r) for r in rows]
    finally:db.close()


def compare(baseline,current,year,output):
    before,after=records(baseline,year),records(current,year)
    old_ids={r['bvid'] for r in before}
    additions=[r for r in after if r['bvid'] not in old_ids]
    old_top={r['bvid'] for r in before[:100]}
    new_top=[r for r in after[:100] if r['bvid'] not in old_top]
    discovered_top=[r for r in after[:100] if r['bvid'] not in old_ids]
    runs=[]
    start=dt.datetime.fromtimestamp(Path(baseline).stat().st_mtime,dt.timezone.utc)
    for path in sorted((ROOT/'data'/'coverage_runs').glob(f'{year}_*.json')):
        meta=json.loads(path.read_text(encoding='utf-8'))
        if dt.datetime.fromisoformat(meta['started_at'])>=start:
            runs.append(meta)
    keywords={}
    recovered=[r for r in runs if r.get('provenance')=='reconstructed_from_valid_cache']
    # A recovered snapshot replaces earlier incomplete checkpoints; later runs
    # still contribute their measured incremental discoveries.
    stat_runs=runs[runs.index(recovered[-1]):] if recovered else runs
    for run in stat_runs:
        for term,stat in run.get('keyword_stats',{}).items():
            row=keywords.setdefault(term,{'keyword':term,'group':stat['group'],'pages':0,'new_candidates':0})
            row['pages']+=stat['pages'];row['new_candidates']+=stat['new_candidates']
    useful=sorted(keywords.values(),key=lambda r:(-r['new_candidates'],r['keyword']))
    result={'year':year,'baseline_count':len(before),'candidate_count':len(after),'new_candidates':len(additions),
            'growth_percent':round((len(after)-len(before))/len(before)*100,1) if before else None,
            'top100_replacements':len(new_top),'newly_discovered_top100':len(discovered_top),
            'queried_keywords':len([r for r in useful if r['pages']]),
            'provenance':'reconstructed_from_valid_cache' if recovered else 'run_checkpoints',
            'network_search_requests':None if recovered else sum((r.get('network_search_requests') or 0) for r in runs),
            'latest_run_finished':bool(runs and runs[-1].get('finished_at')),
            'latest_run_errors':runs[-1].get('errors',[]) if runs else [],
            'latest_unsearched_keywords':runs[-1].get('unsearched_keywords',[]) if runs else [],
            'new_top100_videos':discovered_top,'keyword_stats':useful,'sitewide_complete':False}
    output.mkdir(parents=True,exist_ok=True)
    stem=f'keyword_coverage_{year}'
    (output/(stem+'.json')).write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    lines=[f'# {year} 年候选覆盖扩展结果','',
           '| 指标 | 结果 |','|---|---:|',f'| 扩展前候选 | {len(before):,} |',f'| 扩展后候选 | {len(after):,} |',
           f'| 新发现候选 | {len(additions):,} |',f'| 新发现并进入候选前 100 | {len(discovered_top)} |',
           f'| {"有有效缓存的关键词（含基线）" if recovered else "已处理关键词（含缓存）"} | {result["queried_keywords"]} |','',
           '这些数字衡量本地候选集合的增长，不是全站召回率。播放量是标注采集时间的快照。','',
           '## 新增候选较多的关键词','', '| 关键词 | 分组 | 新增唯一候选 |','|---|---|---:|']
    for row in useful[:20]:
        term=row['keyword'].replace('|','\\|')
        lines.append(f'| {term} | {row["group"]} | {row["new_candidates"]} |')
    if recovered:
        lines+=['','采集进程曾中途停止，逐词增益由基线数据库与有效缓存离线回放重建；包含基线已有缓存，不代表这些词均为本轮新增联网查询。实际网络请求总数无法完整恢复。逐词新增数受回放顺序影响。']
    lines+=['','## 新发现的候选前 100 视频','']
    for row in discovered_top:
        title=row['title'].replace('[','\\[').replace(']','\\]')
        lines.append(f'- [{title}](https://www.bilibili.com/video/{row["bvid"]}) — {row["play"]:,} 次播放')
    if result['latest_run_errors']:
        lines+=['','最后一轮未完成：'+'；'.join(result['latest_run_errors'])]
    (output/(stem+'.md')).write_text('\n'.join(lines)+'\n',encoding='utf-8')
    return result


if __name__=='__main__':
    p=argparse.ArgumentParser()
    p.add_argument('--year',type=int,default=2018)
    p.add_argument('--baseline',type=Path,default=ROOT/'evidence'/'keyword_expansion'/'before.sqlite3')
    args=p.parse_args()
    result=compare(args.baseline,ROOT/'data'/'videos.sqlite3',args.year,ROOT/'output')
    print(json.dumps({k:v for k,v in result.items() if k not in ('keyword_stats','new_top100_videos','latest_unsearched_keywords')},ensure_ascii=False,indent=2))
