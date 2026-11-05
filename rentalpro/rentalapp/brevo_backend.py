"""
Django email backend that sends mail through Brevo's transactional HTTPS API.

Why: Render's free plan blocks outbound SMTP ports (25/465/587), so Django's
normal SMTP backend cannot connect. HTTPS (port 443) is not blocked.
Uses only the Python standard library, so no new dependency is needed.
"""

import base64
import json
import logging
import time
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend
from django.utils.html import strip_tags

logger = logging.getLogger(__name__)

DEFAULT_BREVO_API_URL = 'https://api.brevo.com/v3/smtp/email'
USER_AGENT = 'rental-marketplace-django/1.0'
MAX_ATTEMPTS = 3


class BrevoEmailBackend(BaseEmailBackend):

    def send_messages(self, email_messages):
        if not email_messages:
            return 0

        api_key = getattr(settings, 'BREVO_API_KEY', '').strip()
        if not api_key:
            message = 'BREVO_API_KEY is not set; email not sent.'
            logger.error(message)
            if self.fail_silently:
                return 0
            raise ValueError(message)

        if api_key.startswith('xsmtpsib-'):
            # SMTP keys don't work with the HTTP API; this is the most common mistake.
            message = (
                'BREVO_API_KEY is an SMTP key (starts with xsmtpsib-). '
                'Create a v3 API key instead (starts with xkeysib-).'
            )
            logger.error(message)
            if self.fail_silently:
                return 0
            raise ValueError(message)

        sent = 0
        for email_message in email_messages:
            try:
                self._send(email_message, api_key)
                sent += 1
            except Exception:
                logger.exception('Brevo email send failed to %s', email_message.to)
                if not self.fail_silently:
                    raise
        return sent

    def _build_payload(self, message):
        from_header = message.from_email or settings.DEFAULT_FROM_EMAIL
        sender_name, sender_email = parseaddr(from_header)
        if not sender_email:
            raise ValueError(f'Invalid DEFAULT_FROM_EMAIL/from address: {from_header!r}')

        sender = {'email': sender_email}
        if sender_name:
            sender['name'] = sender_name

        payload = {
            'sender': sender,
            'to': [{'email': addr} for _, addr in map(parseaddr, message.to) if addr],
            'subject': message.subject,
            'textContent': message.body or ' ',
        }

        html = None
        for content, mimetype in getattr(message, 'alternatives', []):
            if mimetype == 'text/html':
                html = content
                break
        if html is None and message.content_subtype == 'html':
            html = message.body
        if html:
            payload['htmlContent'] = html
            if message.content_subtype == 'html':
                payload['textContent'] = strip_tags(message.body) or ' '

        if message.cc:
            payload['cc'] = [{'email': addr} for _, addr in map(parseaddr, message.cc) if addr]
        if message.bcc:
            payload['bcc'] = [{'email': addr} for _, addr in map(parseaddr, message.bcc) if addr]
        if message.reply_to:
            reply_name, reply_email = parseaddr(message.reply_to[0])
            if reply_email:
                payload['replyTo'] = {'email': reply_email}
                if reply_name:
                    payload['replyTo']['name'] = reply_name

        attachments = []
        for attachment in message.attachments:
            if isinstance(attachment, tuple):
                filename, content, _mimetype = attachment
                if isinstance(content, str):
                    content = content.encode('utf-8')
                attachments.append({
                    'name': filename,
                    'content': base64.b64encode(content).decode('ascii'),
                })
        if attachments:
            payload['attachment'] = attachments

        return payload

    def _send(self, message, api_key):
        payload = self._build_payload(message)
        body = json.dumps(payload).encode('utf-8')
        api_url = getattr(settings, 'BREVO_API_URL', DEFAULT_BREVO_API_URL)
        timeout = getattr(settings, 'EMAIL_TIMEOUT', 10)
        headers = {
            'api-key': api_key,
            'accept': 'application/json',
            'content-type': 'application/json',
            # Without a User-Agent, some CDN/WAF layers reject urllib requests.
            'User-Agent': USER_AGENT,
        }

        last_error = None
        for attempt in range(1, MAX_ATTEMPTS + 1):
            request = urllib.request.Request(api_url, data=body, headers=headers, method='POST')
            try:
                with urllib.request.urlopen(request, timeout=timeout) as response:
                    result = json.loads(response.read().decode('utf-8') or '{}')
                logger.info('Brevo accepted email to %s (messageId=%s)',
                            payload['to'], result.get('messageId'))
                return
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode('utf-8', 'replace')
                error = RuntimeError(f'Brevo API error {exc.code}: {detail}')
                # 400/401/403 (bad sender, bad key, bad payload) won't fix on retry.
                # 429 (rate limit) and 5xx are transient, so retry those.
                if 400 <= exc.code < 500 and exc.code != 429:
                    raise error from exc
                last_error = error
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc

            if attempt < MAX_ATTEMPTS:
                time.sleep(attempt)

        raise last_error
