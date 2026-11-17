"""Google Gemini client.

Each person brings their own API key, so every call takes the key as an argument;
nothing here reads a key from the environment.
"""
import json
import os
import re
from urllib.parse import quote

import requests

from .util import ApiError, to_str


def BASE():
    return (os.environ.get('GEMINI_BASE_URL') or 'https://generativelanguage.googleapis.com').rstrip('/')


def MODEL():
    return os.environ.get('GEMINI_MODEL') or 'gemini-2.5-flash'


def clip(s, n):
    return re.sub(r'\s+', ' ', to_str(s) if s else '').strip()[:n]


def city(addr):
    m = re.search(r"([A-Za-zÀ-ÿ' -]+)\s+\d{4,5}\s*$", str(addr or ''))
    return m.group(1).strip() if m else 'Marrakech'


def _json(r):
    try:
        return r.json()
    except ValueError:
        return {}


def api_error(status, j):
    """Turn Gemini's error shapes into something worth showing a person."""
    message = ((j or {}).get('error') or {}).get('message') if isinstance(j, dict) else None
    message = message or f'HTTP {status}'
    if status == 400 and re.search(r'API key not valid', message, re.I):
        return ApiError('That API key was refused by Google. Check it and try again.')
    if status == 403:
        return ApiError('This key is not allowed to use the Gemini API. Enable the Generative Language API for it.')
    if status == 429:
        return ApiError('Gemini rate limit reached. Wait a moment and try again.')
    return ApiError('Gemini: ' + message)


def generate(api_key, system, messages, json_mode=False, max_tokens=2048, temperature=0.7):
    """One call to generateContent.

    messages is a list of {'role': 'user'|'model', 'text': ...}. Returns {'text', 'model'}.
    """
    if not api_key:
        raise ApiError('No Gemini API key set.', code='NO_KEY')
    model = MODEL()
    gen = {'maxOutputTokens': max_tokens, 'temperature': temperature}
    if json_mode:
        gen['responseMimeType'] = 'application/json'
    body = {
        'contents': [{'role': 'model' if m['role'] == 'model' else 'user', 'parts': [{'text': m['text']}]} for m in messages],
        'generationConfig': gen,
    }
    if system:
        body['system_instruction'] = {'parts': [{'text': system}]}
    # The 2.5 models think before answering. These are short, factual replies, so
    # skipping that keeps them fast and stops thinking tokens eating the budget.
    if '2.5' in model:
        gen['thinkingConfig'] = {'thinkingBudget': 0}

    try:
        r = requests.post(f"{BASE()}/v1beta/models/{quote(model, safe='')}:generateContent",
                          headers={'x-goog-api-key': api_key, 'content-type': 'application/json'},
                          data=json.dumps(body), timeout=45)
    except requests.Timeout:
        raise ApiError('Gemini took too long to answer.')
    except requests.RequestException as e:
        raise ApiError(f'Could not reach Gemini: {e}')
    j = _json(r)
    if not r.ok:
        raise api_error(r.status_code, j)
    candidate = (j.get('candidates') or [None])[0]
    parts = ((candidate or {}).get('content') or {}).get('parts') or []
    text = ''.join(p.get('text') or '' for p in parts).strip()
    if not text:
        reason = (candidate or {}).get('finishReason')
        raise ApiError('Gemini refused to answer that.' if reason == 'SAFETY' else 'Gemini returned no text.')
    return {'text': text, 'model': j.get('modelVersion') or model}


def check_key(api_key):
    """Cheap check that a key works, used before we store it."""
    try:
        r = requests.get(f'{BASE()}/v1beta/models', headers={'x-goog-api-key': api_key}, timeout=20)
    except requests.RequestException as e:
        raise ApiError(f'Could not reach Google to check the key: {e}')
    if not r.ok:
        raise api_error(r.status_code, _json(r))
    return True


# ---------- first-contact email ----------

def system_prompt(lang):
    return '\n'.join([
        'You write short first-contact emails on behalf of one sender.',
        'Use only the facts given in <sender> and <company>. Never invent clients, results, prices, deadlines, mutual contacts, or details about the company that are not given.',
        'Be specific when the facts allow it, otherwise stay general. No flattery clichés, no exclamation marks, no emojis.',
        f"Write in {'English' if lang == 'en' else 'French'}. Maximum 120 words in the body. One clear, low-pressure ask. Plain text, no markdown.",
        'Start the body with a greeting. Do not write a signature, a sign-off name, or an opt-out line: the app adds them.',
        'Reply with JSON only, in this shape: {"subject":"...","body":"..."}',
    ])


def user_prompt(ctx):
    lead, settings = ctx['lead'], ctx['settings']
    s = settings.get('sender') or {}
    background = clip(s.get('background'), 600) or 'not specified, stay general'
    if ctx['goal'] == 'pitch':
        goal_text = f'Introduce a service and offer a short call. What the sender offers: {background}.'
    else:
        period = f" ({clip(settings.get('period'), 80)})" if settings.get('period') else ''
        goal_text = f'Send a spontaneous application for an internship{period}. Sender background: {background}.'
    company = (f"<company><name>{clip(lead.get('nom'), 120)}</name><category>{clip(lead.get('categorie'), 60)}</category>"
               f"<city>{city(lead.get('adresse'))}</city>")
    if lead.get('note'):
        company += f"<google_rating>{to_str(lead['note'])} ({to_str(lead.get('nombre_avis') or 0)} reviews)</google_rating>"
    if lead.get('site_web'):
        company += f"<website>{clip(lead['site_web'], 120)}</website>"
    company += '</company>'
    lines = [
        f'<goal>{goal_text}</goal>',
        f"<tone>{clip(ctx.get('tone'), 40) or 'professional'}</tone>",
        f"<sender><name>{clip(s.get('name'), 80)}</name><role>{clip(s.get('role'), 160)}</role></sender>",
        company,
        f"<extra_instructions>{clip(ctx['extra'], 300)}</extra_instructions>" if ctx.get('extra') else '',
    ]
    return '\n'.join(x for x in lines if x)


def parse_draft(text):
    a, b = text.find('{'), text.rfind('}')
    if a >= 0 and b > a:
        try:
            j = json.loads(text[a:b + 1])
            if isinstance(j, dict) and j.get('subject') and j.get('body'):
                return {'subject': to_str(j['subject']).strip(), 'body': to_str(j['body']).strip()}
        except ValueError:
            pass
    lines = text.strip().split('\n')
    subj = re.sub(r'^subject:\s*', '', lines.pop(0), flags=re.I).strip()
    return {'subject': subj[:120], 'body': '\n'.join(lines).strip()}


def draft_email(ctx, api_key):
    out = generate(api_key, system_prompt(ctx['language']), [{'role': 'user', 'text': user_prompt(ctx)}],
                   json_mode=True, max_tokens=900)
    return {**parse_draft(out['text']), 'ai': True, 'model': out['model']}


def template_draft(ctx):
    """Plain template used when the person has not set a key. Facts only, filled from settings."""
    lead, settings, goal = ctx['lead'], ctx['settings'], ctx['goal']
    s = settings.get('sender') or {}
    fr = ctx['language'] != 'en'
    name = re.split(r'\s[-–|]\s', lead.get('nom') or '')[0]
    role = ', ' + s['role'] if s.get('role') else ''
    period = settings.get('period')
    if goal == 'pitch':
        if fr:
            return {
                'subject': f'Une idée pour {name}',
                'body': f"Bonjour,\n\nJe m'appelle {s.get('name') or '[votre nom]'}{role}. {clip(s.get('background'), 300) or '[décrivez en une phrase ce que vous proposez]'}\n\nSeriez-vous disponible pour un échange de 15 minutes cette semaine ou la suivante ?\n\nCordialement,",
            }
        return {
            'subject': f'An idea for {name}',
            'body': f"Hello,\n\nMy name is {s.get('name') or '[your name]'}{role}. {clip(s.get('background'), 300) or '[describe what you offer in one sentence]'}\n\nWould you have 15 minutes for a call this week or next?\n\nBest regards,",
        }
    if fr:
        return {
            'subject': 'Candidature spontanée' + (' : ' + clip(period, 60) if period else ' pour un stage'),
            'body': f"Bonjour,\n\nJe m'appelle {s.get('name') or '[votre nom]'}{role}. {clip(s.get('background'), 300)}\n\nJe vous écris pour proposer ma candidature à un stage{' (' + clip(period, 60) + ')' if period else ''} au sein de {name}. Seriez-vous disposé à échanger quelques minutes à ce sujet ?\n\nCordialement,",
        }
    return {
        'subject': 'Internship application' + (': ' + clip(period, 60) if period else ''),
        'body': f"Hello,\n\nMy name is {s.get('name') or '[your name]'}{role}. {clip(s.get('background'), 300)}\n\nI am writing to apply for an internship{' (' + clip(period, 60) + ')' if period else ''} at {name}. Would you be open to a short conversation about it?\n\nBest regards,",
    }


# ---------- CV ----------

CV_SECTIONS = ('experience', 'education', 'projects')


def cv_system_prompt(lang):
    return '\n'.join([
        'You turn the notes a person gives about themselves into a short, clean CV.',
        'Use only the facts in <profile> and <cv_input>. Never invent an employer, school, date, grade, tool, '
        'number or achievement. If a section has no facts, return an empty list for it.',
        'Rewrite the notes into concise, active bullet points (at most 3 per item, 18 words each). Fix spelling. '
        'Keep periods exactly as given.',
        'The summary is two sentences at most, aimed at the target given, in plain words with no buzzwords.',
        f"Write in {'English' if lang == 'en' else 'French'}. Plain text inside the JSON, no markdown.",
        'Reply with JSON only, in this shape: {"summary":"...","experience":[{"title":"","org":"","period":"",'
        '"points":[""]}],"education":[{"title":"","org":"","period":"","points":[""]}],'
        '"projects":[{"title":"","org":"","period":"","points":[""]}],"skills":[""],"languages":[""]}',
    ])


def cv_user_prompt(profile, data):
    p = profile
    return '\n'.join([
        f"<profile><name>{clip(p.get('fullName'), 120)}</name><headline>{clip(p.get('headline'), 160)}</headline>"
        f"<city>{clip(p.get('city'), 80)}</city><background>{clip(p.get('background'), 1500)}</background></profile>",
        '<cv_input>',
        f"<target>{clip(data.get('target'), 200) or 'an internship'}</target>",
        f"<experience>{to_str(data.get('experience'))[:4000]}</experience>",
        f"<education>{to_str(data.get('education'))[:3000]}</education>",
        f"<projects>{to_str(data.get('projects'))[:3000]}</projects>",
        f"<skills>{to_str(data.get('skills'))[:1000]}</skills>",
        f"<languages>{to_str(data.get('languages'))[:500]}</languages>",
        '</cv_input>',
    ])


def _items(v, limit=12):
    out = []
    for it in (v if isinstance(v, list) else [])[:limit]:
        if not isinstance(it, dict):
            continue
        item = {k: to_str(it.get(k)).strip()[:160] for k in ('title', 'org', 'period')}
        item['points'] = [to_str(x).strip()[:240] for x in (it.get('points') or []) if to_str(x).strip()][:4] \
            if isinstance(it.get('points'), list) else []
        if item['title'] or item['org'] or item['points']:
            out.append(item)
    return out


def _words(v, limit=30):
    return [to_str(x).strip()[:60] for x in (v if isinstance(v, list) else []) if to_str(x).strip()][:limit]


def normalize_cv(j):
    """Keep only the shape the page knows how to show, whatever the model returned."""
    j = j if isinstance(j, dict) else {}
    out = {'summary': to_str(j.get('summary')).strip()[:600]}
    for k in CV_SECTIONS:
        out[k] = _items(j.get(k))
    out['skills'] = _words(j.get('skills'))
    out['languages'] = _words(j.get('languages'), 10)
    return out


def _blocks(text):
    """Notes typed as blocks separated by a blank line: first line is the title, the rest are points.

    A first line like "Developer — Acme (2025)" is split into title, organisation and period.
    """
    items = []
    for block in re.split(r'\n\s*\n', to_str(text).strip()):
        lines = [l.strip(' -•\t') for l in block.splitlines() if l.strip(' -•\t')]
        if not lines:
            continue
        head, period = lines[0], ''
        m = re.search(r'\(([^()]*\d[^()]*)\)\s*$', head)
        if m:
            period, head = m.group(1).strip(), head[:m.start()].strip()
        parts = re.split(r'\s+[—–|@]\s+|\s+-\s+|\s+at\s+|\s+chez\s+', head, maxsplit=1)
        title, org = (parts[0], parts[1]) if len(parts) == 2 else (head, '')
        items.append({'title': title, 'org': org, 'period': period, 'points': lines[1:]})
    return items


def plain_cv(data):
    """The CV without AI: the person's own notes, laid out as they typed them."""
    split = lambda v: [x.strip() for x in re.split(r'[,\n;]', to_str(v)) if x.strip()]  # noqa: E731
    return normalize_cv({
        'summary': to_str(data.get('summary')).strip(),
        'experience': _blocks(data.get('experience')),
        'education': _blocks(data.get('education')),
        'projects': _blocks(data.get('projects')),
        'skills': split(data.get('skills')),
        'languages': split(data.get('languages')),
    })


def generate_cv(profile, data, language, api_key):
    out = generate(api_key, cv_system_prompt(language), [{'role': 'user', 'text': cv_user_prompt(profile, data)}],
                   json_mode=True, max_tokens=2048, temperature=0.4)
    text = out['text']
    a, b = text.find('{'), text.rfind('}')
    try:
        j = json.loads(text[a:b + 1]) if a >= 0 and b > a else None
    except ValueError:
        j = None
    if not isinstance(j, dict):
        raise ApiError('Gemini did not return a CV in the expected shape. Try again.')
    return {**normalize_cv(j), 'model': out['model']}
