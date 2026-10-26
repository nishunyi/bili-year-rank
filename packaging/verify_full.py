"""Verify real distribution contents and simulate official update incompatibility."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import tempfile

def verify(root,installed=False):
    root=Path(root).resolve()
    manifest=json.loads((root/'bundle-manifest.json').read_text(encoding='utf8'))
    for name,digest in manifest['files'].items():
        path=(root/name).resolve()
        if root not in path.parents:raise ValueError('manifest path escapes bundle')
        assert hashlib.sha256(path.read_bytes()).hexdigest()==digest,name
    for name in ('Cookies','Login Data','Local State','Preferences','config.json','client_patch.json','integration.log'):
        assert not list(root.rglob(name)),name
    if not installed:assert not (root/'versions/.appInfo').exists()
    module=root/'resources/year-rank'
    for path in module.rglob('*'):
        if path.suffix in ('.js','.cjs','.json'):
            text=path.read_text(encoding='utf8')
            assert 'D:\\\\codexall' not in text and 'C:\\\\Users\\\\nishu' not in text,path
    data=json.loads((module/'output/static/manifest.json').read_text(encoding='utf8'))
    assert len(data['years'])==18 and data['total_candidates']==9173
    for year in data['years']:
        snapshot=json.loads((module/'output/static'/f'{year["year"]}.json').read_text(encoding='utf8'))
        assert len(snapshot['videos'])==year['count']
        assert all(v['cover'].startswith('https://') for v in snapshot['videos'])
    def check(folder,expected):
        result=subprocess.run([str(folder/'年度榜增强版.exe'),'--check'],timeout=15)
        assert result.returncode==expected,(folder,result.returncode,expected)
    check(root,0)
    with tempfile.TemporaryDirectory(prefix='year-rank-update-') as tmp:
        test=Path(tmp)
        (test/'resources/year-rank').mkdir(parents=True)
        (test/'versions').mkdir()
        for name in ('年度榜增强版.exe','resources/app.asar','resources/year-rank/bootstrap.sha256','versions/.version'):
            shutil.copy2(root/name,test/name)
        check(test,0)
        (test/'versions/.version').write_text('1.20.0',encoding='ascii')
        check(test,2)
        (test/'versions/.version').write_text('1.19.0',encoding='ascii')
        (test/'resources/app.asar').write_bytes(b'simulated new official bootstrap without addon')
        check(test,2)
    return {'files':len(manifest['files']),'years':len(data['years']),'candidates':data['total_candidates'],
        'manifest_sha256':'passed','no_account_files':'passed','relocated_launcher':'passed',
        'new_resource_version_detected':'passed','overwritten_bootstrap_detected':'passed'}

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle',type=Path)
    parser.add_argument('--installed',action='store_true',help='allow the generated runtime .appInfo stamp')
    args=parser.parse_args()
    print(json.dumps(verify(args.bundle,args.installed),ensure_ascii=False,indent=2))
