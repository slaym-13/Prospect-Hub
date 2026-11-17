#!/usr/bin/env python3
"""Prospect Ledger v2: website checker.

    python enrich.py companies.json            -> writes enrichment.json
    python enrich.py companies.json out.json --concurrency 8 --timeout 15000 --force

Needs Python 3.10+ and requests. Run it on your own computer: it visits each
company's website once and records what it finds.

Notes on reading the results:
 - true  = found in the page HTML
 - false = not found in the page HTML
 - missing = could not tell (site is a JavaScript shell, or the page failed)
 Widgets injected late by JavaScript can be missed, so treat "false" as a strong
 hint and confirm on the lead's detail panel before you pitch it.
"""
import argparse
import json
import os
import re
import threading
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from urllib.parse import urlparse

import requests

UA = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36'

RX = {
    'viewport': re.compile(r'<meta[^>]+name=["\']viewport["\']', re.I),
    'whatsapp': re.compile(r'wa\.me/|api\.whatsapp\.com|web\.whatsapp\.com|whatsapp://|joinchat|click-to-chat|ctc-|class=["\'][^"\']*whatsapp', re.I),
    'pixel': re.compile(r'fbq\(|connect\.facebook\.net|googletagmanager\.com|gtag\(|G-[A-Z0-9]{6,}', re.I),
}

CHAT_TOOLS = {
    'tidio': r'tidio', 'crisp': r'crisp\.chat', 'tawk': r'tawk\.to', 'intercom': r'intercom', 'drift': r'js\.driftt?\.com',
    'livechat': r'livechatinc|livechat\.com', 'zendesk': r'zopim|zendesk', 'hubspot': r'hs-scripts|hubspot',
    'manychat': r'manychat', 'botpress': r'botpress', 'smartsupp': r'smartsupp', 'olark': r'olark', 'freshchat': r'freshchat',
    'messenger': r'fb-customerchat|customerchat|m\.me/', 'chatbot': r'chatbot|chat-widget|chatwidget',
}
BOOKING_TOOLS = {
    'calendly': r'calendly', 'simplybook': r'simplybook', 'cloudbeds': r'cloudbeds', 'lodgify': r'lodgify', 'smoobu': r'smoobu',
    'sirvoy': r'sirvoy', 'roomcloud': r'roomcloud', 'beds24': r'beds24', 'checkfront': r'checkfront', 'booksy': r'booksy',
    'zenchef': r'zenchef', 'thefork': r'thefork|lafourchette', 'opentable': r'opentable', 'resiliosoft': r'resiliosoft',
    'form': r'(book(ing)?[ -]?now|réserver|reserver|réservation|reservation|book a (room|table|tour))',
}
CHAT_TOOLS = {k: re.compile(v, re.I) for k, v in CHAT_TOOLS.items()}
BOOKING_TOOLS = {k: re.compile(v, re.I) for k, v in BOOKING_TOOLS.items()}

SOCIAL_HOST = re.compile(r'(facebook\.com|instagram\.com|linktr\.ee|wa\.me|tiktok\.com|youtube\.com|linkedin\.com|booking\.com|'
                         r'tripadvisor\.|airbnb\.|business\.site|g\.page|goo\.gl|maps\.app)', re.I)


def match_all(table, html):
    return [k for k, rx in table.items() if rx.search(html)]


def text_length(html):
    t = re.sub(r'<script[\s\S]*?</script>', ' ', html, flags=re.I)
    t = re.sub(r'<style[\s\S]*?</style>', ' ', t, flags=re.I)
    t = re.sub(r'<[^>]+>', ' ', t)
    return len(re.sub(r'\s+', ' ', t).strip())


def analyze(html, final_url, status):
    out = {'status': status, 'finalUrl': final_url, 'https': final_url.lower().startswith('https:')}
    # Bot walls (403, 429, ...) say nothing about whether the site is up.
    if status in (401, 403, 406, 429, 451, 999):
        out['blocked'] = True
        return out
    out['live'] = status < 400 and len(html) > 200
    if not out['live']:
        return out

    out['mobile'] = bool(RX['viewport'].search(html))
    t = re.search(r'<title[^>]*>([\s\S]*?)</title>', html, re.I)
    if t:
        out['title'] = re.sub(r'\s+', ' ', t.group(1)).strip()[:120]

    # A near-empty body usually means a JavaScript app; absence of widgets
    # in the HTML then proves nothing, so leave those fields unknown.
    shell = text_length(html) < 400
    w = bool(RX['whatsapp'].search(html))
    chat = match_all(CHAT_TOOLS, html)
    book = match_all(BOOKING_TOOLS, html)
    if w or not shell:
        out['whatsapp'] = w
    if chat or not shell:
        out['chat'] = bool(chat)
        if chat:
            out['chatTools'] = chat
    if book or not shell:
        out['booking'] = bool(book)
        if book:
            out['bookingTools'] = book
    out['pixel'] = bool(RX['pixel'].search(html))

    emails = []
    for e in re.findall(r'[a-z0-9._%+-]+@[a-z0-9.-]+\.[a-z]{2,}', html, re.I):
        e = e.lower()
        if re.search(r'\.(png|jpe?g|gif|svg|webp)$', e) or re.search(r'(sentry|wixpress|example\.)', e) or e in emails:
            continue
        emails.append(e)
    if emails:
        out['emails'] = emails[:3]

    social = {}
    ig = re.search(r'instagram\.com/([A-Za-z0-9._]{2,30})(?=[/"\'?\s])', html)
    fb = re.search(r'facebook\.com/(?!sharer|tr\?|plugins|dialog|common)([A-Za-z0-9.\-]{3,60})(?=[/"\'?\s])', html)
    if ig and not re.fullmatch(r'p|reel|explore|accounts', ig.group(1)):
        social['instagram'] = 'https://instagram.com/' + ig.group(1)
    if fb:
        social['facebook'] = 'https://facebook.com/' + fb.group(1)
    if social:
        out['social'] = social
    return out


def now_iso():
    return datetime.now(timezone.utc).isoformat(timespec='milliseconds').replace('+00:00', 'Z')


def check(company, timeout_s):
    url = company.get('site_web')
    rec = {'checked': now_iso()}
    if not url:
        return rec
    try:
        host = urlparse(url).hostname or ''
        if not host:
            raise ValueError
    except ValueError:
        rec['error'] = 'bad url'
        return rec
    if SOCIAL_HOST.search(host):
        rec['skipped'] = 'social or listing page'
        return rec
    try:
        r = requests.get(url, timeout=timeout_s, allow_redirects=True,
                         headers={'user-agent': UA, 'accept': 'text/html,application/xhtml+xml', 'accept-language': 'fr,en;q=0.8'})
        rec.update(analyze(r.text[:1_500_000], r.url or url, r.status_code))
    except requests.Timeout:
        rec['live'] = False
        rec['error'] = 'timeout'
    except requests.RequestException as e:
        rec['live'] = False
        rec['error'] = str(e)[:80]
    return rec


def main():
    p = argparse.ArgumentParser(description='Visit each company website once and record what it finds.')
    p.add_argument('infile', nargs='?', default='companies.json')
    p.add_argument('outfile', nargs='?', default='enrichment.json')
    p.add_argument('--concurrency', type=int, default=6)
    p.add_argument('--timeout', type=int, default=12000, help='milliseconds per site')
    p.add_argument('--force', action='store_true', help='check every site again, ignoring earlier results')
    a = p.parse_args()

    with open(a.infile, encoding='utf-8') as f:
        companies = json.load(f)
    items = {}
    if not a.force and os.path.exists(a.outfile):
        try:
            with open(a.outfile, encoding='utf-8') as f:
                items = json.load(f).get('items') or {}
        except (OSError, ValueError):
            pass  # start fresh
    todo = [c for c in companies if c.get('site_web') and c.get('id') not in items]
    print(f"{len(companies)} companies, {sum(1 for c in companies if c.get('site_web'))} with a website, {len(todo)} to check")

    lock = threading.Lock()
    done = 0

    def save():
        with open(a.outfile, 'w', encoding='utf-8') as f:
            json.dump({'kind': 'enrichment', 'generated': now_iso(), 'items': items}, f, indent=1, ensure_ascii=False)

    def work(c):
        nonlocal done
        r = check(c, a.timeout / 1000)
        with lock:
            items[c['id']] = r
            done += 1
            tag = 'skip' if r.get('skipped') else 'ok  ' if r.get('live') else 'DOWN'
            print(f"[{done}/{len(todo)}] {tag} {c.get('nom', '')[:48]}")
            if done % 10 == 0:
                save()

    with ThreadPoolExecutor(max_workers=max(1, a.concurrency)) as pool:
        list(pool.map(work, todo))
    save()
    print(f'Wrote {a.outfile}.')


if __name__ == '__main__':
    main()
