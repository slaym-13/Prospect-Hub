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
