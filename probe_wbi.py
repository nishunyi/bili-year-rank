"""Small anonymous protocol probe; stores public responses only."""
import datetime as dt
import hashlib
import http.cookiejar
import json
from pathlib import Path
import time
import urllib.error
import urllib.parse
import urllib.request

MIXIN = [46,47,18,2,53,8,23,32,15,50,10,31,58,3,45,35,27,43,5,49,33,9,42,19,29,28,14,39,12,38,41,13,37,48,7,16,24,55,40,61,26,17,0,1,60,51,30,4,22,25,54,21,56,59,6,63,57,62,11,36,20,34,44,52]
jar = http.cookiejar.CookieJar()
opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(jar))
headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36", "Referer": "https://search.bilibili.com/"}
out = Path(__file__).parent / "evidence"
out.mkdir(exist_ok=True)

def get(url):
    with opener.open(urllib.request.Request(url, headers=headers), timeout=20) as r:
        return json.load(r)

nav = get("https://api.bilibili.com/x/web-interface/nav")
wbi = nav["data"]["wbi_img"]
origin = "".join(wbi[k].rsplit("/", 1)[-1].split(".")[0] for k in ("img_url", "sub_url"))
key = "".join(origin[i] for i in MIXIN)[:32]
time.sleep(3)
tz = dt.timezone(dt.timedelta(hours=8))
start = int(dt.datetime(2018, 1, 1, tzinfo=tz).timestamp())
end = int(dt.datetime(2019, 1, 1, tzinfo=tz).timestamp()) - 1
cases = [
    ("signed-2018", {"keyword": "2018"}),
    ("signed-dated-2018", {"keyword": "2018", "pubtime_begin_s": start, "pubtime_end_s": end}),
    ("signed-dated-empty", {"keyword": "", "pubtime_begin_s": start, "pubtime_end_s": end}),
    ("signed-dated-tutorial", {"keyword": "教程", "pubtime_begin_s": start, "pubtime_end_s": end}),
]
for name, extra in cases:
    params = {"search_type": "video", "order": "click", "page": 1, "page_size": 10, **extra, "wts": int(time.time())}
    params = {k: "".join(c for c in str(v) if c not in "!'()*") for k, v in params.items()}
    query = urllib.parse.urlencode(sorted(params.items()), quote_via=urllib.parse.quote)
    url = "https://api.bilibili.com/x/web-interface/wbi/search/type?" + query + "&w_rid=" + hashlib.md5((query + key).encode()).hexdigest()
    try:
        response = get(url)
    except urllib.error.HTTPError as e:
        print(name, "HTTP", e.code, flush=True)
        if e.code in (412, 429):
            print("Stopped on server rate/risk response.", flush=True)
            break
        continue
    (out / (name + ".json")).write_text(json.dumps({"params": extra, "response": response}, ensure_ascii=False, indent=2), encoding="utf-8")
    data = response.get("data") or {}
    print(name, response.get("code"), response.get("message"), "total", data.get("numResults"), "pages", data.get("numPages"), flush=True)
    for x in (data.get("result") or [])[:3]:
        print(x.get("bvid"), dt.datetime.fromtimestamp(x.get("pubdate", 0), tz).isoformat(), x.get("play"), x.get("title"), flush=True)
    if response.get("code") in (-352, -412, -1200):
        print("Stopped on server risk response.", flush=True)
        break
    time.sleep(3)
