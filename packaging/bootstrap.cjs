'use strict';
// Runs before the unmodified client bootstrap, before any Chromium session exists.
const {app}=require('electron');
const fs=require('fs');
const path=require('path');
const crypto=require('crypto');
const profile=path.join(app.getPath('appData'),'bili-year-rank-enhanced');
fs.mkdirSync(profile,{recursive:true});
app.setPath('userData',profile);
app.setPath('sessionData',profile);
app.setAppLogsPath(path.join(profile,'logs'));

// The original bootstrap natively supports an executable-adjacent versions/ dir.
// Its .appInfo is tied to the install's app-update.yml creation time, not a user.
const versions=path.join(path.dirname(process.execPath),'versions');
const stamp=fs.statSync(path.join(process.resourcesPath,'app-update.yml')).ctime.toString();
fs.writeFileSync(path.join(versions,'.appInfo'),crypto.createHash('md5').update(stamp).digest('hex'));
global.__yearRankBundle={root:__dirname,logRoot:path.join(profile,'year-rank')};
require('./integration/main.cjs');
