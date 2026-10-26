'use strict';
// Loaded by a reversible bootstrap patch. Runtime reads frozen JSON only.
const { app, ipcMain, BrowserWindow } = require('electron');
const fs = require('fs');
const path = require('path');
const {query,integer}=require('./snapshot_query.js');
const key = Symbol.for('bili.local.yearRank.v1');
if (!global[key]) {
  global[key] = true;
  const configPath=path.join(__dirname,'config.json');
  const config=fs.existsSync(configPath) ? JSON.parse(fs.readFileSync(configPath,'utf8')) : {root:path.resolve(__dirname,'..')};
  const logPath = path.join(config.root, 'data', 'integration.log');
  const writeLog = (event, detail = '') => {
    try { fs.appendFileSync(logPath, JSON.stringify({time: new Date().toISOString(), event, detail}) + '\n'); } catch (_) {}
  };
  fs.mkdirSync(path.dirname(logPath), {recursive: true});
  const staticRoot=path.join(config.root,'output','static');
  let catalog;
  function getCatalog() {
    if(catalog)return catalog;
    try {
      const data=JSON.parse(fs.readFileSync(path.join(staticRoot,'manifest.json'),'utf8'));
      if(!Array.isArray(data.years))throw new Error('invalid catalog');
      catalog=data;
      return catalog;
    } catch (_) {throw new Error('本地年度榜数据包不可用，请先生成静态榜单');}
  }
  const snapshots=new Map();
  function allowed(url) {
    try {
      const parsed = new URL(url);
      return ['http:', 'https:'].includes(parsed.protocol) && parsed.hostname === 'bilipc.bilibili.com' && /^\/(index|search)\.html$/.test(parsed.pathname);
    } catch (_) { return false; }
  }
  for (const method of ['list', 'catalog']) {
    ipcMain.handle('localYearRank:' + method, (event, data = {}) => {
      if (!allowed(event.senderFrame?.url || '')) throw new Error('拒绝来自非客户端页面的请求');
      if (!data || Array.isArray(data) || typeof data!=='object') throw new Error('筛选参数无效');
      const catalog=getCatalog();
      if (method==='catalog') return catalog;
      const year=integer(data.year,catalog.default_year,2009,9999);
      if (!catalog.years.some(item=>item.year===year)) throw new Error('年份不在静态目录中');
      if (!snapshots.has(year)) snapshots.set(year,JSON.parse(fs.readFileSync(path.join(staticRoot,year+'.json'),'utf8')));
      return query(snapshots.get(year),data);
    });
  }
  ipcMain.handle('localYearRank:hello', event => {
    if (!allowed(event.senderFrame?.url || '')) throw new Error('页面不匹配');
    writeLog('renderer-ready', {id: event.sender.id, url: event.senderFrame.url});
    return {version: '2.0.0', mode:'static', appVersion: app.getVersion()};
  });
  const renderer = fs.readFileSync(path.join(__dirname, 'renderer.js'), 'utf8');
  const observed = new WeakSet();
  function observe(contents) {
    if (observed.has(contents)) return;
    observed.add(contents);
    const inject = () => {
      if (contents.isDestroyed() || !allowed(contents.getURL()) || !contents.getURL().includes('/index.html')) return;
      contents.executeJavaScript(renderer, false).catch(error => writeLog('inject-error', String(error)));
    };
    contents.on('did-finish-load', inject);
    contents.on('did-navigate-in-page', inject);
    contents.on('dom-ready', inject);
    if (!contents.isLoading()) inject();
  }
  app.on('web-contents-created', (_event, contents) => observe(contents));
  app.whenReady().then(() => { for (const window of BrowserWindow.getAllWindows()) observe(window.webContents); });
  writeLog('loaded', {version: app.getVersion(), mode:'static', processId: process.pid});
}
