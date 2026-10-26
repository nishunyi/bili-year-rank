"""Bilibili public-search collector. Python 3.10+, standard library only.

The result is a ranking of collected candidates, never a certified site-wide list.
No account cookies or installed-client files are read by this program.
"""
from __future__ import annotations

import argparse
import errno
import csv
import datetime as dt
import hashlib
import html
import http.cookiejar
import json
import os
from pathlib import Path
import re
import sqlite3
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from keyword_plan import build_plan, keywords_for_year

ROOT = Path(__file__).resolve().parent
TZ = dt.timezone(dt.timedelta(hours=8))
MIXIN = (46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52)
# Compatibility for imports; new entry points always build a plan for the selected year.
DEFAULT_KEYWORDS = tuple(keywords_for_year(2018))
BV_PATTERN = re.compile(r'BV[0-9A-Za-z]{10}\Z')


def now() -> str:
    return dt.datetime.now(TZ).isoformat(timespec='seconds')


def bounds(year: int) -> tuple[int, int]:
    if not 2009 <= year <= dt.datetime.now(TZ).year:
        raise ValueError('年份须在 2009 年至今年之间')
    return (int(dt.datetime(year, 1, 1, tzinfo=TZ).timestamp()),
            int(dt.datetime(year + 1, 1, 1, tzinfo=TZ).timestamp()))


def clean_title(value: object) -> str:
    return html.unescape(re.sub(r'<[^>]*>', '', str(value or ''))).strip()


def count(value: object) -> int | None:
    """Reject abbreviated/display-only counts rather than invent exact numbers."""
    if isinstance(value, bool):
        return None
    text = str(value).strip()
    return int(text) if re.fullmatch(r'\d+', text) else None


def normalize(item: dict, year: int) -> dict | None:
    start, end = bounds(year)
    bvid = str(item.get('bvid') or '')
    try:
        published = int(item.get('pubdate', 0))
    except (ValueError, TypeError):
        return None
    plays = count(item.get('play'))
    if not BV_PATTERN.fullmatch(bvid) or not start <= published < end or plays is None:
        return None
    return {'bvid': bvid, 'aid': count(item.get('aid')) or count(item.get('id')),
            'title': clean_title(item.get('title')), 'author': str(item.get('author') or ''),
            'pubdate': published, 'year': year, 'search_play': plays,
            'duration': str(item.get('duration') or ''), 'collected_at': now()}


def wbi_query(params: dict, key: str, timestamp: int | None = None) -> str:
    data = {**params, 'wts': int(time.time()) if timestamp is None else timestamp}
    data = {k: ''.join(c for c in str(v) if c not in "!'()*") for k, v in data.items()}
    query = urllib.parse.urlencode(sorted(data.items()), quote_via=urllib.parse.quote)
    return query + '&w_rid=' + hashlib.md5((query + key).encode()).hexdigest()


class ApiError(RuntimeError):
    pass


class RiskStop(ApiError):
    pass


class Cancelled(RuntimeError):
    pass


def validate_search_page(data):
    if isinstance(data,dict) and data.get('v_voucher'):
        raise RiskStop('服务器返回风控校验凭据（v_voucher），本轮已停止；不将其视为零结果')
    if (isinstance(data,dict) and 'result' not in data
        and type(data.get('numResults')) is int and data['numResults']==0
        and type(data.get('numPages')) is int and data['numPages']==0):
        # A real zero-hit response can omit result while retaining both counters.
        return {**data,'result':[],'empty_result_normalized':True}
    if not isinstance(data,dict) or not isinstance(data.get('result'),list):
        raise ApiError('搜索响应缺少结果列表，不能将该响应解释为零结果')
    return data


class Client:
    def __init__(self, interval: float = 5, cancel: threading.Event | None = None):
        self.interval = max(2.0, interval)
        self.cancel = cancel or threading.Event()
        self.last_request = 0.0
        self.opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(http.cookiejar.CookieJar()))
        self.key: str | None = None
        self.transport_retries = 0

    def get(self, path: str, params: dict | None = None, signed: bool = False) -> dict:
        if signed and self.key is None:
            nav = self.get('/x/web-interface/nav')
            images = (nav.get('data') or {}).get('wbi_img') or {}
            try:
                origin = ''.join(images[k].rsplit('/', 1)[-1].split('.')[0] for k in ('img_url', 'sub_url'))
                self.key = ''.join(origin[i] for i in MIXIN)[:32]
            except (KeyError, IndexError, TypeError) as error:
                raise ApiError('无法获取公开 WBI 参数') from error
        delay = max(0, self.interval - (time.monotonic() - self.last_request))
        if self.cancel.wait(delay):
            raise Cancelled('已停止，已采集的数据保存在本地')
        query = wbi_query(params or {}, self.key) if signed else urllib.parse.urlencode(params or {})
        url = 'https://api.bilibili.com' + path + ('?' + query if query else '')
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36',
                   'Referer': 'https://search.bilibili.com/'}
        for attempt in range(2):
            self.last_request = time.monotonic()
            try:
                with self.opener.open(urllib.request.Request(url, headers=headers), timeout=20) as response:
                    payload = json.load(response)
                break
            except urllib.error.HTTPError as error:
                if error.code in (403, 412, 429):
                    raise RiskStop(f'服务器返回 HTTP {error.code}，本轮已停止；未自动重试') from error
                raise ApiError(f'HTTP {error.code}') from error
            except (urllib.error.URLError,OSError,json.JSONDecodeError) as error:
                reason=getattr(error,'reason',error)
                transient=isinstance(reason,(TimeoutError,ConnectionResetError)) or getattr(reason,'errno',None) in (errno.ECONNRESET,errno.ETIMEDOUT,10054,10060) or getattr(reason,'winerror',None) in (10054,10060)
                if attempt==0 and transient:
                    self.transport_retries+=1
                    if self.cancel.wait(max(5,self.interval)):
                        raise Cancelled('已停止，已采集的数据保存在本地')
                    continue
                raise ApiError(f'网络或响应错误：{error}') from error
        if not isinstance(payload,dict):
            raise ApiError('接口响应格式无效')
        code = payload.get('code', 0)
        if isinstance(payload.get('data'),dict) and payload['data'].get('v_voucher'):
            raise RiskStop('服务器返回风控校验凭据（v_voucher），本轮已停止；未自动重试')
        if code in (-352, -412, -1200):
            raise RiskStop(f'服务器返回 {code}：{payload.get("message", "请求受限")}，本轮已停止')
        if code != 0 and not (path.endswith('/nav') and code == -101):
            raise ApiError(f'接口返回 {code}：{payload.get("message", "未知错误")}')
        return payload

    def search(self, keyword: str, year: int, page: int, page_size: int) -> dict:
        if not keyword.strip():
            raise ValueError('搜索接口需要关键词，不能用空关键词代表全站')
        start, end = bounds(year)
        params = {'search_type': 'video', 'keyword': keyword.strip(), 'order': 'click',
                  'page': page, 'page_size': page_size,
                  'pubtime_begin_s': start, 'pubtime_end_s': end - 1}
        return validate_search_page(self.get('/x/web-interface/wbi/search/type', params, signed=True).get('data'))

    def stats(self, bvid: str) -> dict:
        if not BV_PATTERN.fullmatch(bvid):
            raise ValueError('BV 号格式错误')
        return self.get('/x/web-interface/archive/stat', {'bvid': bvid})['data']


class Store:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path)
        self.db.row_factory = sqlite3.Row
        self.db.executescript('''
        CREATE TABLE IF NOT EXISTS videos (
            bvid TEXT PRIMARY KEY, aid INTEGER, title TEXT, author TEXT, pubdate INTEGER,
            year INTEGER, search_play INTEGER, duration TEXT, collected_at TEXT,
            verified_play INTEGER, verified_at TEXT);
        CREATE TABLE IF NOT EXISTS hits (
            bvid TEXT, year INTEGER, keyword TEXT, PRIMARY KEY (bvid,year,keyword));
        CREATE TABLE IF NOT EXISTS pages (
            year INTEGER, keyword TEXT, page INTEGER, page_size INTEGER,
            fetched_at REAL, payload TEXT, PRIMARY KEY(year,keyword,page,page_size));
        ''')

    def close(self):
        self.db.close()

    def cached_page(self, year: int, keyword: str, page: int, size: int, hours: float) -> dict | None:
        row = self.db.execute('SELECT fetched_at,payload FROM pages WHERE year=? AND keyword=? AND page=? AND page_size=?', (year, keyword, page, size)).fetchone()
        if row and time.time() - row['fetched_at'] < hours * 3600:
            return validate_search_page(json.loads(row['payload']))
        return None

    def save_page(self, year: int, keyword: str, page: int, size: int, payload: dict):
        payload=validate_search_page(payload)
        self.db.execute('INSERT OR REPLACE INTO pages VALUES(?,?,?,?,?,?)', (year, keyword, page, size, time.time(), json.dumps(payload, ensure_ascii=False)))
        self.db.commit()

    def page_time(self, year, keyword, page, size):
        row = self.db.execute('SELECT fetched_at FROM pages WHERE year=? AND keyword=? AND page=? AND page_size=?', (year,keyword,page,size)).fetchone()
        return dt.datetime.fromtimestamp(row[0],TZ).isoformat(timespec='seconds') if row else now()

    def cutoff(self, year, top_k):
        start,end=bounds(year)
        row=self.db.execute('''SELECT CASE WHEN verified_at>=collected_at THEN verified_play ELSE search_play END AS play
            FROM videos WHERE pubdate>=? AND pubdate<? ORDER BY play DESC,bvid LIMIT 1 OFFSET ?''',(start,end,top_k-1)).fetchone()
        return row[0] if row else None

    def ingest(self, items: list, year: int, keyword: str, collected_at: str | None = None) -> tuple[int, int]:
        accepted = rejected = 0
        for item in items:
            record = normalize(item, year)
            if record is None:
                rejected += 1
                continue
            if collected_at is not None:
                record['collected_at']=collected_at
            self.db.execute('''INSERT INTO videos(bvid,aid,title,author,pubdate,year,search_play,duration,collected_at)
                VALUES(:bvid,:aid,:title,:author,:pubdate,:year,:search_play,:duration,:collected_at)
                ON CONFLICT(bvid) DO UPDATE SET aid=excluded.aid,title=excluded.title,author=excluded.author,
                pubdate=excluded.pubdate,year=excluded.year,search_play=excluded.search_play,
                duration=excluded.duration,collected_at=excluded.collected_at
                WHERE excluded.collected_at>=videos.collected_at''', record)
            self.db.execute('INSERT OR IGNORE INTO hits VALUES(?,?,?)', (record['bvid'], year, keyword))
            accepted += 1
        self.db.commit()
        return accepted, rejected

    def rows(self, year: int) -> list[dict]:
        start, end = bounds(year)
        rows = self.db.execute('''SELECT *,
            CASE WHEN verified_at >= collected_at THEN verified_play ELSE search_play END AS play,
            CASE WHEN verified_at >= collected_at THEN '统计接口' ELSE '搜索接口' END AS play_source,
            CASE WHEN verified_at >= collected_at THEN verified_at ELSE collected_at END AS play_at
            FROM videos WHERE pubdate>=? AND pubdate<? ORDER BY play DESC,bvid''', (start, end)).fetchall()
        output = []
        for row in rows:
            item = dict(row)
            item['published_at'] = dt.datetime.fromtimestamp(row['pubdate'], TZ).strftime('%Y-%m-%d %H:%M:%S')
            item['url'] = 'https://www.bilibili.com/video/' + item['bvid']
            item['keywords'] = '、'.join(x[0] for x in self.db.execute('SELECT keyword FROM hits WHERE bvid=? AND year=? ORDER BY keyword', (item['bvid'], year)))
            output.append(item)
        return output

    def verify(self, bvid: str, stats: dict):
        plays = count(stats.get('view'))
        if plays is None:
            raise ApiError(f'{bvid} 的播放量不可用')
        self.db.execute('UPDATE videos SET verified_play=?,verified_at=? WHERE bvid=?', (plays, now(), bvid))
        self.db.commit()


def collect(client: Client, store: Store, year: int, keywords: list[str], pages: int, page_size: int, cache_hours: float, log=print, meta: dict | None = None, *, adaptive=False, top_k=100, request_budget=0, plan=None, cache_only=False, checkpoint=None) -> dict:
    if meta is None:
        meta = {}
    baseline=store.rows(year)
    seen={r['bvid'] for r in baseline}
    info={item['keyword']:item for item in (plan or [])}
    terms=list(dict.fromkeys(k.strip() for k in keywords if k.strip()))
    meta.update({'year': year, 'started_at': now(), 'scope': 'collected_candidates', 'sitewide_complete': False,
                 'keywords': terms, 'pages': [], 'rejected_rows': 0, 'errors': [],
                 'strategy':'breadth_first', 'adaptive_top_k':top_k if adaptive else None,
                 'request_budget':request_budget, 'network_search_requests':0,
                 'run_mode':'cache_only' if cache_only else 'online',
                 'baseline_candidates':len(baseline), 'baseline_top100':[r['bvid'] for r in baseline[:100]],
                 'new_candidate_ids':[], 'keyword_stats':{k:{'group':info.get(k,{}).get('group','自定义'),
                    'source':info.get(k,{}).get('source','custom'),'pages':0,'new_candidates':0,
                    'accepted':0,'stop_reason':None} for k in terms}})
    states={k:{'fingerprints':set(),'ordered':True,'tail':None} for k in terms}
    active=list(terms)
    # Visit every subject's first page before spending budget on deeper pages.
    for page in range(1,pages+1):
        if page>1:
            active.sort(key=lambda k:-(states[k]['tail'] or 0))
        next_active=[]
        for keyword in active:
            if client.cancel.is_set():
                raise Cancelled('已停止，已采集的数据保存在本地')
            data = store.cached_page(year, keyword, page, page_size, cache_hours)
            cached = data is not None
            stat=meta['keyword_stats'][keyword]
            if data is None:
                if cache_only:
                    stat['stop_reason']='cache_only'
                    continue
                if request_budget and meta['network_search_requests']>=request_budget:
                    stat['stop_reason']='request_budget'
                    meta['budget_limited']=True
                    continue
                meta['last_request']={'keyword':keyword,'page':page}
                meta['network_search_requests']+=1
                if checkpoint:checkpoint()
                data = client.search(keyword, year, page, page_size)
                store.save_page(year, keyword, page, page_size, data)
            items = [x for x in data.get('result', []) if isinstance(x, dict) and x.get('type', 'video') == 'video']
            fingerprint = tuple(x.get('bvid') for x in items)
            state=states[keyword]
            if fingerprint and fingerprint in state['fingerprints']:
                log(f'「{keyword}」第 {page} 页重复，停止该关键词')
                stat['stop_reason']='repeated_page'
                continue
            state['fingerprints'].add(fingerprint)
            valid=[r for item in items if (r:=normalize(item,year)) is not None]
            new_ids={r['bvid'] for r in valid}-seen
            seen.update(new_ids)
            meta['new_candidate_ids'].extend(sorted(new_ids))
            accepted, rejected = store.ingest(items, year, keyword,store.page_time(year,keyword,page,page_size))
            meta['rejected_rows'] += rejected
            stat['pages']+=1;stat['accepted']+=accepted;stat['new_candidates']+=len(new_ids)
            meta['pages'].append({'keyword': keyword, 'page': page, 'items': len(items), 'accepted': accepted,
                                  'new_candidates':len(new_ids),'numResults': data.get('numResults'),
                                  'numPages': data.get('numPages'), 'cached': cached})
            log(f'[{page}/{pages}]「{keyword}」：接收 {accepted}，新增 {len(new_ids)}，累计 {len(seen)}' + ('（缓存）' if cached else ''))
            if checkpoint:checkpoint()
            if not items or (data.get('numPages') is not None and page >= int(data['numPages'])):
                stat['stop_reason']='last_page'
                continue
            plays=[r['search_play'] for r in valid]
            ordered=all(a>=b for a,b in zip(plays,plays[1:]))
            if state['tail'] is not None and plays and plays[0]>state['tail']:
                ordered=False
            state['ordered']=state['ordered'] and ordered
            state['tail']=plays[-1] if plays else None
            cutoff=store.cutoff(year,top_k) if adaptive else None
            # A heuristic, not proof: unstable ordering disables this optimization.
            if adaptive and len(valid)==len(items) and plays and state['ordered'] and cutoff is not None and plays[-1]<cutoff:
                stat['stop_reason']='below_top_k_threshold'
                stat['threshold']=cutoff
                continue
            stat['stop_reason']='page_limit' if page==pages else None
            next_active.append(keyword)
        active=next_active
        if not active:break
    meta['finished_at'] = now()
    return meta


def coverage_summary(store,year,meta):
    rows=store.rows(year)
    new_ids=set(meta.get('new_candidate_ids',[]))
    top_ids={r['bvid'] for r in rows[:100]}
    meta.update({'candidate_count':len(rows),'new_candidates':len(new_ids),
                 'top100_replacements':len(top_ids-set(meta.get('baseline_top100',top_ids))),
                 'newly_discovered_top100':len(top_ids&new_ids),
                 'queried_keywords':sum(s['pages']>0 for s in meta.get('keyword_stats',{}).values()),
                 'unsearched_keywords':[k for k,s in meta.get('keyword_stats',{}).items() if not s['pages']]})
    return meta


def search_states(database):
    path=Path(database).resolve().parent/'search_state.json'
    try:
        data=json.loads(path.read_text(encoding='utf-8'))
    except (FileNotFoundError,json.JSONDecodeError):
        return {}
    if not isinstance(data,dict):return {}
    if isinstance(data.get('years'),dict):return data['years']
    # Read the original single-year state without losing it on the next write.
    return {str(data['year']):data} if 'year' in data else {}


def search_state(database,year):
    state=search_states(database).get(str(year),{})
    return state if isinstance(state,dict) else {}


def update_search_state(database,year,meta):
    if meta.get('paused_reason')=='risk_control':
        state={'year':year,'paused':True,'reason':'risk_control','at':now(),
               'message':'本轮采集遇到服务器风控，网络请求已暂停。已获得的候选可继续离线浏览；部分关键词或后续页尚待恢复。'}
    elif (meta.get('run_mode')=='online' and meta.get('network_search_requests',0)>0
          and meta.get('finished_at') and not meta.get('errors')):
        state={'year':year,'paused':False,'at':now()}
    else:
        # Cached responses and exports do not demonstrate that service resumed.
        return
    states=search_states(database)
    states[str(year)]=state
    path=Path(database).resolve().parent/'search_state.json'
    staged=path.with_suffix('.tmp')
    staged.write_text(json.dumps({'years':states},ensure_ascii=False,indent=2),encoding='utf-8')
    os.replace(staged,path)


def csv_safe(value: object) -> object:
    if isinstance(value, str) and value.lstrip().startswith(('=', '+', '-', '@')):
        return "'" + value
    return value


def export(store: Store, year: int, limit: int, meta: dict, output: Path) -> tuple[Path, Path]:
    output.mkdir(parents=True, exist_ok=True)
    all_rows = store.rows(year)
    rows = all_rows[:limit]
    meta = {**meta, 'exported_at': now(), 'candidate_count': len(all_rows), 'exported_count': len(rows),
            'sitewide_complete': False, 'scope': 'collected_candidates',
            'all_keywords_in_database': [r[0] for r in store.db.execute('SELECT DISTINCT keyword FROM hits WHERE year=? ORDER BY keyword', (year,))]}
    stem = f'bilibili_{year}_candidates'
    csv_path, html_path = output / (stem + '.csv'), output / (stem + '.html')
    with csv_path.open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.writer(stream)
        writer.writerow(['候选排名', '标题', 'UP主', '发布时间(北京时间)', '播放量', '数据来源', '播放量采集时间', 'BV号', '链接', '命中关键词'])
        for index, row in enumerate(rows, 1):
            writer.writerow([csv_safe(v) for v in (index, row['title'], row['author'], row['published_at'], row['play'], row['play_source'], row['play_at'], row['bvid'], row['url'], row['keywords'])])
    body = []
    for index, row in enumerate(rows, 1):
        esc = lambda name: html.escape(str(row[name]), quote=True)
        body.append(f'<tr><td>{index}</td><td><a href="{esc("url")}" target="_blank" rel="noopener noreferrer">{esc("title")}</a><small>{esc("bvid")} · {esc("keywords")}</small></td><td>{esc("author")}</td><td>{esc("published_at")}</td><td class="number">{row["play"]:,}</td><td>{esc("play_source")}<small>{esc("play_at")}</small></td></tr>')
    page = '''<!doctype html><html lang="zh-CN"><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
    <title>YEAR 年视频候选播放榜</title><style>body{font:15px/1.65 'Microsoft YaHei',sans-serif;background:#f5f7fa;color:#243042;margin:0;padding:36px}main{max-width:1400px;margin:auto}h1{margin-bottom:8px}p{max-width:1000px}.notice{padding:18px 22px;background:#fff5dc;border:1px solid #e7cc91;border-radius:12px;margin:22px 0}table{border-collapse:collapse;background:white;width:100%;border-radius:10px}th,td{padding:14px;text-align:left;border-bottom:1px solid #e9edf2;vertical-align:top}th{background:#eaf0f6;position:sticky;top:0}a{color:#006b94;text-decoration:none}a:hover{text-decoration:underline}small{display:block;font-size:12px;color:#748092;margin-top:5px}.number{font-variant-numeric:tabular-nums;white-space:nowrap;font-weight:bold}footer{color:#748092;padding:24px 0}input{padding:10px 14px;border:1px solid #c7d0db;border-radius:8px;width:320px;margin-bottom:16px}</style>
    <main><h1>YEAR 年发布视频 · 候选播放榜</h1><p>按采集到的播放量降序排列。共 CANDIDATES 个候选，显示前 EXPORTED 个。</p><div class="notice"><b>这是已采集候选中的排名，不能据此认定为全站前 100。</b><br>搜索接口需要关键词，存在检索与分页限制。发布时间在本地再次校验；每条播放量的数据来源和采集时间见表。未完成统计核验的行采用搜索接口返回值。<p>RUNNOTICE</p><details><summary>展开本地索引累计命中关键词</summary>KEYWORDS</details></div>
    <input id="filter" placeholder="在本页筛选标题、UP 主或 BV 号" aria-label="筛选结果"><div style="overflow:auto"><table><thead><tr><th>候选排名</th><th>视频</th><th>UP 主</th><th>发布时间</th><th>播放量</th><th>来源 / 采集时间</th></tr></thead><tbody>ROWS</tbody></table></div><footer>导出时间：EXPORTEDAT（北京时间）。这是静态快照，重新采集后才会更新。</footer></main><script>document.getElementById('filter').addEventListener('input',e=>{const q=e.target.value.toLowerCase();document.querySelectorAll('tbody tr').forEach(r=>r.hidden=!r.textContent.toLowerCase().includes(q));});</script></html>'''
    # Substitute the template once, so video titles cannot become template tokens.
    notice=''
    if meta.get('paused_reason')=='risk_control':
        notice='本轮网络采集因服务器风控暂停；部分关键词尚未完成。此表仅使用已经取得的有效视频数据。'
    elif meta.get('run_mode')=='cache_only':notice='本次为离线缓存汇总，未发起网络请求。'
    elif meta.get('budget_limited'):notice='本轮达到搜索页请求预算，尚有部分关键词或后续页未完成。'
    elif meta.get('errors'):notice='本轮采集未完整完成：'+'；'.join(meta['errors'])
    replacements = {'YEAR': str(year), 'CANDIDATES': str(len(all_rows)), 'EXPORTED': str(len(rows)),
                    'KEYWORDS': html.escape('、'.join(meta['all_keywords_in_database'])),
                    'RUNNOTICE':html.escape(notice),
                    'ROWS': ''.join(body), 'EXPORTEDAT': html.escape(meta['exported_at'])}
    page = re.sub(r'EXPORTEDAT|CANDIDATES|KEYWORDS|RUNNOTICE|EXPORTED|ROWS|YEAR', lambda m: replacements[m.group()], page)
    html_path.write_text(page, encoding='utf-8')
    (output / (stem + '.json')).write_text(json.dumps({'metadata': meta, 'videos': rows}, ensure_ascii=False, indent=2), encoding='utf-8')
    return csv_path, html_path


def run(args, log=print, cancel: threading.Event | None = None) -> tuple[Path, Path]:
    bounds(args.year)
    client = Client(args.interval, cancel)
    store = Store(Path(args.database))
    plan=build_plan(args.year,getattr(args,'keyword_profile','broad'),store)
    keywords = args.keywords or [item['keyword'] for item in plan]
    meta = {'year': args.year, 'started_at': now(), 'keywords': keywords, 'errors': []}
    run_dir=ROOT/'data'/'coverage_runs'
    stamp=dt.datetime.now(TZ).strftime('%Y%m%d_%H%M%S_%f')
    run_path=run_dir/f'{args.year}_{stamp}.json'
    def checkpoint():
        run_dir.mkdir(parents=True,exist_ok=True)
        meta['checkpoint_at']=now()
        staged=run_path.with_suffix('.tmp')
        staged.write_text(json.dumps(meta,ensure_ascii=False,indent=2),encoding='utf-8')
        os.replace(staged,run_path)
    try:
        if not args.export_only:
            collect(client, store, args.year, keywords, args.pages, args.page_size, args.cache_hours, log, meta,
                    adaptive=not getattr(args,'full_depth',False),top_k=args.limit,
                    request_budget=getattr(args,'request_budget',0),plan=plan,
                    cache_only=getattr(args,'cache_only',False),checkpoint=checkpoint)
            if args.refresh_stats and not getattr(args,'cache_only',False):
                rows = store.rows(args.year)
                log(f'逐条核验全部 {len(rows)} 个候选的统计数据')
                for index, row in enumerate(rows, 1):
                    if client.cancel.is_set():
                        raise Cancelled('已停止，已采集的数据保存在本地')
                    store.verify(row['bvid'], client.stats(row['bvid']))
                    log(f'核验 {index}/{len(rows)}：{row["bvid"]}')
    except (ApiError, Cancelled) as error:
        meta.setdefault('errors', []).append(str(error))
        meta['stopped_at'] = now()
        if isinstance(error,RiskStop):
            meta['paused_reason']='risk_control'
            last=meta.get('last_request',{})
            if last.get('keyword') in meta.get('keyword_stats',{}):
                meta['keyword_stats'][last['keyword']]['stop_reason']='risk_control'
        log(str(error))
    finally:
        try:
            if not args.export_only:
                meta['transport_retries']=getattr(client,'transport_retries',0)
                coverage_summary(store,args.year,meta)
                update_search_state(args.database,args.year,meta)
                checkpoint()
            issue=search_state(args.database,args.year)
            if issue.get('paused'):
                meta['paused_reason']=issue.get('reason','risk_control')
                meta['collection_notice']=issue.get('message')
            paths = export(store, args.year, args.limit, meta, Path(args.output))
        finally:
            store.close()
    log(f'已导出：{paths[0]}')
    log(f'可浏览报告：{paths[1]}')
    return paths


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description='B 站按发布年份收集候选视频并按播放量排序；不保证全站完整性')
    p.add_argument('--year', type=int, default=2018)
    p.add_argument('--keywords', nargs='+', help='自定义关键词；留空时按所选年份生成分组词库与有限补词')
    p.add_argument('--keyword-profile', choices=['quick','broad'],default='broad')
    p.add_argument('--full-depth',action='store_true',help='不使用前 K 名播放量阈值裁剪，翻至每词页数上限')
    p.add_argument('--request-budget',type=int,default=80,help='本轮最多请求的搜索页数；默认 80，0 为不额外限制，缓存不计入')
    p.add_argument('--cache-only',action='store_true',help='仅汇总已有有效缓存，不发起网络请求')
    p.add_argument('--pages', type=int, choices=range(1, 101), default=2, metavar='1..100')
    p.add_argument('--page-size', type=int, choices=range(1, 51), default=30, metavar='1..50')
    p.add_argument('--limit', type=int, default=100)
    p.add_argument('--interval', type=float, default=5, help='请求间隔秒数，默认 5，最小 2 秒')
    p.add_argument('--cache-hours', type=float, default=6)
    p.add_argument('--refresh-stats', action='store_true', help='逐条请求统计接口；遇到限制会停止并导出已完成数据')
    p.add_argument('--export-only', action='store_true')
    p.add_argument('--database', default=str(ROOT / 'data' / 'videos.sqlite3'))
    p.add_argument('--output', default=str(ROOT / 'output'))
    return p


if __name__ == '__main__':
    arguments = parser().parse_args()
    if arguments.limit <= 0:
        raise SystemExit('--limit 必须大于 0')
    run(arguments, lambda message: print(message, flush=True))
