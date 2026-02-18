"""
Email Verifier API — Layer 5 of the email discovery stack.

Wraps ZeroBounce for API-level email verification.
Falls back to MX-only (existing behavior) when API key not configured.

ZeroBounce:  set ZEROBOUNCE_API_KEY in .env — $0.01/email, bulk discounts
REOON:       set REOON_API_KEY in .env — alternative provider (already in .env)

Never export unverified emails to Instantly.ai.
"""

import os
import json
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

logger = logging.getLogger(__name__)


@dataclass
class VerificationResult:
    """Standardized result from email verification."""
    email: str
    status: str          # 'valid', 'invalid', 'catch-all', 'unknown', 'spamtrap', 'abuse', 'do_not_mail'
    sub_status: str = ''  # More detail: 'mailbox_not_found', 'no_dns_entries', etc.
    is_deliverable: bool = False
    provider: str = 'mx_only'
    confidence: int = 0   # 0-100
    error: Optional[str] = None
    raw: Optional[dict] = None

    def to_dict(self) -> dict:
        return {
            'email': self.email,
            'status': self.status,
            'sub_status': self.sub_status,
            'is_deliverable': self.is_deliverable,
            'provider': self.provider,
            'confidence': self.confidence,
            'error': self.error,
        }

    def is_usable(self) -> bool:
        """Return True if safe to use for outreach."""
        return self.status in ('valid', 'catch-all') and self.is_deliverable


class ZeroBounceProvider:
    """
    ZeroBounce email verifier.

    Activate: add ZEROBOUNCE_API_KEY to your .env
    Pricing:  $0.01/email, 100 free credits on signup
    Docs:     https://www.zerobounce.net/docs/

    Falls back to MX-only validation when key not configured.
    """

    API_URL = 'https://api.zerobounce.net/v2/validate'

    def __init__(self):
        self.api_key = os.getenv('ZEROBOUNCE_API_KEY')

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def verify(self, email: str, ip_address: str = '') -> VerificationResult:
        """
        Verify an email address via ZeroBounce API.
        Falls back to MX-only when not configured.
        """
        if not self.is_configured():
            logger.debug("ZeroBounce not configured — falling back to MX-only validation")
            return self._mx_fallback(email)

        params = urlencode({'api_key': self.api_key, 'email': email, 'ip_address': ip_address})
        url = f'{self.API_URL}?{params}'

        try:
            req = Request(url)
            with urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            status = data.get('status', 'unknown').lower()
            sub_status = data.get('sub_status', '').lower()
            is_deliverable = status == 'valid'
            confidence = {
                'valid': 90,
                'catch-all': 50,
                'unknown': 20,
                'spamtrap': 0,
                'abuse': 0,
                'do_not_mail': 0,
                'invalid': 0,
            }.get(status, 10)

            return VerificationResult(
                email=email,
                status=status,
                sub_status=sub_status,
                is_deliverable=is_deliverable,
                provider='zerobounce',
                confidence=confidence,
                raw=data,
            )

        except HTTPError as e:
            logger.warning(f"ZeroBounce HTTP {e.code} for {email}")
            return VerificationResult(
                email=email, status='unknown',
                provider='zerobounce', error=f'HTTP {e.code}',
            )
        except (URLError, json.JSONDecodeError, Exception) as e:
            logger.warning(f"ZeroBounce error for {email}: {e}")
            return self._mx_fallback(email)

    def _mx_fallback(self, email: str) -> VerificationResult:
        """Fall back to MX record check when ZeroBounce is unavailable."""
        from .email_verifier import EmailVerifier
        from .email_patterns import extract_domain

        domain = extract_domain(f'http://{email.split("@")[1]}') if '@' in email else None
        if not domain:
            return VerificationResult(
                email=email, status='unknown',
                provider='mx_only', error='Could not extract domain',
            )

        verifier = EmailVerifier()
        mx_hosts = verifier.get_mx_records(domain)
        has_mx = len(mx_hosts) > 0

        return VerificationResult(
            email=email,
            status='unknown' if not has_mx else 'catch-all',
            sub_status='no_mx' if not has_mx else 'mx_only_check',
            is_deliverable=has_mx,
            provider='mx_only',
            confidence=30 if has_mx else 0,
        )


class ReoonProvider:
    """
    Reoon email verifier — alternative to ZeroBounce.
    REOON_API_KEY is already in the project .env.

    Activate: REOON_API_KEY is already configured!
    Pricing:  Pay-per-use, affordable bulk pricing
    Docs:     https://reoon.com/email-verifier/
    """

    API_URL = 'https://emailverifier.reoon.com/api/v1/verify'

    def __init__(self):
        self.api_key = os.getenv('REOON_API_KEY')

    def is_configured(self) -> bool:
        return bool(self.api_key)

    def verify(self, email: str) -> VerificationResult:
        """Verify via Reoon API."""
        if not self.is_configured():
            return VerificationResult(
                email=email, status='unknown',
                provider='reoon', error='REOON_API_KEY not configured',
            )

        params = urlencode({
            'email': email,
            'key': self.api_key,
            'mode': 'quick',
        })
        url = f'{self.API_URL}?{params}'

        try:
            req = Request(url)
            with urlopen(req, timeout=15) as resp:
                data = json.loads(resp.read().decode('utf-8'))

            status = data.get('status', 'unknown').lower()
            # Reoon statuses: valid, invalid, catch_all, disposable, spamtrap, unknown
            is_deliverable = status in ('valid', 'catch_all')
            confidence = {
                'valid': 85,
                'catch_all': 45,
                'disposable': 0,
                'spamtrap': 0,
                'invalid': 0,
                'unknown': 20,
            }.get(status, 15)

            return VerificationResult(
                email=email,
                status=status,
                sub_status=data.get('reason', ''),
                is_deliverable=is_deliverable,
                provider='reoon',
                confidence=confidence,
                raw=data,
            )

        except HTTPError as e:
            logger.warning(f"Reoon HTTP {e.code} for {email}")
            return VerificationResult(
                email=email, status='unknown',
                provider='reoon', error=f'HTTP {e.code}',
            )
        except (URLError, json.JSONDecodeError, Exception) as e:
            logger.warning(f"Reoon error: {e}")
            return VerificationResult(
                email=email, status='unknown',
                provider='reoon', error=str(e)[:80],
            )


def verify_email(email: str) -> VerificationResult:
    """
    Verify an email using best available provider.
    Priority: Reoon (already configured) → ZeroBounce → MX-only fallback.
    """
    if not email or '@' not in email:
        return VerificationResult(
            email=email or '', status='invalid',
            provider='none', error='Invalid email format',
        )

    # Reoon is already configured in .env
    reoon = ReoonProvider()
    if reoon.is_configured():
        logger.debug(f"Verifying {email} via Reoon")
        return reoon.verify(email)

    # ZeroBounce (activate by adding ZEROBOUNCE_API_KEY)
    zb = ZeroBounceProvider()
    if zb.is_configured():
        logger.debug(f"Verifying {email} via ZeroBounce")
        return zb.verify(email)

    # MX-only fallback
    logger.debug(f"Verifying {email} via MX-only fallback")
    return zb._mx_fallback(email)
