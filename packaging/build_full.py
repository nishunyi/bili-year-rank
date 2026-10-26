"""Build a relocatable full client from version-checked local public binaries."""
from __future__ import annotations
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'integration'))
from patch_client import Archive,build_archive,sha,MARKER

VERSION='0.2.0'
TOP_FILES=('哔哩哔哩.exe','bili-config.json','chrome_100_percent.pak','chrome_200_percent.pak',
    'd3dcompiler_47.dll','ffmpeg.dll','icudtl.dat','libEGL.dll','libGLESv2.dll',
    'LICENSE.electron.txt','LICENSES.chromium.html','resources.pak','snapshot_blob.bin',
    'v8_context_snapshot.bin','vk_swiftshader_icd.json','vk_swiftshader.dll','vulkan-1.dll')
MODULES=('main.cjs','renderer.js','snapshot_query.js')
NOTICE='''哔哩哔哩（年度榜增强版） v0.2.0

Windows 10 / 11 64 位。完整包内含客户端运行文件和年度榜，使用时无需先安装原版、Python 或 Node.js。
安装版：运行 setup 安装程序，按提示安装，从桌面入口打开。
免安装版：将整个文件夹解压到可写位置，双击“年度榜增强版.exe”。不要只移动 exe。

侧栏“年度榜”与首页、精选并列。选择年份后浏览和筛选；点击视频使用客户端播放器。
2009—2026 年共 9,173 个候选，播放量为采集时快照，不能保证覆盖全站前 100。
榜单元信息在本地，封面、在线页面与播放需联网。

增强版使用独立的 bili-year-rank-enhanced 用户目录。包内没有作者的登录态、Cookie、观看历史或个人配置；需要账号的功能请自行登录。
卸载增强版不会卸载已安装的原版。个人数据默认保留在用户 AppData 下。
基础客户端引导包 1.17.2，运行资源 1.19.0。保留官方更新检查和通知。
官方整包更新可能覆盖年度榜引导入口，资源热更新也可能改变页面结构。启动器检测到文件或资源版本变化时会提示获取适配版本，不保证未知官方版本兼容。需要时重新安装增强包可恢复所附的已适配版本；不会自动降级官方更新。

本项目为第三方增强，非哔哩哔哩官方发布。客户端及其第三方组件的权利和许可归各自权利人；本项目 MIT 许可仅适用于自有代码。
项目与源码：https://github.com/nishunyi/bili-year-rank
'''

def build(source:Path,hot:Path,dest:Path):
    source=source.resolve();hot=hot.resolve();dest=dest.resolve()
    if dest.exists():raise ValueError('构建目标已存在，请选择新的空目录')
    expected=json.loads((ROOT/'integration/supported_bootstrap.json').read_text(encoding='utf8'))
    original=source/'resources/app.asar'
    if sha(original)!=expected['sha256']:raise ValueError('引导包未通过已验证哈希校验')
    version=(hot/'.version').read_text(encoding='utf8').strip()
    if version!='1.19.0':raise ValueError('运行资源版本尚未适配')
    archive_name=hashlib.md5(version.encode()).hexdigest()[:16]+'.asar'
    if Archive(hot/archive_name).version!=version:raise ValueError('运行包版本不符')
    dest.mkdir(parents=True)
    for name in TOP_FILES:shutil.copy2(source/name,dest/name)
    for name in ('locales','resources'):shutil.copytree(source/name,dest/name)
    module_root=dest/'resources/year-rank'
    (module_root/'integration').mkdir(parents=True)
    for name in MODULES:shutil.copy2(ROOT/'integration'/name,module_root/'integration'/name)
    shutil.copy2(ROOT/'packaging/bootstrap.cjs',module_root/'bootstrap.cjs')
    shutil.copytree(ROOT/'output/static',module_root/'output/static')
    shutil.copy2(ROOT/'LICENSE',module_root/'LICENSE')
    # Only the four known public code resources, never the surrounding user profile.
    (dest/'versions').mkdir()
    for name in ('.version','.biliapp','.bilijsc',archive_name):
        shutil.copy2(hot/name,dest/'versions'/name)
    prelude=MARKER+b";require(require('path').join(process.resourcesPath,'year-rank','bootstrap.cjs'));\n"
    result=build_archive(original,dest/'resources/app.asar',{'index.js':prelude+Archive(original).read('index.js')})
    (module_root/'bootstrap.sha256').write_text(result['patched_sha256']+'\n',encoding='ascii')
    csc=Path(os.environ.get('WINDIR',r'C:\Windows'))/'Microsoft.NET/Framework64/v4.0.30319/csc.exe'
    subprocess.run([str(csc),'/nologo','/target:winexe','/platform:x64','/r:System.Windows.Forms.dll',
        '/out:'+str(dest/'年度榜增强版.exe'),str(ROOT/'packaging/Launcher.cs')],check=True)
    (dest/'使用说明.txt').write_text(NOTICE,encoding='utf-8-sig')
    files={str(p.relative_to(dest)).replace('\\','/'):sha(p) for p in sorted(dest.rglob('*')) if p.is_file()}
    manifest={'version':VERSION,'bootstrap':expected['version'],'resources':version,
        'bootstrap_patch':result['changed_files'],'files':files,'contains_account_data':False}
    (dest/'bundle-manifest.json').write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding='utf8')
    return manifest

def checksum(file):
    file.with_name(file.name+'.sha256').write_text(sha(file)+'  '+file.name+'\n',encoding='ascii')

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source',type=Path,default=Path(r'C:\Program Files\bilibili'))
    parser.add_argument('--hot',type=Path,default=Path(os.environ.get('APPDATA',''))/'bilibili/resource')
    parser.add_argument('--dest',type=Path,default=ROOT/'dist/full-client-v0.2.0')
    parser.add_argument('--iscc',type=Path)
    parser.add_argument('--zip',action='store_true')
    args=parser.parse_args()
    result=build(args.source,args.hot,args.dest)
    print(json.dumps({'files':len(result['files']),'bundle':str(args.dest.resolve()),'version':VERSION},ensure_ascii=False),flush=True)
    if args.zip:
        target=ROOT/'dist'/f'bili-year-rank-full-portable-v{VERSION}-x64.zip'
        with zipfile.ZipFile(target,'w',zipfile.ZIP_DEFLATED,compresslevel=5) as z:
            for file in sorted(args.dest.rglob('*')):
                if file.is_file():z.write(file,Path('哔哩哔哩（年度榜增强版）')/file.relative_to(args.dest))
        checksum(target);print(str(target),flush=True)
    if args.iscc:
        subprocess.run([str(args.iscc.resolve()),'/DBundleDir='+str(args.dest.resolve()),
            '/DReleaseDir='+str((ROOT/'dist').resolve()),str(ROOT/'packaging/full-client.iss')],check=True)
        checksum(ROOT/'dist'/f'bili-year-rank-full-setup-v{VERSION}-x64.exe')

if __name__=='__main__':main()
