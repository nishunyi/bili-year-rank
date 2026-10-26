(function(root) {
  'use strict';
  function integer(value, fallback, low, high) {
    value = value === undefined ? fallback : value;
    if (!Number.isSafeInteger(value) || value < low || value > high) throw new Error('筛选参数无效');
    return value;
  }
  function query(snapshot, data = {}) {
    const limit=integer(data.limit,100,1,1000);
    const minimum=integer(data.minPlay,0,0,1e12);
    const keyword=String(data.keyword || '').trim().slice(0,100).toLocaleLowerCase();
    const sort=data.sort || 'play';
    if (!['play','pubdate'].includes(sort)) throw new Error('排序参数无效');
    let rows=snapshot.videos.filter(r=>r.play>=minimum && (!keyword ||
      (r.title+' '+r.author+' '+r.bvid).toLocaleLowerCase().includes(keyword)));
    if (sort==='pubdate') rows=rows.slice().sort((a,b)=>b.pubdate-a.pubdate || a.bvid.localeCompare(b.bvid));
    return {year:snapshot.year,total:snapshot.videos.length,filtered:rows.length,
      latest:snapshot.latest,snapshotAt:snapshot.snapshot_at,status:snapshot.status,
      collectionNotice:snapshot.notice,videos:rows.slice(0,limit),sitewideComplete:false,scope:'static_candidates'};
  }
  const api={query,integer};
  if (typeof module==='object' && module.exports) module.exports=api;
  else root.yearRankQuery=api;
})(typeof globalThis==='object' ? globalThis : this);
