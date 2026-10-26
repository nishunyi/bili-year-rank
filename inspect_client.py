"""Read-only inspection of an installed Electron ASAR; no third-party packages."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import struct


def entries(node, prefix=''):
    for name, item in node.get('files', {}).items():
        if 'files' in item:
            yield from entries(item, prefix + name + '/')
        else:
            yield prefix + name, item


def inspect(path: Path) -> dict:
    with path.open('rb') as stream:
        fixed = stream.read(16)
        if len(fixed) != 16:
            raise ValueError('不是完整 ASAR 文件')
        _, header_size, _, json_size = struct.unpack('<4I', fixed)
        if json_size > 32 * 1024 * 1024:
            raise ValueError('ASAR 头大小异常')
        header = json.loads(stream.read(json_size))
        offset = 8 + header_size
        output = {'source': str(path), 'read_only': True, 'package': None, 'findings': []}
        signals = ['/x/web-interface/search/type', 'pubtime_begin_s', 'pubtime_end_s',
                   'search_type:"video"', 'order:"click"', 'isWbi:!0']
        for name, item in entries(header):
            if item.get('unpacked') or not (name == 'package.json' or (name.startswith('render/assets/') and name.endswith('.js') and '/lib/' not in name)):
                continue
            if int(item.get('size', 0)) > 2_000_000:
                continue
            stream.seek(offset + int(item['offset']))
            raw = stream.read(item['size'])
            body = raw.decode('utf-8', errors='replace')
            if name == 'package.json':
                output['package'] = json.loads(body)
            for signal in signals:
                for match in list(re.finditer(re.escape(signal), body))[:2]:
                    output['findings'].append({'file': name, 'file_sha256': hashlib.sha256(raw).hexdigest(),
                        'offset': match.start(), 'signal': signal,
                        'excerpt': body[max(0, match.start()-140):match.end()+220]})
    return output


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='只读检查 B 站 Electron 客户端的公开搜索调用代码')
    parser.add_argument('--asar', type=Path, default=Path(r'C:\Program Files\bilibili\resources\app.asar'))
    parser.add_argument('--output', type=Path, default=Path(__file__).parent/'evidence'/'client_inspection.json')
    args = parser.parse_args()
    report = inspect(args.asar)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'客户端 {report["package"]["version"]}，发现 {len(report["findings"])} 条线索。报告：{args.output}')
