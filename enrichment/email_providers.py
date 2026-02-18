"""
Email Provider Stubs — Layer 4 of the email discovery stack.

These integrations are built and ready. Activate by setting the relevant
API key in the project .env file.

Hunter.io:   set HUNTER_API_KEY  ($49/mo for 500 searches)
Snov.io:     set SNOV_CLIENT_ID + SNOV_CLIENT_SECRET  ($39/mo for 1,000 credits)
"""

import os
import json
import logging
from typing import Optional
from dataclasses import dataclass, field
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)


@dataclass
class EmailResult:
    """Standard result returned by all provider implementations."""
    email: Optional[str] = None
    confidence: int = 0          # 0-100
    source: str = 'none'
    verified: bool = False
    error: Optional[str] = None
    raw: Optional[dict] = field(default=None, repr=False)

    def to_dict(self) -> dict:
        return {
            'email': self.email,
            'confidence': self.confidence,
            'source': self.source,
            'verified': self.verified,
            'error': self.error,
        }


class HunterIOProvider:
    """
    Hunter.io email finder — finds and verifies emails via domain lookup.

    Activate: add HUNTER_API_KEY to your .env
    Pricing:  $49/mo starter (500 requests/mo), $0.10/request pay-as-you-go

    Docs: https://hunter.io/api-documentation/v2
    """

    BASE_URL = 'https://api.hunter.io/v2'

    def __init__(self):
        self.api_key = os.getenv('HUNTER_API_KEY')

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def find_email(
        self,
        domain: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> EmailResult:
        """
        Find email for a person at a domain.

        Returns EmailResult with email and confidence if found.
        Returns EmailResult with error='not configured' if API key missing.
        """
        if not self.is_configured():
            logger.debug("Hunter.io not configured — set HUNTER_API_KEY to enable")
            return EmailResult(
                source='hunter_io',
                error='Hunter.io not configured — set HUNTER_API_KEY to enable',
            )

        params: dict = {'domain': domain, 'api_key': self.api_key}
        if first_name:
            params['first_name'] = first_name
        if last_name:
            params['last_name'] = last_name

        endpoint = 'email-finder' if (first_name and last_name) else 'domain-search'
        url = f"{self.BASE_URL}/{endpoint}?{urlencode(params)}"

        try:
            req = Request(url)
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            if endpoint == 'email-finder':
                d = data.get('data', {})
                email = d.get('email')
                score = d.get('score', 0)
                return EmailResult(
                    email=email,
                    confidence=score,
                    source='hunter_io',
                    verified=d.get('verification', {}).get('status') == 'valid',
                    raw=data,
                )
            else:
                # domain-search: return first email
                emails = data.get('data', {}).get('emails', [])
                if emails:
                    e = emails[0]
                    return EmailResult(
                        email=e.get('value'),
                        confidence=e.get('confidence', 0),
                        source='hunter_io',
                        verified=e.get('verification', {}).get('status') == 'valid',
                        raw=data,
                    )
                return EmailResult(source='hunter_io', error='No emails found for domain')

        except HTTPError as e:
            logger.warning(f"Hunter.io HTTP {e.code}: {e.reason}")
            return EmailResult(source='hunter_io', error=f'HTTP {e.code}')
        except (URLError, json.JSONDecodeError, Exception) as e:
            logger.warning(f"Hunter.io error: {e}")
            return EmailResult(source='hunter_io', error=str(e)[:80])

    def verify_email(self, email: str) -> dict:
        """
        Verify a single email via Hunter.io verification endpoint.
        Returns dict with 'status', 'score', 'regexp', 'gibberish', 'disposable', 'smtp_server'
        """
        if not self.is_configured():
            return {'status': 'unknown', 'error': 'Hunter.io not configured'}

        url = f"{self.BASE_URL}/email-verifier?email={email}&api_key={self.api_key}"
        try:
            req = Request(url)
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            return data.get('data', {})
        except Exception as e:
            return {'status': 'unknown', 'error': str(e)[:80]}


class SnovIOProvider:
    """
    Snov.io email finder — alternative to Hunter.io with prospecting features.

    Activate: add SNOV_CLIENT_ID and SNOV_CLIENT_SECRET to your .env
    Pricing:  $39/mo starter (1,000 credits/mo)

    Docs: https://snov.io/api
    """

    AUTH_URL = 'https://api.snov.io/v1/oauth/access_token'
    BASE_URL = 'https://api.snov.io/v1'

    def __init__(self):
        self.client_id = os.getenv('SNOV_CLIENT_ID')
        self.client_secret = os.getenv('SNOV_CLIENT_SECRET')
        self._token: Optional[str] = None

    def is_configured(self) -> bool:
        return bool(self.client_id and self.client_secret)

    def _get_token(self) -> Optional[str]:
        """Get OAuth access token."""
        if self._token:
            return self._token

        if not self.is_configured():
            return None

        payload = urlencode({
            'grant_type': 'client_credentials',
            'client_id': self.client_id,
            'client_secret': self.client_secret,
        }).encode()

        try:
            req = Request(self.AUTH_URL, data=payload)
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))
            self._token = data.get('access_token')
            return self._token
        except Exception as e:
            logger.warning(f"Snov.io auth failed: {e}")
            return None

    def find_email(
        self,
        domain: str,
        first_name: Optional[str] = None,
        last_name: Optional[str] = None,
    ) -> EmailResult:
        """
        Find email for a person at a domain.
        """
        if not self.is_configured():
            logger.debug("Snov.io not configured — set SNOV_CLIENT_ID and SNOV_CLIENT_SECRET to enable")
            return EmailResult(
                source='snov_io',
                error='Snov.io not configured — set SNOV_CLIENT_ID and SNOV_CLIENT_SECRET to enable',
            )

        token = self._get_token()
        if not token:
            return EmailResult(source='snov_io', error='Snov.io auth failed')

        params = {'access_token': token, 'domain': domain}
        if first_name:
            params['firstName'] = first_name
        if last_name:
            params['lastName'] = last_name

        endpoint = 'get-emails-from-names' if (first_name and last_name) else 'get-domain-emails'
        url = f"{self.BASE_URL}/{endpoint}?{urlencode(params)}"

        try:
            req = Request(url)
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            emails = data.get('emails', [])
            if emails:
                e = emails[0]
                email_addr = e.get('email') or (e.get('emailAddress'))
                return EmailResult(
                    email=email_addr,
                    confidence=e.get('confidence', 50),
                    source='snov_io',
                    raw=data,
                )
            return EmailResult(source='snov_io', error='No emails found')

        except HTTPError as e:
            logger.warning(f"Snov.io HTTP {e.code}")
            return EmailResult(source='snov_io', error=f'HTTP {e.code}')
        except (URLError, json.JSONDecodeError, Exception) as e:
            logger.warning(f"Snov.io error: {e}")
            return EmailResult(source='snov_io', error=str(e)[:80])


def find_email_paid(
    domain: str,
    first_name: Optional[str] = None,
    last_name: Optional[str] = None,
) -> EmailResult:
    """
    Try paid providers in priority order.
    Tries Hunter.io first, then Snov.io.
    Returns first successful result.
    """
    providers = [
        ('Hunter.io', HunterIOProvider()),
        ('Snov.io', SnovIOProvider()),
    ]

    for name, provider in providers:
        if not provider.is_configured():
            continue
        logger.info(f"Layer 4: Trying {name} for {domain}")
        result = provider.find_email(domain, first_name, last_name)
        if result.email:
            logger.info(f"Layer 4 ({name}): Found {result.email}")
            return result
        logger.debug(f"Layer 4 ({name}): {result.error}")

    return EmailResult(
        source='paid_providers',
        error='No paid providers configured or no results found',
    )
