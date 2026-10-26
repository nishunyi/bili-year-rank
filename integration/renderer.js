(() => {
  'use strict';
  if (window.__localYearRank) { window.__localYearRank.mount(); return; }
  const pink = '#fb7299';
  const calendar = '<svg viewBox="0 0 24 24" width="23" height="23" fill="none" stroke="currentColor" stroke-width="1.7"><rect x="3" y="5" width="18" height="16" rx="4"/><path d="M7 2v6M17 2v6M3 11h18M7 15h3M14 15h3M7 18h3"/></svg>';
  const routeName='LocalYearRank';
  const routePath='/page/local-year-rank';
  let panel, shadow, entry, catalog, router, queryId = 0;
  function setSelection(active) {
    if(entry) {
      entry.classList.toggle('router-link-active',active);
      if(active) entry.setAttribute('aria-current','page'); else entry.removeAttribute('aria-current');
    }
    document.body.toggleAttribute('data-local-year-rank-active',active);
  }
  function hidePage() {
    if(panel) panel.hidden=true;
    queryId++;
    setSelection(false);
  }
  function ensureRouter() {
    const root=document.getElementById('app') || document.querySelector('[data-v-app]');
    const candidate=root?.__vue_app__?.config.globalProperties.$router;
    if(!candidate?.hasRoute?.('Page') || typeof candidate.addRoute!=='function') return false;
    if(router===candidate) return true;
    router=candidate;
    if(!router.hasRoute(routeName)) {
      const activate=function() {
        if(router.currentRoute.value.name!==routeName) return;
        showPage(this.$el?.parentElement || document.querySelector('.app_container')).catch(error);
      };
      router.addRoute('Page', {name:routeName,path:'local-year-rank',meta:{isSubPage:false},component:{
        name:routeName,render:()=>null,mounted:activate,activated:activate,
        deactivated:hidePage,beforeUnmount:hidePage
      }});
    }
    router.afterEach((to,_from,failure)=>{
      if(failure) return;
      if(to.name!==routeName) hidePage(); else setSelection(true);
    });
    if(router.currentRoute.value.path===routePath) router.replace(router.currentRoute.value.fullPath).catch(error);
    return true;
  }
  const call = (method, data = {}) => {
    if (!window.biliBridgePc?.callNative) return Promise.reject(new Error('客户端桥接尚未就绪'));
    return window.biliBridgePc.callNative('localYearRank:' + method, data);
  };
  const esc = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;'}[c]));
  const compact = count => count >= 1e8 ? (count / 1e8).toFixed(2) + '亿' : count >= 1e4 ? (count / 1e4).toFixed(1) + '万' : String(count);
  const $ = id => shadow?.getElementById(id);
  function mount() {
    if(!document.body || window.__yearRankStandalone || !ensureRouter()) return;
    const home=document.querySelector('.app_sidebar--pages-wrap a[href*="#/page/home"]');
    const row=home?.closest('li.pages-item');
    if(!row?.parentElement) return;
    if(!document.getElementById('bili-local-year-rank-style')) {
      const style=document.createElement('style'); style.id='bili-local-year-rank-style';
      style.textContent=`#bili-local-year-rank-nav .router-link{text-align:center;cursor:pointer;-webkit-app-region:no-drag}
        body[data-local-year-rank-active] .app_header--center{visibility:hidden}`;
      document.head.append(style);
    }
    if(entry?.isConnected && entry.parentElement.parentElement===row.parentElement) return;
    document.getElementById('bili-local-year-rank-nav')?.remove();
    const own=document.createElement('li'); own.id='bili-local-year-rank-nav'; own.className='pages-item';
    entry=document.createElement('a'); entry.id='bili-local-year-rank-entry';
    entry.className='router-link'; entry.href='#'+routePath; entry.title='年度榜';
    entry.innerHTML=calendar+'<p class="b_text text3">年度榜</p>';
    entry.addEventListener('click',event=>{event.preventDefault();open().catch(error);});
    own.append(entry);
    const selected=row.parentElement.querySelector('a[href*="#/page/selected"]')?.closest('li.pages-item');
    (selected || row).insertAdjacentElement('afterend',own);
    setSelection(router.currentRoute.value.name===routeName);
  }
  function createPanel(host) {
    catalog=undefined;
    panel = document.createElement('div'); panel.id = 'bili-local-year-rank-panel'; panel.hidden = true;
    panel.style.cssText='width:100%;height:100%;min-height:0;-webkit-app-region:no-drag;';
    if(window.__yearRankStandalone) panel.style.cssText+='position:fixed;inset:16px;width:auto;height:auto;';
    else panel.setAttribute('native-page','');
    shadow = panel.attachShadow({mode:'open'});
    const year = new Date().getFullYear();
    shadow.innerHTML = `<style>
      :host{font:14px/1.55 "Microsoft YaHei UI","Microsoft YaHei",sans-serif;color:#18191c;--surface:#fff;--bg:#f6f7f8;--line:#e8eaed;--text:#18191c;--muted:#9499a0;--pink:${pink};color-scheme:light}
      :host([dark]){--surface:#232428;--bg:#18191c;--line:#37383e;--text:#f1f2f3;--muted:#9a9da4;color-scheme:dark}*{box-sizing:border-box}button,input,select,textarea{font:inherit}button{cursor:pointer}button:disabled{cursor:default;opacity:.55}
      .app{height:100%;display:flex;flex-direction:column;background:var(--bg);border:1px solid var(--line);border-radius:14px;box-shadow:0 12px 40px #0002;overflow:hidden;color:var(--text)}
      header{background:var(--surface);padding:20px 24px 16px;flex:none;border-bottom:1px solid var(--line)}.top{display:flex;gap:12px;align-items:center}.mark{width:40px;height:40px;background:#fff0f5;color:var(--pink);border-radius:12px;display:grid;place-items:center}h1{font-size:23px;line-height:1.2;margin:0;font-weight:650;letter-spacing:.5px}.subtitle{font-size:12px;color:var(--muted);margin-top:5px}.spacer{flex:1}.close{border:0;background:transparent;font-size:25px;color:var(--muted);width:34px;height:34px;border-radius:8px}.close:hover{background:var(--bg)}
      :host([native-page]) .app{border:0;border-radius:0;box-shadow:none}
      .filters{display:flex;flex-wrap:wrap;align-items:end;gap:10px;margin-top:20px}label{display:block;font-size:11px;color:var(--muted)}label>span{display:block;margin:0 0 4px 2px}input,select,textarea{border:1px solid var(--line);background:var(--surface);color:var(--text);outline:none;border-radius:7px;padding:8px 10px}input:focus,select:focus,textarea:focus{border-color:var(--pink)}select{height:36px}.query{flex:1;min-width:170px}.query input{width:100%}.minimum{width:105px}.minimum input{width:100%}.primary{background:var(--pink);color:#fff;border:1px solid var(--pink);padding:8px 16px;border-radius:7px}.secondary{background:var(--surface);color:var(--text);border:1px solid var(--line);padding:8px 13px;border-radius:7px}.secondary:hover{border-color:var(--pink);color:var(--pink)}
      .scope{margin-top:13px;display:flex;gap:8px;align-items:center;color:var(--muted);font-size:11px}.badge{color:#bd7e15;background:#fff6df;border-radius:4px;padding:2px 6px;white-space:nowrap}.content{flex:1;min-height:0;overflow:auto;padding:16px 24px}.summary{display:flex;align-items:center;gap:12px;margin-bottom:13px;font-size:12px;color:var(--muted)}.summary b{font-size:18px;color:var(--text);font-weight:650}.cards{display:flex;flex-direction:column;gap:9px}.card{display:grid;grid-template-columns:32px 140px minmax(0,1fr) 114px;align-items:center;gap:14px;background:var(--surface);border:1px solid var(--line);border-radius:10px;padding:12px}.rank{text-align:center;font-size:19px;font-weight:650;color:var(--muted);font-variant-numeric:tabular-nums}.rank.top3{color:var(--pink)}.cover{width:140px;aspect-ratio:16/9;border-radius:6px;overflow:hidden;background:var(--bg);position:relative;cursor:pointer;display:grid;place-items:center;color:var(--muted)}.cover img{position:absolute;inset:0;width:100%;height:100%;object-fit:cover}.cover img[hidden]{display:none}.duration{position:absolute;right:5px;bottom:4px;background:#0009;color:white;padding:0 4px;border-radius:3px;font-size:10px}.title{border:0;background:transparent;color:var(--text);text-align:left;font-weight:550;font-size:14px;line-height:1.5;padding:0;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden}.title:hover{color:var(--pink)}.meta{margin-top:8px;font-size:11px;color:var(--muted);display:flex;flex-wrap:wrap;gap:10px}.bv{font-size:10px;color:var(--muted);margin-top:4px}.metric{text-align:right}.plays{font-size:19px;font-weight:650;letter-spacing:.2px;font-variant-numeric:tabular-nums}.metric small{display:block;color:var(--muted);font-size:10px;margin-bottom:8px}.play{border:0;background:#fff0f5;color:var(--pink);padding:5px 10px;border-radius:6px;font-size:11px}.empty{text-align:center;padding:60px 15px;color:var(--muted)}.empty strong{display:block;color:var(--text);font-size:17px;margin-bottom:9px}.hint{font-size:11px;color:var(--muted)}
      footer{border-top:1px solid var(--line);background:var(--surface);padding:10px 24px;display:flex;align-items:center;gap:12px;flex:none;font-size:11px;color:var(--muted)}.status{flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}.error{color:#d34c63}
      @media(max-width:850px){header{padding:16px}.content{padding:14px 16px}.card{grid-template-columns:25px 100px minmax(0,1fr) 83px;gap:9px;padding:10px}.cover{width:100px}.title{font-size:12px}.plays{font-size:16px}.meta{font-size:10px;gap:5px}.minimum{display:none}.scope{font-size:10px}footer{padding:9px 16px}}
    </style><div class="app"><header><div class="top"><div class="mark">${calendar}</div><div><h1>历年视频榜</h1><div class="subtitle">预先整理 · 按发布年份浏览固定榜单</div></div><div class="spacer"></div></div>
      <div class="filters"><label><span>发布年份</span><select id="year">${Array.from({length:year-2008},(_,i)=>year-i).map(y=>`<option ${y===2018?'selected':''}>${y}</option>`).join('')}</select></label><label><span>排序方式</span><select id="sort"><option value="play">累计播放量 ↓</option><option value="pubdate">最新发布 ↓</option></select></label><label><span>显示数量</span><select id="limit">${[50,100,200,500,1000].map(n=>`<option ${n===100?'selected':''}>${n}</option>`).join('')}</select></label><label class="query"><span>筛选已收录视频</span><input id="keyword" placeholder="标题 / UP 主 / BV 号"></label><label class="minimum"><span>最低播放量（万）</span><input id="minimum" type="number" min="0" value="0"></label><button id="query" class="primary">查看榜单</button></div>
      <div class="scope"><span class="badge">候选榜静态快照</span><span>播放量保留整理时的数据和采集时间；当前候选范围不能保证覆盖全站。</span></div></header>
      <section class="content"><div class="summary"><span id="summary">正在读取年度快照…</span><div class="spacer"></div><span id="updated"></span></div><div id="cards" class="cards"></div></section>
      <footer><span id="status" class="status">固定本地榜单 · 浏览无需采集</span><span id="snapshot-time"></span></footer></div>`;
    host.append(panel);
    $('query').onclick = query;
    ['sort','limit'].forEach(id => $(id).addEventListener('change', query));
    $('year').addEventListener('change', query);
    $('keyword').addEventListener('keydown', e => { if (e.key==='Enter') query(); });
    $('minimum').addEventListener('keydown', e => { if (e.key==='Enter') query(); });
    $('cards').addEventListener('error', e => {
      if(e.target.tagName==='IMG') e.target.hidden=true;
    }, true);
    $('cards').addEventListener('click', e => {
      const target = e.target.closest('[data-play]');
      if (target) play(target.dataset.play);
    });
  }
  function close() {
    if(!window.__yearRankStandalone && router?.currentRoute.value.name===routeName) {
      return router.push({name:'Home'}).catch(error);
    }
    hidePage();
  }
  async function open() {
    if(window.__yearRankStandalone) return showPage(document.body);
    mount();
    if(router) await router.push({name:routeName});
  }
  async function showPage(host) {
    if(!host) return;
    if(panel?.isConnected && !panel.hidden) return;
    if(!panel?.isConnected) createPanel(host);
    else if(panel.parentElement!==host) host.append(panel);
    panel.toggleAttribute('dark',document.documentElement.classList.contains('bili_dark') || document.body.classList.contains('bili_dark'));
    panel.hidden=false;
    if(!window.__yearRankStandalone) setSelection(true);
    try {
      if(!catalog) {
        catalog=await call('catalog');
        $('year').innerHTML=catalog.years.map(y=>`<option value="${y.year}">${y.year} · ${y.count ? y.count.toLocaleString()+' 条' : '待整理'}${y.status==='partial'?' · 部分':''}</option>`).join('');
        $('year').value=String(catalog.default_year);
        $('snapshot-time').textContent='整理于 '+catalog.snapshot_at.replace('T',' ').slice(0,16);
      }
      if(!window.__yearRankStandalone && router.currentRoute.value.name!==routeName) return;
      await query();
    } catch(e) {error(e);}
  }
  function error(e) { if ($('status')) { $('status').textContent = e?.message || String(e); $('status').classList.add('error'); } }
  async function query() {
    const requestId=++queryId;
    $('status').classList.remove('error');
    try {
      const result = await call('list', {year:Number($('year').value), limit:Number($('limit').value), keyword:$('keyword').value, minPlay:Math.round(Number($('minimum').value||0)*10000), sort:$('sort').value});
      if(requestId!==queryId)return;
      $('summary').innerHTML = `${result.year} 年 · 已整理 <b>${result.total.toLocaleString()}</b> 个候选 · 匹配 ${result.filtered.toLocaleString()} 个 · 显示 ${result.videos.length} 个`;
      $('updated').textContent = result.latest ? '采集于 ' + result.latest.replace('T',' ').slice(0,16) : '';
      $('cards').innerHTML = result.videos.length ? result.videos.map(v=>`<article class="card"><div class="rank ${v.rank<=3?'top3':''}">${v.rank}</div><div class="cover" data-play="${esc(v.bvid)}"><span aria-hidden="true">▶</span>${v.cover?`<img src="${esc(v.cover)}" alt="${esc(v.title)}" loading="lazy" decoding="async" referrerpolicy="no-referrer" width="140" height="79">`:''}<span class="duration">${esc(v.duration)}</span></div><div><button class="title" data-play="${esc(v.bvid)}">${esc(v.title)}</button><div class="meta"><span>UP ${esc(v.author)}</span><span>${esc(v.published_at.slice(0,10))}</span></div><div class="bv">${esc(v.bvid)} · ${esc(v.play_source)} · ${esc(v.play_at.replace('T',' ').slice(0,16))}</div></div><div class="metric"><div class="plays" title="${v.play.toLocaleString()} 次播放">${compact(v.play)}</div><small>累计播放</small><button class="play" data-play="${esc(v.bvid)}">▶ 播放</button></div></article>`).join('') : `<div class="empty"><strong>${result.total ? '没有匹配的视频' : '这一年尚待整理'}</strong>${result.total ? '请调整标题、UP 主或播放量筛选条件。' : '当前静态数据包尚未收录这一年的有效视频。'}</div>`;
      $('status').textContent=result.collectionNotice || '固定候选快照 · 点击播放打开视频';
    } catch(e) { if(requestId===queryId)error(e); }
  }
  async function play(bvid) {
    if (!/^BV[0-9A-Za-z]{10}$/.test(bvid)) return;
    if(window.__yearRankStandalone){window.open('https://www.bilibili.com/video/'+bvid,'_blank','noopener');return;}
    try {
      $('status').textContent = '正在打开客户端播放器…';
      await window.biliBridgePc.callNative('window/openPlayerWindow', {type:'ugc', bvid, fromSpmid:'main.search-result.0.0.pv'});
      $('status').textContent = '已请求打开播放器：' + bvid;
    } catch(e) { error(e); }
  }
  window.__localYearRank = {mount, open, close};
  const observer = new MutationObserver(mount);
  const init = () => {
    mount(); observer.observe(document.body, {childList:true, subtree:true});
    call('hello').catch(()=>{});
    document.addEventListener('keydown', e => { if(e.key==='Escape' && !window.__yearRankStandalone && panel && !panel.hidden) close(); });
  };
  if (document.body) init(); else document.addEventListener('DOMContentLoaded', init, {once:true});
})();
