"""
ADR Parts - Email Sender Cloud Function
Odesílá HTML e-maily:
  - type 'order'      → interní objednávka na ORDER_EMAIL + potvrzení zákazníkovi
  - type 'withdrawal' → odstoupení od smlouvy na ORDER_EMAIL + kopie zákazníkovi
  - type 'offer'      → nabídka zákazníkovi (+ kopie na ORDER_EMAIL), PDF v příloze;
                        smí odeslat jen přihlášený admin (Firebase ID token v Authorization)

Odesílatel všech e-mailů = SMTP_USER (adr.parts.cz@gmail.com).
Odpovědi zákazníků jdou na REPLY_TO (info@fimas.cz).

Proměnné prostředí (nastavují se při deployi):
  SMTP_USER   - adr.parts.cz@gmail.com
  SMTP_PASS   - heslo aplikace Google pro adr.parts.cz@gmail.com (16 znaků, bez mezer)
  ORDER_EMAIL - kam chodí objednávky (TEST: adr@fimas.cz → PRODUKCE: fimasinfo@gmail.com)
  REPLY_TO    - adresa pro odpovědi zákazníků (výchozí info@fimas.cz)
"""
import functions_framework
import smtplib
import json
import os
import re
import html as htmllib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.application import MIMEApplication
import base64
from email.utils import formataddr, make_msgid, formatdate

SMTP_HOST = 'smtp.gmail.com'
SMTP_PORT = 587
SENDER_NAME = 'ADR Parts – FIMAS s.r.o.'
EMAIL_RE = re.compile(r'^[^@\s<>,;]+@[^@\s<>,;]+\.[^@\s<>,;]+$')
PROJECT_ID = 'adr-fimas'
ADMIN_EMAILS = {'pajulinux@gmail.com'}  # stejný seznam jako ADMIN_EMAILS v index.html a firestore.rules
MAX_ATTACHMENT = 8 * 1024 * 1024


def _admin_from_token(request):
    """Ověří Firebase ID token z hlavičky Authorization; vrátí e-mail admina nebo None."""
    auth = request.headers.get('Authorization', '')
    if not auth.startswith('Bearer '):
        return None
    try:
        from google.oauth2 import id_token
        from google.auth.transport import requests as grequests
        claims = id_token.verify_firebase_token(auth[7:], grequests.Request(), audience=PROJECT_ID)
    except Exception:
        return None
    email = (claims or {}).get('email', '').lower()
    if claims and claims.get('email_verified') and email in ADMIN_EMAILS:
        return email
    return None


def _cors():
    return {
        'Access-Control-Allow-Origin': '*',
        'Access-Control-Allow-Methods': 'POST, OPTIONS',
        'Access-Control-Allow-Headers': 'Content-Type, Authorization',
        'Access-Control-Max-Age': '3600',
    }


@functions_framework.http
def send_order_email(request):
    """HTTP Cloud Function to send order / withdrawal emails."""
    if request.method == 'OPTIONS':
        return ('', 204, _cors())

    headers = {'Access-Control-Allow-Origin': '*', 'Content-Type': 'application/json'}

    if request.method != 'POST':
        return (json.dumps({'error': 'Only POST allowed'}), 405, headers)

    try:
        data = request.get_json(silent=True)
        if not data:
            return (json.dumps({'error': 'No JSON body'}), 400, headers)

        msg_type = data.get('type', 'order')
        html_content = data.get('html', '')
        customer_html = data.get('customerHtml') or html_content
        customer_email = (data.get('customerEmail') or '').strip()
        order_number = data.get('orderNumber', '')
        subject_text = data.get('subject', f'Objednávka ADR Parts č. {order_number}')

        if not html_content:
            return (json.dumps({'error': 'Missing html content'}), 400, headers)

        smtp_user = os.environ.get('SMTP_USER', '')
        smtp_pass = os.environ.get('SMTP_PASS', '')
        order_email = os.environ.get('ORDER_EMAIL', 'adr@fimas.cz')
        reply_to = os.environ.get('REPLY_TO', 'info@fimas.cz')

        if not smtp_user or not smtp_pass:
            return (json.dumps({'error': 'SMTP not configured'}), 500, headers)

        attachments = []
        if msg_type == 'offer':
            if not _admin_from_token(request):
                return (json.dumps({'error': 'Nabídku může odeslat jen přihlášený administrátor'}), 403, headers)
            if not (customer_email and EMAIL_RE.match(customer_email)):
                return (json.dumps({'error': 'Neplatný e-mail zákazníka'}), 400, headers)
            for a in (data.get('attachments') or [])[:3]:
                raw = base64.b64decode(a.get('contentBase64', ''), validate=False)
                if raw and len(raw) <= MAX_ATTACHMENT:
                    name = re.sub(r'[^A-Za-z0-9._-]', '_', a.get('filename') or 'priloha.pdf')
                    attachments.append((name, raw))

        if msg_type == 'offer':
            internal_subject = f'[NABÍDKA] {subject_text}'
            customer_subject = subject_text
        elif msg_type == 'withdrawal':
            internal_subject = f'[ODSTOUPENÍ OD SMLOUVY] {subject_text}'
            customer_subject = f'Potvrzení přijetí odstoupení od smlouvy – {order_number}'
        else:
            internal_subject = f'[OBJEDNÁVKA] {subject_text}'
            customer_subject = f'Potvrzení objednávky {order_number} – ADR Parts (FIMAS s.r.o.)'

        valid_customer = bool(customer_email and EMAIL_RE.match(customer_email))
        sent_to, errors = [], []

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT, timeout=30) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)

            # 1) Interní e-mail pro FIMAS – odpověď půjde přímo zákazníkovi
            try:
                _send(server, smtp_user, order_email, internal_subject, html_content,
                      reply_to=customer_email if valid_customer else reply_to, attachments=attachments)
                sent_to.append(order_email)
            except Exception as e:
                errors.append(f'FIMAS: {e}')

            # 2) Potvrzení zákazníkovi z adr.parts.cz@gmail.com, odpověď na info@fimas.cz
            if valid_customer:
                try:
                    _send(server, smtp_user, customer_email, customer_subject, customer_html,
                          reply_to=reply_to, attachments=attachments)
                    sent_to.append(customer_email)
                except Exception as e:
                    errors.append(f'Customer: {e}')
            elif customer_email:
                errors.append('Customer: invalid e-mail address')

        ok_target = customer_email if msg_type == 'offer' else order_email
        result = {'success': ok_target in sent_to, 'sentTo': sent_to}
        if errors:
            result['errors'] = errors
        return (json.dumps(result), 200 if result['success'] else 500, headers)

    except Exception as e:
        return (json.dumps({'error': str(e)}), 500, headers)


def _send(server, from_addr, to_addr, subject, html, reply_to=None, attachments=None):
    msg = MIMEMultipart('mixed') if attachments else MIMEMultipart('alternative')
    msg['From'] = formataddr((SENDER_NAME, from_addr))
    msg['To'] = to_addr
    msg['Subject'] = subject
    msg['Date'] = formatdate(localtime=True)
    msg['Message-ID'] = make_msgid(domain='adrparts.cz')
    if reply_to:
        msg['Reply-To'] = reply_to

    plain = re.sub(r'<(script|style)[^>]*>.*?</\1>', '', html, flags=re.S | re.I)
    plain = re.sub(r'<br\s*/?>|</p>|</tr>|</h\d>|</div>', '\n', plain, flags=re.I)
    plain = re.sub(r'<[^>]+>', ' ', plain)
    plain = htmllib.unescape(plain)
    plain = re.sub(r'[ \t]+', ' ', plain)
    plain = re.sub(r'\n\s*\n+', '\n\n', plain).strip()

    body = MIMEMultipart('alternative') if attachments else msg
    body.attach(MIMEText(plain, 'plain', 'utf-8'))
    body.attach(MIMEText(html, 'html', 'utf-8'))
    if attachments:
        msg.attach(body)
        for name, raw in attachments:
            part = MIMEApplication(raw, _subtype='pdf' if name.lower().endswith('.pdf') else 'octet-stream')
            part.add_header('Content-Disposition', 'attachment', filename=name)
            msg.attach(part)
    server.sendmail(from_addr, [to_addr], msg.as_string())
