"""Append the contribution HUD to the shipped plaintext VJS v4 DATA block.

This intentionally supports only this pinned resource, not arbitrary Source 2 files.
The original JS and RED2 block remain byte-identical. Only DATA size and file size
change. Format reference: ValveResourceFormat ResourceTypes/Panorama.cs (VJS v4).
"""
from pathlib import Path
import argparse
import hashlib
import json
import struct

ROOT = Path(__file__).resolve().parents[1]
RELATIVE = 'panorama/scripts/custom_game/gemtd.vjs_c'
RESOURCE = ROOT / 'game/gemtd_debug' / RELATIVE
SOURCE = ROOT / 'content/gemtd_debug/panorama/scripts/custom_game/coop_contribution.js'
MARKER = b'\n;\n// GEMTD_COOP_CONTRIBUTION_V1\n'


def data_block(blob):
    size, header, version, offset, count = struct.unpack_from('<IHHII', blob)
    assert (size, header, version, count) == (len(blob), 12, 4, 2), 'Unexpected VJS header'
    blocks = []
    for i in range(count):
        entry = 8 + offset + i * 12
        name, relative, length = struct.unpack_from('<4sII', blob, entry)
        start = entry + 4 + relative
        assert start >= 8 + offset + count * 12 and start + length <= len(blob)
        blocks.append((name, entry, start, length))
    assert [b[0] for b in blocks] == [b'RED2', b'DATA']
    _, entry, start, length = blocks[1]
    assert blocks[0][2] + blocks[0][3] <= start and start + length == len(blob)
    blob[start:].decode('utf-8')
    return entry, start


def replace_data(blob, payload):
    entry, start = data_block(blob)
    result = bytearray(blob[:start] + payload)
    struct.pack_into('<I', result, 0, len(result))
    struct.pack_into('<I', result, entry + 8, len(payload))
    data_block(result)
    return bytes(result)


def build(blob, source):
    _, start = data_block(blob)
    original = replace_data(blob, blob[start:].split(MARKER)[0])
    manifest = json.loads((ROOT / 'baseline/manifest.json').read_text(encoding='utf-8'))
    expected = next(f['sha256'] for f in manifest['files'] if f['path'] == RELATIVE)
    assert hashlib.sha256(original).hexdigest() == expected, 'Unrecognized original gemtd.vjs_c; refusing to patch'
    assert MARKER not in source
    return replace_data(original, original[start:] + MARKER + source)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--check', action='store_true', help='Verify generated runtime without writing')
    args = parser.parse_args()
    current = RESOURCE.read_bytes()
    expected = build(current, SOURCE.read_bytes())
    if args.check:
        assert current == expected, 'Run python tools/build_contribution_ui.py to update runtime'
        print('PASS: HUD resource matches source; original script/metadata verified against baseline')
    else:
        RESOURCE.write_bytes(expected)
        print('Built', RESOURCE.relative_to(ROOT), len(expected), 'bytes')
