"""Outgoing email over SMTP, or a dry run that only logs."""
import json
import os
import smtplib
from email.message import EmailMessage
from email.utils import formataddr, make_msgid

from .util import ApiError


def mode():
    if os.environ.get('SMTP_MODE') == 'json':
        return 'dry-run'
    if os.environ.get('SMTP_HOST') and os.environ.get('SMTP_USER') and os.environ.get('SMTP_PASS'):
        return 'smtp'
    return 'off'


def _from():
    email = os.environ.get('SMTP_FROM_EMAIL') or os.environ.get('SMTP_USER') or 'dry-run@localhost'
    name = os.environ.get('SMTP_FROM_NAME') or ''
    return email, (formataddr((name, email)) if name else email)


def send(to, subject, text, reply_to=''):
    m = mode()
    if m == 'off':
        raise ApiError('SMTP is not configured. Set SMTP_HOST, SMTP_USER and SMTP_PASS in .env '
                       '(or SMTP_MODE=json for a dry run).', code='NO_SMTP')
    from_email, from_header = _from()
    msg = EmailMessage()
    msg['From'] = from_header
    msg['To'] = to
    msg['Subject'] = subject
    if reply_to:
        msg['Reply-To'] = reply_to
    msg['List-Unsubscribe'] = f'<mailto:{from_email}?subject=stop>'
    msg['Message-ID'] = make_msgid(domain=from_email.split('@')[-1])
    msg.set_content(text)

    if m == 'dry-run':
        print('[dry-run] ' + json.dumps({'to': to, 'subject': subject, 'messageId': msg['Message-ID']}, ensure_ascii=False))
        return {'mode': m, 'messageId': msg['Message-ID']}

    host = os.environ['SMTP_HOST']
    port = int(os.environ.get('SMTP_PORT') or 587)
    if port == 465:
        server = smtplib.SMTP_SSL(host, port, timeout=30)
    else:
        server = smtplib.SMTP(host, port, timeout=30)
    with server:
        if port != 465:
            server.ehlo()
            if server.has_extn('starttls'):
                server.starttls()
                server.ehlo()
        server.login(os.environ['SMTP_USER'], os.environ['SMTP_PASS'])
        server.send_message(msg)
    return {'mode': m, 'messageId': msg['Message-ID']}
