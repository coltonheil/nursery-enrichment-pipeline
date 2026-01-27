"""
Email Verification Module

Verifies email addresses using:
1. Basic syntax validation
2. MX record checking
3. SMTP verification (optional, can trigger rate limits)
4. API verification via NeverBounce/ZeroBounce (optional, costs money)
"""

import re
import socket
import smtplib
import dns.resolver
from typing import Dict, List, Optional, Tuple
from enum import Enum
import os
import json
import urllib.request
import urllib.error
from datetime import datetime


class VerificationStatus(Enum):
    VALID = 'valid'
    INVALID = 'invalid'
    RISKY = 'risky'
    CATCH_ALL = 'catch_all'
    UNKNOWN = 'unknown'
    UNVERIFIED = 'unverified'


# Simple email regex
EMAIL_REGEX = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

# User-Agent for API requests
USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36"


class EmailVerifier:
    """
    Multi-method email verification.
    
    Verification layers:
    1. Syntax check (free, instant)
    2. MX record check (free, fast)
    3. SMTP verification (free, but can be blocked)
    4. API verification (paid, most accurate)
    """
    
    def __init__(
        self,
        neverbounce_api_key: Optional[str] = None,
        zerobounce_api_key: Optional[str] = None,
    ):
        self.neverbounce_api_key = neverbounce_api_key or os.environ.get('NEVERBOUNCE_API_KEY')
        self.zerobounce_api_key = zerobounce_api_key or os.environ.get('ZEROBOUNCE_API_KEY')
        self._mx_cache: Dict[str, List[str]] = {}
        self._catchall_cache: Dict[str, bool] = {}
    
    def verify_syntax(self, email: str) -> bool:
        """Check if email has valid syntax."""
        if not email:
            return False
        return bool(EMAIL_REGEX.match(email.strip().lower()))
    
    def get_mx_records(self, domain: str) -> List[str]:
        """Get MX records for a domain (cached)."""
        if domain in self._mx_cache:
            return self._mx_cache[domain]
        
        try:
            mx_records = dns.resolver.resolve(domain, 'MX')
            records = [str(r.exchange).rstrip('.') for r in mx_records]
            self._mx_cache[domain] = records
            return records
        except Exception:
            self._mx_cache[domain] = []
            return []
    
    def verify_mx(self, email: str) -> bool:
        """Check if domain has valid MX records."""
        if not self.verify_syntax(email):
            return False
        
        domain = email.split('@')[1].lower()
        mx_records = self.get_mx_records(domain)
        return len(mx_records) > 0
    
    def smtp_verify(self, email: str, timeout: int = 10) -> Dict:
        """
        Verify email using SMTP handshake.
        
        WARNING: This can be unreliable and may get your IP blocked.
        Use sparingly and prefer API verification for production.
        
        Returns:
            Dict with 'valid', 'catch_all', 'error'
        """
        result = {
            'valid': None,
            'catch_all': None,
            'error': None
        }
        
        if not self.verify_mx(email):
            result['valid'] = False
            result['error'] = 'No MX records'
            return result
        
        domain = email.split('@')[1].lower()
        mx_records = self.get_mx_records(domain)
        
        if not mx_records:
            result['valid'] = False
            result['error'] = 'No MX records'
            return result
        
        # Try first MX server
        mx_host = mx_records[0]
        
        try:
            # Connect to SMTP server
            smtp = smtplib.SMTP(timeout=timeout)
            smtp.connect(mx_host, 25)
            smtp.helo('verify.local')
            smtp.mail('verify@verify.local')
            
            # Check if email is accepted
            code, message = smtp.rcpt(email)
            smtp.quit()
            
            if code == 250:
                result['valid'] = True
            elif code == 550:
                result['valid'] = False
            else:
                result['valid'] = None  # Unknown
                result['error'] = f'SMTP code {code}'
            
        except smtplib.SMTPServerDisconnected:
            result['error'] = 'Server disconnected'
        except smtplib.SMTPConnectError:
            result['error'] = 'Connection refused'
        except socket.timeout:
            result['error'] = 'Timeout'
        except Exception as e:
            result['error'] = str(e)[:100]
        
        return result
    
    def check_catchall(self, domain: str) -> Optional[bool]:
        """
        Check if domain is catch-all (accepts all emails).
        
        Uses cached results to avoid repeated checks.
        """
        if domain in self._catchall_cache:
            return self._catchall_cache[domain]
        
        # Generate a random email that definitely doesn't exist
        import random
        import string
        random_local = ''.join(random.choices(string.ascii_lowercase, k=20))
        test_email = f"{random_local}@{domain}"
        
        result = self.smtp_verify(test_email, timeout=5)
        
        # If random email is accepted, it's catch-all
        is_catchall = result.get('valid') == True
        self._catchall_cache[domain] = is_catchall
        
        return is_catchall
    
    def api_verify_neverbounce(self, email: str) -> Dict:
        """
        Verify email using NeverBounce API.
        
        Cost: ~$0.003-0.008 per verification
        
        Returns:
            Dict with 'status', 'result', 'confidence'
        """
        if not self.neverbounce_api_key:
            return {'error': 'NeverBounce API key not configured'}
        
        url = f"https://api.neverbounce.com/v4/single/check"
        params = {
            'key': self.neverbounce_api_key,
            'email': email
        }
        
        try:
            query = '&'.join(f"{k}={v}" for k, v in params.items())
            req = urllib.request.Request(
                f"{url}?{query}",
                headers={'User-Agent': USER_AGENT}
            )
            
            resp = urllib.request.urlopen(req, timeout=30)
            data = json.load(resp)
            
            # NeverBounce result codes:
            # valid, invalid, disposable, catchall, unknown
            result_code = data.get('result')
            
            status_map = {
                'valid': VerificationStatus.VALID,
                'invalid': VerificationStatus.INVALID,
                'disposable': VerificationStatus.INVALID,
                'catchall': VerificationStatus.CATCH_ALL,
                'unknown': VerificationStatus.UNKNOWN,
            }
            
            return {
                'status': status_map.get(result_code, VerificationStatus.UNKNOWN).value,
                'result': result_code,
                'is_catchall': result_code == 'catchall',
                'raw': data
            }
            
        except urllib.error.HTTPError as e:
            return {'error': f'HTTP {e.code}'}
        except Exception as e:
            return {'error': str(e)[:100]}
    
    def api_verify_zerobounce(self, email: str) -> Dict:
        """
        Verify email using ZeroBounce API.
        
        Cost: ~$0.008-0.01 per verification
        
        Returns:
            Dict with 'status', 'sub_status', 'confidence'
        """
        if not self.zerobounce_api_key:
            return {'error': 'ZeroBounce API key not configured'}
        
        url = "https://api.zerobounce.net/v2/validate"
        params = {
            'api_key': self.zerobounce_api_key,
            'email': email
        }
        
        try:
            query = '&'.join(f"{k}={v}" for k, v in params.items())
            req = urllib.request.Request(
                f"{url}?{query}",
                headers={'User-Agent': USER_AGENT}
            )
            
            resp = urllib.request.urlopen(req, timeout=30)
            data = json.load(resp)
            
            # ZeroBounce status codes:
            # valid, invalid, catch-all, unknown, spamtrap, abuse, do_not_mail
            zb_status = data.get('status', '').lower()
            
            status_map = {
                'valid': VerificationStatus.VALID,
                'invalid': VerificationStatus.INVALID,
                'catch-all': VerificationStatus.CATCH_ALL,
                'unknown': VerificationStatus.UNKNOWN,
                'spamtrap': VerificationStatus.INVALID,
                'abuse': VerificationStatus.RISKY,
                'do_not_mail': VerificationStatus.INVALID,
            }
            
            return {
                'status': status_map.get(zb_status, VerificationStatus.UNKNOWN).value,
                'sub_status': data.get('sub_status'),
                'is_catchall': zb_status == 'catch-all',
                'confidence': data.get('mx_record') == 'true',
                'raw': data
            }
            
        except urllib.error.HTTPError as e:
            return {'error': f'HTTP {e.code}'}
        except Exception as e:
            return {'error': str(e)[:100]}
    
    def verify(
        self,
        email: str,
        use_api: bool = False,
        api_provider: str = 'neverbounce'
    ) -> Dict:
        """
        Full verification pipeline.
        
        Args:
            email: Email address to verify
            use_api: Whether to use paid API verification
            api_provider: 'neverbounce' or 'zerobounce'
        
        Returns:
            Dict with:
                - status: VerificationStatus value
                - confidence: 0-100 score
                - is_catchall: Boolean
                - method: How it was verified
                - error: Error message if any
        """
        email = email.strip().lower() if email else ''
        
        result = {
            'email': email,
            'status': VerificationStatus.UNKNOWN.value,
            'confidence': 0,
            'is_catchall': None,
            'method': None,
            'error': None
        }
        
        # Step 1: Syntax check
        if not self.verify_syntax(email):
            result['status'] = VerificationStatus.INVALID.value
            result['confidence'] = 100
            result['method'] = 'syntax'
            result['error'] = 'Invalid email syntax'
            return result
        
        # Step 2: MX record check
        if not self.verify_mx(email):
            result['status'] = VerificationStatus.INVALID.value
            result['confidence'] = 95
            result['method'] = 'mx'
            result['error'] = 'Domain has no MX records'
            return result
        
        # Basic checks passed
        result['confidence'] = 50
        result['method'] = 'mx'
        
        # Step 3: API verification (if enabled)
        if use_api:
            if api_provider == 'neverbounce' and self.neverbounce_api_key:
                api_result = self.api_verify_neverbounce(email)
                if 'error' not in api_result:
                    result['status'] = api_result['status']
                    result['is_catchall'] = api_result.get('is_catchall')
                    result['confidence'] = 95 if api_result['status'] in ['valid', 'invalid'] else 70
                    result['method'] = 'neverbounce'
                    return result
                    
            elif api_provider == 'zerobounce' and self.zerobounce_api_key:
                api_result = self.api_verify_zerobounce(email)
                if 'error' not in api_result:
                    result['status'] = api_result['status']
                    result['is_catchall'] = api_result.get('is_catchall')
                    result['confidence'] = 95 if api_result['status'] in ['valid', 'invalid'] else 70
                    result['method'] = 'zerobounce'
                    return result
        
        # No API or API failed - return MX-only result
        result['status'] = VerificationStatus.UNVERIFIED.value
        result['confidence'] = 50
        
        return result
    
    def verify_batch(
        self,
        emails: List[str],
        use_api: bool = False
    ) -> List[Dict]:
        """Verify multiple emails."""
        return [self.verify(email, use_api=use_api) for email in emails]


# ============================================================
# Convenience functions
# ============================================================

def quick_verify(email: str) -> Dict:
    """Quick verification using only free methods (syntax + MX)."""
    verifier = EmailVerifier()
    return verifier.verify(email, use_api=False)


def has_valid_mx(email: str) -> bool:
    """Check if email domain has valid MX records."""
    verifier = EmailVerifier()
    return verifier.verify_mx(email)


# ============================================================
# Test functions
# ============================================================

def test_verifier():
    """Test email verification."""
    print("=== Testing Email Verifier ===\n")
    
    verifier = EmailVerifier()
    
    test_emails = [
        "test@gmail.com",           # Valid domain
        "invalid",                  # Invalid syntax
        "test@nonexistentdomain12345.com",  # Invalid domain
        "john.smith@greenvalleynursery.com",  # Likely doesn't exist
    ]
    
    for email in test_emails:
        result = verifier.verify(email, use_api=False)
        print(f"Email: {email}")
        print(f"  Status: {result['status']}")
        print(f"  Confidence: {result['confidence']}%")
        print(f"  Method: {result['method']}")
        if result.get('error'):
            print(f"  Error: {result['error']}")
        print()


if __name__ == '__main__':
    test_verifier()
