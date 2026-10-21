"""Language & region backend: user-level formats in plasma-localerc (KDE reads it at login) and system locale via localectl."""
import json
import re
from pathlib import Path

from . import sysutil

LOC_OK = re.compile(r'^[a-z]{2,3}(_[A-Z]{2})?(\.[Uu][Tt][Ff]-?8)?(@[a-z]+)?$')
FORMAT_KEYS = [('LC_TIME', 'Dates and times'), ('LC_NUMERIC', 'Numbers'), ('LC_MONETARY', 'Currency'), ('LC_MEASUREMENT', 'Units'),
               ('LC_COLLATE', 'Sorting'), ('LC_PAPER', 'Paper size')]
ISO = Path('/usr/share/iso-codes/json')


def _names(fname, key_a, key_b, field='name'):
    try:
        data = json.loads((ISO / fname).read_text(encoding='utf-8'))
        top = next(iter(data.values()))
        out = {}
        for e in top:
            for k in (key_a, key_b):
                if k in e:
                    out[e[k]] = e.get(field, '')
        return out
    except (OSError, ValueError, StopIteration):
        return {}


_lang_cache, _country_cache = {}, {}


def describe(locale_name):
    """'de_DE.UTF-8' -> 'German (Germany)'."""
    if not _lang_cache:
        _lang_cache.update(_names('iso_639-3.json', 'alpha_2', 'alpha_3'))
        _country_cache.update(_names('iso_3166-1.json', 'alpha_2', 'alpha_3'))
    base = locale_name.split('.')[0].split('@')[0]
    lang, _, country = base.partition('_')
    lname = (_lang_cache.get(lang) or lang).split(';')[0]
    cname = _country_cache.get(country) or country
    return f'{lname} ({cname})' if country else lname


def installed():
    res = sysutil.run(['locale', '-a'])
    seen, out = set(), []
    for line in res.out.splitlines():
        name = line.strip()
        if name in ('C', 'POSIX') or 'utf' not in name.lower() or '@' in name:
            continue
        canon = name.split('.')[0] + '.UTF-8'
        if canon not in seen:
            seen.add(canon)
            out.append(canon)
    return sorted(out, key=lambda n: describe(n).lower())


def system_locale():
    res = sysutil.run(['localectl', 'status'])
    m = re.search(r'LANG=(\S+)', res.out)
    return m.group(1) if m else ''


def user_settings():
    return {'language': sysutil.kread('plasma-localerc', 'Translations', 'LANGUAGE', ''),
            'lang': sysutil.kread('plasma-localerc', 'Formats', 'LANG', ''),
            **{k: sysutil.kread('plasma-localerc', 'Formats', k, '') for k, _t in FORMAT_KEYS}}


def check(locale_name):
    if not LOC_OK.match(locale_name or ''):
        raise ValueError('Invalid locale.')
    return locale_name


def set_language(locale_name):
    """Display language for this user (applies at the next login)."""
    check(locale_name)
    sysutil.kwrite('plasma-localerc', 'Formats', 'LANG', locale_name)
    sysutil.kwrite('plasma-localerc', 'Translations', 'LANGUAGE', locale_name.split('.')[0] + ':en_US')
    return user_settings()


def set_format(key, locale_name):
    if key not in dict(FORMAT_KEYS):
        raise ValueError('Unknown format.')
    check(locale_name)
    sysutil.kwrite('plasma-localerc', 'Formats', key, locale_name)
    return user_settings()


def set_all_formats(locale_name):
    check(locale_name)
    for key, _t in FORMAT_KEYS:
        sysutil.kwrite('plasma-localerc', 'Formats', key, locale_name)
    return user_settings()


def clear_format(key):
    if key not in dict(FORMAT_KEYS):
        raise ValueError('Unknown format.')
    sysutil.kwrite('plasma-localerc', 'Formats', key, '')
    return user_settings()
