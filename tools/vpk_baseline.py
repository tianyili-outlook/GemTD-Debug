"""Lossless, checksum-verified extraction of this single-file VPK v2 baseline.

No decompilation or resource compilation. Python standard library only.
Format reference: https://github.com/panzi/unvpk (and its linked VPK spec).
Refuses split archives, unsafe paths, nonempty extraction targets, and changed input.
"""
import argparse
import collections
import hashlib
import json
from pathlib import Path, PurePosixPath
import struct
import zlib

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_SOURCE = Path(r"F:\Steam\steamapps\workshop\content\570\474619917\474619917.vpk")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_vpk(source):
    raw = source.read_bytes()
    magic, version, tree_size, data_size, chunk_size, other_size, signature_size = struct.unpack_from('<7I', raw)
    if magic != 0x55AA1234 or version != 2:
        raise ValueError('Expected a VPK v2 archive')
    tree_end = 28 + tree_size
    data_end = tree_end + data_size
    other_start = data_end + chunk_size
    if other_start + other_size + signature_size != len(raw) or other_size != 48 or chunk_size % 28:
        raise ValueError('Invalid VPK section sizes')
    for index, (data, expected) in enumerate((
        (raw[28:tree_end], raw[other_start:other_start+16]),
        (raw[data_end:other_start], raw[other_start+16:other_start+32]),
        (raw[:other_start+32], raw[other_start+32:other_start+48]),
    )):
        # Older map packers can omit the first two section hashes (all zero).
        # The whole-file digest must still be present and valid.
        if index < 2 and expected == bytes(16):
            continue
        if hashlib.md5(data).digest() != expected:
            raise ValueError('VPK section MD5 mismatch')
    for pos in range(data_end, other_start, 28):
        archive, hash_type, offset, size, expected = struct.unpack_from('<HHII16s', raw, pos)
        if archive != 0x7FFF or offset + size > data_size:
            raise ValueError('Unsupported external archive or invalid chunk bounds')
        if hash_type not in (0, 1):
            raise ValueError('Unknown chunk hash type')
        # Modern Source 2 uses Blake3 (type 1). No third-party dependency is
        # needed here: whole-file MD5 above plus each file's CRC32 below cover
        # the payload. Record that Blake3 chunks were not independently checked.
        if hash_type == 0 and hashlib.md5(raw[tree_end+offset:tree_end+offset+size]).digest() != expected:
            raise ValueError('VPK chunk MD5 mismatch')
    pos = 28
    def string():
        nonlocal pos
        end = raw.index(b'\0', pos, tree_end)
        value = raw[pos:end].decode('utf-8')
        pos = end + 1
        return value
    entries = []
    seen = set()
    while (extension := string()):
        while (directory := string()):
            while (name := string()):
                if pos + 18 > tree_end:
                    raise ValueError('Truncated entry')
                crc, preload_size, archive, offset, size, terminator = struct.unpack_from('<IHHIIH', raw, pos)
                pos += 18
                if terminator != 0xFFFF or pos + preload_size > tree_end:
                    raise ValueError('Invalid entry')
                preload = raw[pos:pos+preload_size]
                pos += preload_size
                if size and (archive != 0x7FFF or offset + size > data_size):
                    raise ValueError('Unsupported external archive or invalid entry bounds')
                path = ('' if directory == ' ' else directory + '/') + name + ('' if extension == ' ' else '.' + extension)
                parts = PurePosixPath(path).parts
                if not parts or path.startswith('/') or any(p in ('.', '..') or ':' in p or '\\' in p or p.endswith((' ', '.')) for p in parts):
                    raise ValueError('Unsafe archive path: ' + path)
                if path.casefold() in seen:
                    raise ValueError('Duplicate archive path: ' + path)
                seen.add(path.casefold())
                payload = preload + (raw[tree_end+offset:tree_end+offset+size] if size else b'')
                if zlib.crc32(payload) != crc:
                    raise ValueError('CRC32 mismatch: ' + path)
                entries.append((dict(path=path, size=len(payload), crc32=f'{crc:08x}', sha256=digest(payload)), payload))
    if pos != tree_end:
        raise ValueError('Unconsumed directory bytes')
    return raw, entries, dict(version=version, tree_size=tree_size, data_size=data_size,
                             chunk_count=chunk_size // 28, signature_size=signature_size,
                             verification='available section MD5; whole-file MD5; every entry CRC32; extracted SHA256',
                             tree_md5_present=raw[other_start:other_start+16] != bytes(16),
                             hash_section_md5_present=raw[other_start+16:other_start+32] != bytes(16),
                             blake3_chunks_verified=False, signature_verified=False)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['inspect', 'extract', 'verify'])
    parser.add_argument('--source', type=Path, default=DEFAULT_SOURCE)
    parser.add_argument('--target', type=Path, default=ROOT / 'game/gemtd_debug')
    parser.add_argument('--manifest', type=Path, default=ROOT / 'baseline/manifest.json')
    args = parser.parse_args()
    raw, entries, header = read_vpk(args.source)
    records = sorted((record for record, _ in entries), key=lambda r: r['path'])
    metadata = args.source.with_name('publish_data.txt').read_bytes()
    manifest = dict(source=str(args.source), source_size=len(raw), source_sha256=digest(raw),
                    publish_data_sha256=digest(metadata), header=header, files=records)
    if args.manifest.exists():
        old = json.loads(args.manifest.read_text(encoding='utf-8'))
        if any(old[key] != manifest[key] for key in ('source_sha256', 'publish_data_sha256', 'files')):
            raise ValueError('Input differs from the saved baseline; use a separate manifest and target for a new version')
    if args.mode == 'extract':
        if args.target.exists() and any(args.target.iterdir()):
            raise ValueError('Extraction target must be empty; existing work will not be overwritten')
        args.target.mkdir(parents=True, exist_ok=True)
        root = args.target.resolve()
        for record, payload in entries:
            destination = args.target / record['path']
            if not destination.resolve().is_relative_to(root):
                raise ValueError('Destination escapes extraction root')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with destination.open('xb') as stream:
                stream.write(payload)
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')
        args.manifest.with_name('publish_data.txt').write_bytes(metadata)
    if args.mode in ('extract', 'verify'):
        expected_paths = {record['path'] for record in records}
        actual_paths = {p.relative_to(args.target).as_posix() for p in args.target.rglob('*') if p.is_file()}
        if expected_paths != actual_paths:
            raise ValueError(f'File set mismatch: missing={expected_paths-actual_paths}, extra={actual_paths-expected_paths}')
        for record in records:
            if digest((args.target / record['path']).read_bytes()) != record['sha256']:
                raise ValueError('Extracted file mismatch: ' + record['path'])
        print('Verified every extracted file byte-for-byte (SHA-256) against checksum-validated VPK entries.')
    print(json.dumps(dict(mode=args.mode, file_count=len(records), extracted_bytes=sum(r['size'] for r in records),
                          source_sha256=manifest['source_sha256'], header=header,
                          top_level=dict(collections.Counter(r['path'].split('/')[0] for r in records)),
                          extensions=dict(collections.Counter(Path(r['path']).suffix for r in records))), indent=2))


if __name__ == '__main__':
    main()
