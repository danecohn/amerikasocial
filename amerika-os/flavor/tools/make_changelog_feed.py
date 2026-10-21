#!/usr/bin/env python3
"""Turn flavor/debian-src/debian/changelog into the JSON changelog feed (see flavor/updates/changelog-feed.md).

    make_changelog_feed.py [--changelog PATH] [--channel stable|testing] [--output FILE]   (default: stdout)
"""
import argparse
import datetime
import email.utils
import json
import re
import sys
from pathlib import Path

DEFAULT = Path(__file__).resolve().parents[1] / 'debian-src/debian/changelog'
HEAD = re.compile(r'^(?P<src>\S+) \((?P<ver>[^)]+)\) (?P<dist>[^;]+); urgency=(?P<urg>\w+)')
TRAIL = re.compile(r'^ -- (?P<who>.+?)  (?P<date>\w{3}, .+)$')
MAX_BYTES = 256 * 1024


def parse(text):
    releases, cur = [], None
    for line in text.splitlines():
        m = HEAD.match(line)
        if m:
            cur = {'source': m['src'], 'version': m['ver'], 'urgency': m['urg'].lower(), 'changes': [], 'date': None}
            continue
        if cur is None:
            continue
        t = TRAIL.match(line)
        if t:
            dt = email.utils.parsedate_to_datetime(t['date']).astimezone(datetime.timezone.utc)
            cur['date'] = dt.strftime('%Y-%m-%dT%H:%M:%SZ')
            releases.append(cur)
            cur = None
        elif line.startswith('  * '):
            cur['changes'].append(line[4:].strip())
        elif line.startswith('    ') and cur['changes']:
            cur['changes'][-1] += ' ' + line.strip()
    return releases


def feed(text, channel='stable'):
    releases = parse(text)
    out = []
    for r in releases:
        sec = any(re.search(r'CVE-\d{4}-\d+|security', c, re.I) for c in r['changes'])
        out.append({'version': r['version'], 'date': r['date'], 'urgency': r['urgency'], 'security': sec, 'changes': r['changes']})
    now = datetime.datetime.now(datetime.timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')
    doc = {'schema': 1, 'source': releases[0]['source'] if releases else 'amerika-os', 'generated': now, 'channel': channel,
           'releases': out}
    while len(json.dumps(doc).encode()) > MAX_BYTES and len(doc['releases']) > 1:
        doc['releases'].pop()
    return doc


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument('--changelog', default=str(DEFAULT))
    ap.add_argument('--channel', default='stable', choices=('stable', 'testing'))
    ap.add_argument('--output')
    args = ap.parse_args(argv)
    doc = feed(Path(args.changelog).read_text(), args.channel)
    text = json.dumps(doc, indent=2, ensure_ascii=False) + '\n'
    if args.output:
        Path(args.output).write_text(text)
    else:
        sys.stdout.write(text)


if __name__ == '__main__':
    main()
