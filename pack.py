"""Offline builder. Run with Python 3.13 and python-minifier available."""
from itertools import product
from pathlib import Path
import ast
import lzma
import re
import python_minifier

def pack(source):
    best = None
    for hoist, rename in product((False, True), repeat=2):
        text = python_minifier.minify(source, rename_globals=rename, hoist_literals=hoist,
                                      remove_literal_statements=True).encode()
        for lc, lp, pb, nice in product(range(5), range(2), range(5), (32, 64, 128, 273)):
            if lc+lp>4:
                continue
            filters = [dict(id=lzma.FILTER_LZMA1, preset=9|lzma.PRESET_EXTREME,
                            lc=lc, lp=lp, pb=pb, dict_size=65536, nice_len=nice, mf=lzma.MF_BT4)]
            data = lzma.compress(text, format=lzma.FORMAT_ALONE, filters=filters)
            for quote in (b'"', b"'"):
                body = data.replace(b'\\', b'\\\\').replace(b'\r', b'\\r')
                body = re.sub(rb'\x00(?![0-7])', lambda _: b'\\0', body).replace(b'\x00', b'\\x00')
                body = body.replace(quote*3, quote*2+b'\\'+quote)
                if body.endswith(quote):
                    body = body[:-1]+b'\\'+quote
                wrap = (b'#coding:l1\nimport lzma\nexec(lzma.decompress('+quote*3+body+quote*3
                        +b'.encode("L1")))\n')
                if best is not None and len(wrap)>=len(best):
                    continue
                tree = ast.parse(wrap)
                encoded = max((n.value for n in ast.walk(tree)
                               if isinstance(n, ast.Constant) and isinstance(n.value,str)), key=len)
                if lzma.decompress(encoded.encode('L1')) != text:
                    continue
                compile(wrap,'main.py','exec')
                best = wrap
    return best

if __name__=='__main__':
    folder = Path(__file__).resolve().parent
    result = pack((folder/'engine.py').read_text(encoding='utf-8'))
    print(f'{len(result)} bytes')
    if len(result)>4096:
        raise SystemExit('main.py exceeds 4096 bytes')
    (folder/'main.py').write_bytes(result)
