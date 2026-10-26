"""Year-aware, balanced query expansion; catalog + bounded public metadata seeds."""
from collections import Counter, deque
import json
import math
from pathlib import Path
import re
import unicodedata

CATALOG = json.loads((Path(__file__).parent/'keyword_catalog.json').read_text(encoding='utf-8'))


def canonical(term):
    return unicodedata.normalize('NFKC', term).strip().casefold()


def admissible(term, year):
    if not isinstance(term, str) or not 2 <= len(term.strip()) <= 40:
        return False
    if any(ord(c)<32 for c in term) or re.search(r'https?://|www\.|[<>|]',term,re.I):
        return False
    if term.strip().isdecimal() or re.fullmatch(r'bili_\d+',term.strip(),re.I):
        return False
    return not any(int(y)>year+1 for y in re.findall(r'(?<!\d)(20\d{2})(?!\d)',term))


def discovered_terms(store, year, tag_limit=12, author_limit=8, exclude=None):
    """Count each BV once; feedback is capped so one topic cannot dominate seeds."""
    if store is None:
        return []
    videos={}
    for row in store.db.execute('SELECT payload FROM pages WHERE year=? ORDER BY fetched_at',(year,)):
        for item in json.loads(row[0]).get('result',[]):
            if isinstance(item,dict) and item.get('bvid'):
                videos[item['bvid']]=item
    valid={r['bvid']:r for r in store.rows(year)}
    tag_scores=Counter()
    authors={}
    excluded=exclude or set()
    for bv,row in valid.items():
        weight=math.log10(max(1,row['play'])+1)
        raw=videos.get(bv,{})
        for tag in set(re.split('[,，、]',str(raw.get('tag') or ''))):
            tag=tag.strip()
            if admissible(tag,year) and canonical(tag) not in excluded:tag_scores[tag]+=weight
        author=row['author'].strip()
        if admissible(author,year) and canonical(author) not in excluded and author not in ('账号已注销','哔哩哔哩'):
            authors[author]=max(authors.get(author,0),row['play'])
    return ([{'keyword':term,'group':'结果标签扩展','source':'tag'} for term,_ in tag_scores.most_common(tag_limit)] +
            [{'keyword':term,'group':'作者扩展','source':'author'} for term,_ in sorted(authors.items(),key=lambda x:(-x[1],x[0]))[:author_limit]])


def build_plan(year, profile='broad', store=None):
    if profile not in ('quick','broad'):
        raise ValueError('未知关键词方案')
    groups=[]
    for name,terms in CATALOG['groups'].items():
        selected=terms if profile=='broad' else terms[:3]
        groups.append(deque({'keyword':t.format(year=year),'group':name,'source':'catalog'} for t in selected))
    for era in CATALOG['eras']:
        if era['from']<=year<=era['to']:
            terms=era['terms'] if profile=='broad' else era['terms'][:4]
            groups.append(deque({'keyword':t,'group':era['name'],'source':'era'} for t in terms))
    specific=CATALOG['year_terms'].get(str(year),[])
    groups.append(deque({'keyword':t,'group':f'{year} 年题材','source':'year'} for t in (specific if profile=='broad' else specific[:4])))
    # Round-robin serves all subjects early, even if a run is interrupted.
    result=[]
    seen=set()
    while any(groups):
        for group in groups:
            if not group:continue
            item=group.popleft()
            key=canonical(item['keyword'])
            if key and key not in seen:
                seen.add(key);result.append(item)
    if profile=='broad':
        for item in discovered_terms(store,year,exclude=seen):
            key=canonical(item['keyword'])
            if key not in seen:seen.add(key);result.append(item)
    return result


def keywords_for_year(year, profile='broad', store=None):
    return [item['keyword'] for item in build_plan(year,profile,store)]
