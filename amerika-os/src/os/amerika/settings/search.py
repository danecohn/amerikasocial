"""Search over pages and individual settings (sidebar filter and Ctrl+K quick-jump). Pure Python, no GTK."""
from . import pageindex


def _score(query_words, title, haystack):
    title_l = title.lower()
    score = 0
    for w in query_words:
        if title_l == w:
            score += 100
        elif title_l.startswith(w):
            score += 60
        elif w in title_l:
            score += 40
        elif any(h.startswith(w) for h in haystack):
            score += 20
        elif w in ' '.join(haystack):
            score += 8
        else:
            return 0  # every word must match somewhere
    return score


def search(query, limit=12, available=None):
    """Ranked results: [{'page': id, 'title': str, 'page_title': str, 'kind': 'page'|'setting'}]. Empty query lists all pages."""
    words = [w for w in query.lower().replace('-', ' ').split() if w]
    info = {p['id']: p for p in pageindex.pages()}
    allowed = set(available) if available is not None else set(info)
    out = []
    if not words:
        return [{'page': p['id'], 'title': p['title'], 'page_title': p['title'], 'kind': 'page'} for p in info.values() if p['id'] in allowed][:limit]
    for p in info.values():
        if p['id'] not in allowed:
            continue
        s = _score(words, p['title'], p['keywords'] + p['summary'].lower().split())
        if s:
            out.append((s + 5, {'page': p['id'], 'title': p['title'], 'page_title': p['title'], 'kind': 'page'}))
    for page_id, title, extra in pageindex.ITEMS:
        if page_id not in allowed:
            continue
        s = _score(words, title, extra.split() + info[page_id]['keywords'][:0])
        if s:
            out.append((s, {'page': page_id, 'title': title, 'page_title': info[page_id]['title'], 'kind': 'setting'}))
    out.sort(key=lambda t: -t[0])
    seen, res = set(), []
    for _s, r in out:
        key = (r['page'], r['title'])
        if key not in seen:
            seen.add(key)
            res.append(r)
    return res[:limit]


def matching_pages(query, available=None):
    """Page ids that match (for filtering the sidebar), preserving sidebar order."""
    words = [w for w in query.lower().split() if w]
    if not words:
        return None
    hits = {r['page'] for r in search(query, limit=200, available=available)}
    return hits
