"""Private JSON-lines worker for the desktop integration (no listening socket)."""
from __future__ import annotations
import json
from pathlib import Path
import sys
import threading
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import bili_rank

lock = threading.Lock()
cancel = threading.Event()
thread: threading.Thread | None = None
state = {'running': False, 'phase': 'idle', 'logs': [], 'message': '准备就绪'}


def integer(data, name, default, low, high):
    value = data.get(name, default)
    if isinstance(value, bool) or not isinstance(value, int) or not low <= value <= high:
        raise ValueError(f'{name} 参数无效')
    return value


def list_records(data):
    year = integer(data, 'year', 2018, 2009, bili_rank.dt.datetime.now(bili_rank.TZ).year)
    limit = integer(data, 'limit', 100, 1, 1000)
    minimum = integer(data, 'minPlay', 0, 0, 10**12)
    keyword = str(data.get('keyword', '')).strip()[:100].casefold()
    sort = data.get('sort', 'play')
    if sort not in ('play', 'pubdate'):
        raise ValueError('排序参数无效')
    store = bili_rank.Store(ROOT / 'data' / 'videos.sqlite3')
    try:
        rows = store.rows(year)
        total = len(rows)
        years = [r[0] for r in store.db.execute('SELECT DISTINCT year FROM videos ORDER BY year DESC')]
        cover = {}
        for row in store.db.execute('SELECT payload FROM pages WHERE year=? ORDER BY fetched_at', (year,)):
            for item in json.loads(row[0]).get('result', []):
                pic = item.get('pic', '')
                if pic.startswith('//'):
                    pic = 'https:' + pic
                if pic.startswith(('https://i0.hdslb.com/', 'https://i1.hdslb.com/', 'https://i2.hdslb.com/')):
                    cover[item.get('bvid')] = pic
        if keyword:
            rows = [r for r in rows if keyword in (r['title'] + ' ' + r['author'] + ' ' + r['bvid']).casefold()]
        rows = [r for r in rows if r['play'] >= minimum]
        if sort == 'pubdate':
            rows.sort(key=lambda r: (r['pubdate'], r['bvid']), reverse=True)
        filtered = len(rows)
        latest = max((r['play_at'] for r in rows), default=None)
        records = [{**r, 'rank': index, 'cover': cover.get(r['bvid'], '')} for index, r in enumerate(rows[:limit], 1)]
        issue=bili_rank.search_state(ROOT/'data'/'videos.sqlite3',year)
        return {'year': year, 'total': total, 'filtered': filtered, 'latest': latest,
                'years': years, 'videos': records, 'scope': 'candidates', 'sitewideComplete': False,
                'collectionNotice':issue.get('message') if issue.get('paused') else None}
    finally:
        store.close()


def update(message):
    with lock:
        state['message'] = str(message)
        state['logs'] = (state['logs'] + [str(message)])[-60:]


def keyword_plan(data):
    year=integer(data,'year',2018,2009,bili_rank.dt.datetime.now(bili_rank.TZ).year)
    profile=data.get('profile','broad')
    store=bili_rank.Store(ROOT/'data'/'videos.sqlite3')
    try:
        plan=bili_rank.build_plan(year,profile,store)
        return {'year':year,'profile':profile,'keywords':[p['keyword'] for p in plan],
                'count':len(plan),'groups':len({p['group'] for p in plan}),'plan':plan}
    finally:store.close()


def start_job(data):
    global thread, cancel
    year = integer(data, 'year', 2018, 2009, bili_rank.dt.datetime.now(bili_rank.TZ).year)
    pages = integer(data, 'pages', 2, 1, 10)
    profile=data.get('profile','broad')
    if profile not in ('quick','broad'):raise ValueError('未知关键词方案')
    keywords = data.get('keywords')
    if keywords is not None and (not isinstance(keywords, list) or not 1 <= len(keywords) <= 250 or any(not isinstance(k, str) or not k.strip() or len(k) > 80 for k in keywords)):
        raise ValueError('请输入 1—250 个关键词，每词不超过 80 字')
    with lock:
        if state['running']:
            raise ValueError('已有采集任务正在运行')
        cancel = threading.Event()
        state.update({'running': True, 'phase': 'collecting', 'year': year,
                      'message': '正在准备采集', 'logs': [], 'startedAt': bili_rank.now()})

    def work():
        try:
            args = bili_rank.parser().parse_args([])
            args.year, args.pages, args.keywords = year, pages, keywords
            args.keyword_profile=profile
            args.request_budget=80
            args.refresh_stats = False  # Known-unavailable legacy stats route is not exposed.
            paths = bili_rank.run(args, update, cancel)
            metadata = json.loads(paths[1].with_suffix('.json').read_text(encoding='utf-8'))['metadata']
            with lock:
                state['phase'] = 'stopped' if metadata.get('errors') else 'completed'
                state['message'] = metadata.get('errors', [None])[0] if metadata.get('errors') else f'采集完成：{metadata["candidate_count"]} 个候选，本轮新增 {metadata.get("new_candidates",0)} 个'
                state['finishedAt'] = bili_rank.now()
        except Exception as error:
            with lock:
                state.update({'phase': 'failed', 'message': str(error)})
        finally:
            with lock:
                state['running'] = False
    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    return {'started': True}


def dispatch(method, data):
    if not isinstance(data, dict):
        raise ValueError('请求必须为对象')
    if method == 'list':
        return list_records(data)
    if method == 'plan':
        return keyword_plan(data)
    if method == 'start':
        return start_job(data)
    if method == 'status':
        with lock:
            return dict(state)
    if method == 'cancel':
        cancel.set()
        return {'cancelled': True}
    raise ValueError('未知方法')


def main():
    for line in sys.stdin:
        request = {}
        try:
            if len(line) > 64_000:
                raise ValueError('请求过长')
            request = json.loads(line)
            result = dispatch(request.get('method'), request.get('data', {}))
            response = {'id': request.get('id'), 'result': result}
        except Exception as error:
            response = {'id': request.get('id'), 'error': str(error)}
        print(json.dumps(response, ensure_ascii=False), flush=True)
    cancel.set()
    if thread and thread.is_alive():
        thread.join(timeout=22)


if __name__ == '__main__':
    main()
