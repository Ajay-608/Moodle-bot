"""
Simple in-memory rate limiter for the chat endpoint.

Protects your Groq/OpenRouter API quota from being exhausted by a single
user or bot spamming requests. Limits are per IP address, reset hourly.

NOTE: This uses in-memory storage, so limits reset if the app restarts
(which happens often on Render's free tier). That's fine for a demo —
if you need robust limiting across restarts, use Django's cache framework
with Redis instead.

Usage: add 'core.rate_limit_middleware.ChatRateLimitMiddleware' to your
MIDDLEWARE list in settings.py, placed after AuthenticationMiddleware.
"""

import time
from django.http import JsonResponse

# In-memory store: { ip_address: [timestamp1, timestamp2, ...] }
_request_log = {}

# Only rate-limit these paths (adjust to match your actual chat send URL)
RATE_LIMITED_PATHS = ['/chat/send/']

MAX_REQUESTS_PER_HOUR = 20


class ChatRateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in RATE_LIMITED_PATHS and request.method == 'POST':
            ip = self._get_client_ip(request)
            now = time.time()
            one_hour_ago = now - 3600

            # Clean old entries and get this IP's recent requests
            timestamps = _request_log.get(ip, [])
            timestamps = [t for t in timestamps if t > one_hour_ago]

            if len(timestamps) >= MAX_REQUESTS_PER_HOUR:
                return JsonResponse(
                    {
                        "error": "Rate limit reached. Please try again in a bit — "
                                 "this demo shares a limited free AI quota across all visitors."
                    },
                    status=429
                )

            timestamps.append(now)
            _request_log[ip] = timestamps

        return self.get_response(request)

    def _get_client_ip(self, request):
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            return x_forwarded_for.split(',')[0].strip()
        return request.META.get('REMOTE_ADDR', 'unknown')