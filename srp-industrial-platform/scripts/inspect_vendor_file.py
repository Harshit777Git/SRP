import argparse
import collections
import hashlib
import json
from pathlib import Path
import zipfile


def inspect(path):
    raw=path.read_bytes()
    result=dict(filename=path.name,size_bytes=len(raw),sha256=hashlib.sha256(raw).hexdigest(),
                first_bytes_hex=raw[:32].hex(),parser_status="UNVERIFIED")
    if zipfile.is_zipfile(path):
        with zipfile.ZipFile(path) as archive:
            result["archive_entries"]=archive.namelist()
        return result
    for encoding in ("utf-8-sig","utf-16"):
        try:
            string=raw.decode(encoding)
        except UnicodeError:
            continue
        if not string or sum(c.isprintable() or c in "\r\n\t" for c in string)<.95*len(string):
            continue
        lines=string.splitlines()
        result.update(encoding=encoding,line_count=len(lines),
                      field_count_histograms={d:dict(collections.Counter(len(s.split(d)) for s in lines[:200]))
                                              for d in (",",";","\t","|")})
        break
    return result


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("file",type=Path)
    print(json.dumps(inspect(p.parse_args().file),indent=2))
