"""Version-bound ASAR patcher. The installed executable is never modified."""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import os
from pathlib import Path
import shutil
import struct
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]
MARKER = b'/* BILI_LOCAL_YEAR_RANK_V1 */'
ENTRY = 'main/index.js'
SUPPORTED = ('1.19.0',)


def sha(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024*1024), b''):
            digest.update(block)
    return digest.hexdigest()


def walk(node, prefix=''):
    for name, item in node.get('files', {}).items():
        if 'files' in item:
            yield from walk(item, prefix+name+'/')
        else:
            yield prefix+name, item


class Archive:
    def __init__(self, path):
        self.path = Path(path)
        with self.path.open('rb') as stream:
            values = struct.unpack('<4I', stream.read(16))
            if values[0] != 4 or values[3] > 32*1024*1024:
                raise ValueError('ASAR 头不符合预期')
            self.header = json.loads(stream.read(values[3]))
            self.base = 8 + values[1]

    def read(self, name):
        item = self.header
        for part in name.split('/'):
            item = item['files'][part]
        if 'offset' not in item or item.get('unpacked'):
            raise ValueError('不是打包内的普通文件：'+name)
        with self.path.open('rb') as stream:
            stream.seek(self.base+int(item['offset']))
            data = stream.read(item['size'])
        if len(data) != item['size']:
            raise ValueError('ASAR 文件截断')
        return data

    @property
    def version(self):
        return json.loads(self.read('package.json'))['version']


def integrity(data, block_size=4194304):
    return {'algorithm':'SHA256', 'hash':hashlib.sha256(data).hexdigest(), 'blockSize':block_size,
            'blocks':[hashlib.sha256(data[i:i+block_size]).hexdigest() for i in range(0,len(data),block_size)]}


def build_archive(source, target, replacements):
    archive = Archive(source)
    header = copy.deepcopy(archive.header)
    items = [(name,item) for name,item in walk(header) if 'offset' in item and not item.get('unpacked')]
    items.sort(key=lambda pair:int(pair[1]['offset']))
    offset, blobs = 0, []
    for name,item in items:
        data = replacements.get(name)
        if data is None:
            data = archive.read(name)
        else:
            item['integrity'] = integrity(data, item.get('integrity',{}).get('blockSize',4194304))
        item['offset'] = str(offset)
        item['size'] = len(data)
        offset += len(data)
        blobs.append(data)
    raw = json.dumps(header,ensure_ascii=False,separators=(',',':')).encode('utf-8')
    padding = (-(len(raw)+4)) % 4
    header_bytes = struct.pack('<II',4+len(raw)+padding,len(raw))+raw+b'\0'*padding
    target = Path(target)
    target.parent.mkdir(parents=True,exist_ok=True)
    with target.open('wb') as stream:
        stream.write(struct.pack('<II',4,len(header_bytes)))
        stream.write(header_bytes)
        for data in blobs:
            stream.write(data)
    after = Archive(target)
    changed = []
    for name,item in items:
        old,new = archive.read(name),after.read(name)
        if old != new:
            changed.append(name)
        expected = replacements.get(name,old)
        if new != expected:
            raise ValueError('重打包校验失败：'+name)
    if set(changed) != {name for name,data in replacements.items() if archive.read(name)!=data}:
        raise ValueError('改动文件集合不符')
    return {'version':archive.version,'source_sha256':sha(source),'patched_sha256':sha(target),'changed_files':changed}


def prefix():
    module = json.dumps(str(ROOT/'integration'/'main.cjs'),ensure_ascii=True)
    error_log = json.dumps(str(ROOT/'data'/'integration_boot_error.log'),ensure_ascii=True)
    return MARKER + (f";try{{require({module});}}catch(__localYrError){{try{{require('fs').appendFileSync({error_log},String(__localYrError)+'\\n');}}catch(_){{}}}};\n").encode('utf-8')


def active_cache():
    resource = Path(os.environ['APPDATA'])/'bilibili'/'resource'
    version = (resource/'.version').read_text(encoding='utf-8').strip()
    if version not in SUPPORTED:
        raise ValueError('当前运行资源版本 '+version+' 尚未适配；不会自动应用旧补丁')
    name = hashlib.md5(version.encode()).hexdigest()[:16]+'.asar'
    target = resource/name
    if Archive(target).version != version:
        raise ValueError('缓存版本与资源包版本不一致')
    return target


def install():
    hot=active_cache()
    installed=Path(r'C:\Program Files\bilibili\resources\app.asar')
    expected=json.loads((ROOT/'integration'/'supported_bootstrap.json').read_text(encoding='utf-8'))
    if sha(installed)!=expected['sha256']:
        raise ValueError('安装版引导包与已验证构建不同，拒绝修改')
    client=ROOT/'client'
    marker=client/'.bili-year-rank-client'
    if client.exists() and not marker.exists():
        raise ValueError('目标目录已存在且不属于本工具，拒绝覆盖')
    client.mkdir(exist_ok=True)
    marker.write_text('local-year-rank-client',encoding='utf-8')
    if not (client/'哔哩哔哩.exe').exists():
        shutil.copytree(installed.parents[1],client,dirs_exist_ok=True)
    backup=ROOT/'integration'/'backups'/expected['sha256']/'original.asar'
    backup.parent.mkdir(parents=True,exist_ok=True)
    if not backup.exists():shutil.copy2(installed,backup)
    if sha(backup)!=expected['sha256']:raise ValueError('原包备份校验失败')
    archive=Archive(installed)
    staged=ROOT/'integration'/'build'/'patched.asar'
    result=build_archive(installed,staged,{'index.js':prefix()+archive.read('index.js')})
    target=client/'resources'/'app.asar'
    result.update({'target':str(target),'backup':str(backup),'status':'prepared',
                   'mode':'per-user-native-client','hot_version':Archive(hot).version,
                   'executable':str(client/'哔哩哔哩.exe'),'module_root':str(ROOT/'integration'),
                   'original_executable':str(installed.parents[1]/'哔哩哔哩.exe'),
                   'shortcut':str(Path.home()/'Desktop'/'哔哩哔哩（年度榜增强版）.lnk')})
    state_file=ROOT/'data'/'client_patch.json'
    state_file.parent.mkdir(exist_ok=True)
    state_file.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    nearby=target.with_name(target.name+'.year-rank-new')
    shutil.copyfile(staged,nearby)
    if sha(nearby)!=result['patched_sha256']:raise ValueError('暂存补丁校验失败')
    os.replace(nearby,target)
    result['status']='installed'
    state_file.write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))
    return result


def restore():
    state_file=ROOT/'data'/'client_patch.json'
    state=json.loads(state_file.read_text(encoding='utf-8'))
    target,backup=Path(state['target']),Path(state['backup'])
    if target.resolve()!=(ROOT/'client'/'resources'/'app.asar').resolve():
        raise ValueError('恢复目标不在预期增强客户端目录')
    if sha(target)==state['source_sha256']:
        print('已经是原始资源包')
        return
    if sha(target)!=state['patched_sha256'] or sha(backup)!=state['source_sha256']:
        raise ValueError('资源包或备份已变化，拒绝覆盖')
    nearby=target.with_name(target.name+'.year-rank-restore')
    shutil.copyfile(backup,nearby)
    os.replace(nearby,target)
    state['status']='restored'
    state_file.write_text(json.dumps(state,ensure_ascii=False,indent=2),encoding='utf-8')
    print('已撤销增强副本的入口补丁；原版安装、账户数据与年度榜数据均保留')


def prepare_sandbox():
    installed=Path(r'C:\Program Files\bilibili\resources\app.asar')
    sandbox=ROOT/'.client-sandbox'
    marker=sandbox/'.bili-year-rank-sandbox'
    if sandbox.exists() and not marker.exists():
        raise ValueError('测试目录已存在且不是本工具创建，拒绝覆盖')
    sandbox.mkdir(exist_ok=True)
    marker.write_text('local-year-rank-test',encoding='utf-8')
    if not (sandbox/'哔哩哔哩.exe').exists():
        shutil.copytree(installed.parents[1],sandbox,dirs_exist_ok=True)
    profile=ROOT/'.sandbox-baseline'
    profile_literal=json.dumps(str(profile),ensure_ascii=True)
    prelude=(f";{{const __yrApp=require('electron').app;const __yrPath={profile_literal};require('fs').mkdirSync(__yrPath,{{recursive:true}});__yrApp.setPath('userData',__yrPath);}};\n").encode('utf-8')
    archive=Archive(installed)
    result=build_archive(installed,sandbox/'resources'/'app.asar',{'index.js':prelude+prefix()+archive.read('index.js')})
    result.update({'executable':str(sandbox/'哔哩哔哩.exe'),'profile':str(profile)})
    (ROOT/'integration'/'sandbox_manifest.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False,indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description='Bilibili 本机年度榜补丁（安装/恢复前须退出客户端）')
    p.add_argument('action',choices=['prepare-sandbox','install','restore','status'])
    args=p.parse_args()
    if args.action=='prepare-sandbox':prepare_sandbox()
    elif args.action=='install':install()
    elif args.action=='restore':restore()
    else:
        target=ROOT/'client'/'resources'/'app.asar'
        print(json.dumps({'target':str(target),'version':Archive(target).version,'patched':Archive(target).read('index.js').startswith(MARKER),'sha256':sha(target)},ensure_ascii=False,indent=2))
