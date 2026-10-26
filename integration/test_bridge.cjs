'use strict';
const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const vm=require('node:vm');
const {EventEmitter}=require('node:events');
const handlers=new Map();
const app=new EventEmitter();
app.getVersion=()=> '1.17.2';
app.whenReady=()=>Promise.resolve();
const logs=[];
let unavailableManifest=true;
const fakeFs={...fs,mkdirSync(){},appendFileSync(_path,line){logs.push(line);},
  readFileSync(file,...args){
    if(unavailableManifest && String(file).endsWith('manifest.json'))throw new Error('missing test manifest');
    return fs.readFileSync(file,...args);
  }};
const localProcess=new EventEmitter();localProcess.pid=process.pid;
const box={Symbol,URL,Promise,Map,WeakSet,JSON,Error,console,setTimeout,clearTimeout,
  __dirname:__dirname,process:localProcess};
box.global=box;
box.require=name=>{
  if(name==='electron')return {app,ipcMain:{handle(name,handler){assert(!handlers.has(name));handlers.set(name,handler);}},BrowserWindow:{getAllWindows:()=>[]}};
  if(name==='fs')return fakeFs;
  return require(name);
};
const context=vm.createContext(box);
const code=fs.readFileSync(path.join(__dirname,'main.cjs'),'utf8');
vm.runInContext('(function(){'+code+'\n})();',context);
vm.runInContext('(function(){'+code+'\n})();',context);
(async()=>{
  assert.equal(handlers.size,3);
  for (const method of ['plan','start','status','cancel']) assert(!handlers.has('localYearRank:'+method));
  assert.throws(()=>handlers.get('localYearRank:list')({senderFrame:{url:'https://example.com/index.html'}},{}),/非客户端/);
  const event={senderFrame:{url:'https://bilipc.bilibili.com/index.html#/page/home'}};
  assert.throws(()=>handlers.get('localYearRank:catalog')(event,{}),/数据包不可用/);
  unavailableManifest=false;
  const catalog=await handlers.get('localYearRank:catalog')(event,{});
  assert.equal(catalog.mode,'static');
  assert(catalog.years.some(y=>y.year===2009));
  const result=await handlers.get('localYearRank:list')(event,{year:2018,limit:5});
  assert.equal(result.videos.length,5);
  assert.deepEqual(result.videos.map(v=>v.play),result.videos.map(v=>v.play).slice().sort((a,b)=>b-a));
  const hit=result.videos[2];
  const filtered=await handlers.get('localYearRank:list')(event,{year:2018,keyword:hit.bvid});
  assert.equal(filtered.videos.length,1);
  assert.equal(filtered.videos[0].rank,hit.rank);
  for(const year of [true,'../../private',2008,9999])
    assert.throws(()=>handlers.get('localYearRank:list')(event,{year}));
  assert(!code.includes('child_process'));
  console.log('BRIDGE_OK: frozen catalog, local JSON filtering, original ranks, no collection channels or worker');
})().catch(error=>{console.error(error);process.exitCode=1;});
