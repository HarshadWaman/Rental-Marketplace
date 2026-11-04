"""
Django email backend that sends mail through Brevo's HTTPS API (port 443).

Why: Render's free plan blocks outbound SMTP ports (25/465/587), so normal
Django SMTP cannot work there. HTTPS is not blocked. Uses only the standard
library, so no new dependency is needed.
"""
import json
import logging
import time
import urllib.error
import urllib.request
from email.utils import parseaddr

from django.conf import settings
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

BREVO_URL = 'https://api.brevo.com/v3/smtp/email'


class BrevoEmailBackend(BaseEmailBackend):
    def send_messages(self, email_messages):
        api_key = getattr(settings, 'BREVO_API_KEY', '')
        if not api_key:
            logger.error('BREVO_API_KEY is not set; email not sent.')
            if not self.fail_silently:
                raise ValueError('BREVO_API_KEY is not set')
            return 0

        sent = 0
        for message in email_messages:
            try:
                self._send(message, api_key)
                sent += 1
            except Exception:
                logger.exception('Brevo email send failed')
                if not self.fail_silently:
                    raise
        return sent

    def _send(self, message, api_key):
        name, address = parseaddr(message.from_email or settings.DEFAULT_FROM_EMAIL)
        payload = {
            'sender': {'email': address, **({'name': name} if name else {})},
            'to': [{'email': r} for r in message.to],
            'subject': message.subject,
        }
        if message.cc:
            payload['cc'] = [{'email': r} for r in message.cc]
        if message.bcc:
            payload['bcc'] = [{'email': r} for r in message.bcc]

        html = None
        for content, mimetype in getattr(message, 'alternatives', []):
            if mimetype == 'text/html':
                html = content
        if message.content_subtype == 'html':
            html = message.body
        else:
            payload['textContent'] = message.body or ' '
        if html:
            payload['htmlContent'] = html

        request = urllib.request.Request(
            BREVO_URL,
            data=json.dumps(payload).encode('utf-8'),
            headers={
                'api-key': api_key,
                'accept': 'application/json',
                'content-type': 'application/json',
            },
            method='POST',
        )
        timeout = getattr(settings, 'EMAIL_TIMEOUT', 10)
        last_error = None
        for attempt in range(3):
            try:
                with urllib.request.urlopen(request, timeout=timeout) as resp:
                    resp.read()
                return
            except urllib.error.HTTPError as exc:
                detail = exc.read().decode('utf-8', 'replace')
                last_error = RuntimeError(f'Brevo API error {exc.code}: {detail}')
                if exc.code < 500 and exc.code != 429:
                    raise last_error from exc  # bad key/sender etc: retrying won't help
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                last_error = exc  # network hiccup / Render cold start: retry
            time.sleep(1.5 * (attempt + 1))
        raise last_error