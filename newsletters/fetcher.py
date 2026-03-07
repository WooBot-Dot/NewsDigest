#!/usr/bin/env python3
"""
fetcher.py

Fetch top free articles from NRK, VG, Dagbladet, E24, Aftenposten (fallback).
- Follow front-page links and collect up to N articles per source
- Extract canonical URL, headline, publish time (if available), and first paragraphs
- Deduplicate against index.json
- Translate headline+summary to Simplified Chinese using DeepL if DEEPL_API_KEY is set
- Save HTML and Markdown in archive/YYYY-MM-DD.{html,md} and update index.json

Requirements: requests, beautifulsoup4
Install: pip install requests beautifulsoup4

Environment:
- DEEPL_API_KEY (optional) - if present, will translate via DeepL API (https://api-free.deepl.com/v2/translate)

Run: python fetcher.py
"""
import os
import sys
import json
import time
from datetime import datetime
from urllib.parse import urljoin, urlparse
import requests
from bs4 import BeautifulSoup

ROOT = os.path.dirname(__file__)
ARCHIVE = os.path.join(ROOT, 'news')
if not os.path.exists(ARCHIVE):
    os.makedirs(ARCHIVE)
INDEX_PATH = os.path.join(ROOT, 'index.json')
if not os.path.exists(INDEX_PATH):
    with open(INDEX_PATH, 'w', encoding='utf8') as f:
        json.dump([], f)

with open(INDEX_PATH, 'r', encoding='utf8') as f:
    seen = set(json.load(f))

SOURCES = [
    'https://www.nrk.no',
    'https://www.vg.no',
    'https://www.dagbladet.no',
    'https://e24.no',
    'https://www.aftenposten.no',
]
PER_SOURCE_LIMIT = 15
USER_AGENT = 'NewsDigestFetcher/1.0 (+https://example.local)'
TIMEOUT = 10
DEEPL_KEY = os.getenv('DEEPL_API_KEY')

session = requests.Session()
session.headers.update({'User-Agent': USER_AGENT})

def fetch_url(url):
    try:
        r = session.get(url, timeout=TIMEOUT)
        r.raise_for_status()
        return r.text, r.url
    except Exception as e:
        print(f'Failed to fetch {url}: {e}', file=sys.stderr)
        return None, url

def extract_links(html, base):
    soup = BeautifulSoup(html, 'html.parser')
    links = []
    for a in soup.find_all('a', href=True):
        href = a['href']
        if href.startswith('#') or href.startswith('mailto:'):
            continue
        full = urljoin(base, href)
        # only same-host links
        if urlparse(full).netloc.endswith(urlparse(base).netloc):
            links.append(full)
    # preserve order, unique
    seen_l = set()
    out = []
    for u in links:
        if u not in seen_l:
            seen_l.add(u)
            out.append(u)
    return out

def extract_article(html, url):
    soup = BeautifulSoup(html, 'html.parser')
    # title
    title = None
    if soup.find('meta', property='og:title'):
        title = soup.find('meta', property='og:title').get('content')
    if not title and soup.title:
        title = soup.title.string.strip()
    # time
    t = None
    meta_time = soup.find('meta', attrs={'property':'article:published_time'}) or soup.find('meta', attrs={'name':'pubdate'})
    if meta_time and meta_time.get('content'):
        t = meta_time.get('content')
    else:
        time_tag = soup.find('time')
        if time_tag and time_tag.get('datetime'):
            t = time_tag.get('datetime')
    # summary: first 2 non-empty <p>
    paras = []
    for p in soup.find_all('p'):
        text = p.get_text().strip()
        if text and len(text) > 40:
            paras.append(text)
        if len(paras) >= 2:
            break
    summary = '\n\n'.join(paras)
    return title or '', t or '', summary or ''

def translate_text(text, target_lang='ZH'):
    if not DEEPL_KEY:
        return None
    url = 'https://api-free.deepl.com/v2/translate'
    try:
        r = requests.post(url, data={
            'auth_key': DEEPL_KEY,
            'text': text,
            'target_lang': target_lang,
            'tag_handling': 'html'
        }, timeout=10)
        r.raise_for_status()
        data = r.json()
        if 'translations' in data and len(data['translations'])>0:
            return data['translations'][0].get('text')
    except Exception as e:
        print(f'Deepl translation failed: {e}', file=sys.stderr)
    return None

collected = []
cutoff = datetime.utcnow().astimezone().isoformat()
now = datetime.now().strftime('%Y-%m-%d')

for src in SOURCES:
    print(f'Visiting {src}...')
    html, final = fetch_url(src)
    if not html:
        continue
    links = extract_links(html, final)
    count = 0
    for link in links:
        if count >= PER_SOURCE_LIMIT:
            break
        # skip if already seen
        canon = link.split('?')[0].rstrip('/')
        if canon in seen:
            continue
        # skip resource files
        if any(link.endswith(ext) for ext in ['.jpg','.png','.gif','.pdf']):
            continue
        art_html, art_final = fetch_url(link)
        if not art_html:
            continue
        title, pubtime, summary = extract_article(art_html, art_final)
        if not title and not summary:
            continue
        # hopeful free content: heuristic - skip if contains 'e-avis' or 'logg inn' or 'betal'
        lower = art_html.lower()
        paywalled = False
        if 'logg inn' in lower or 'betal' in lower or 'abonner' in lower or 'e-avis' in lower:
            paywalled = True
        # translate
        to_translate = title + '\n\n' + (summary[:1000])
        tr = translate_text(to_translate, target_lang='ZH') if DEEPL_KEY else None
        if tr:
            tr_title = tr.split('\n\n',1)[0]
            tr_summary = tr.split('\n\n',1)[1] if '\n\n' in tr else ''
        else:
            tr_title = ''
            tr_summary = ''
        item = {
            'source': src,
            'url': art_final,
            'canonical': canon,
            'title': title,
            'title_cn': tr_title,
            'pubtime': pubtime,
            'summary': summary,
            'summary_cn': tr_summary,
            'paywalled': paywalled
        }
        collected.append(item)
        seen.add(canon)
        count += 1
        time.sleep(0.5)

# write outputs
md_lines = []
md_lines.append(f'# Norway Daily News Digest — {now} (generated)')
md_lines.append(f'Collected up to: {cutoff}')
md_lines.append('')
for i,item in enumerate(collected, start=1):
    md_lines.append(f'{i}. {item["title_cn"] or item["title"]}')
    md_lines.append('')
    md_lines.append(f'   - Original: "{item["title"]}" — {item["source"]}')
    md_lines.append(f'   - Time: {item["pubtime"] or "time not available"}')
    md_lines.append(f'   - Link: {item["url"]}')
    md_lines.append('')
    md_lines.append(f'   - Summary: {item["summary_cn"] or item["summary"][:500]}')
    md_lines.append('')

md_content = '\n'.join(md_lines)
md_path = os.path.join(ARCHIVE, f'{now}.md')
with open(md_path, 'w', encoding='utf8') as f:
    f.write(md_content)
print('Wrote', md_path)

# simple HTML
html_lines = ['<!doctype html>','<html><head><meta charset="utf-8"><title>Norway Daily News Digest</title></head><body>']
html_lines.append(f'<h1>Norway Daily News Digest — {now}</h1>')
html_lines.append(f'<p>Collected up to: {cutoff}</p>')
for i,item in enumerate(collected, start=1):
    html_lines.append('<div class="item">')
    html_lines.append(f'<h2>{i}. {item["title_cn"] or item["title"]}</h2>')
    html_lines.append(f'<p class="meta">Published: {item["pubtime"] or "time not available"}</p>')
    html_lines.append(f'<p class="source">Original: "{item["title"]}" — <a href="{item["url"]}">原文链接</a></p>')
    html_lines.append(f'<p>{item["summary_cn"] or item["summary"]}</p>')
    if item['paywalled']:
        html_lines.append('<p><em>[Paywalled — summarized from preview]</em></p>')
    html_lines.append('</div>')

html_lines.append('</body></html>')
html_path = os.path.join(ARCHIVE, f'{now}.html')
with open(html_path, 'w', encoding='utf8') as f:
    f.write('\n'.join(html_lines))
print('Wrote', html_path)

# update index
with open(INDEX_PATH, 'w', encoding='utf8') as f:
    json.dump(list(seen), f, ensure_ascii=False, indent=2)
print('Updated index.json with', len(seen), 'items')

# Optionally: post to channel — left as manual step or integrate with messaging API
print('Done')
