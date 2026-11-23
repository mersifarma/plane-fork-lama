# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

"""
One instance served on two addresses at once: http on the LAN and https through a tunnel.

- auth redirects go back to the address the user came in on, but only for configured origins
- cookies are Secure on https requests only, so the http address can still log in
"""

import pytest
from django.http import HttpResponse
from django.test import RequestFactory

from plane.authentication.utils.host import base_host, request_origin
from plane.middleware.secure_cookies import SecureCookiesPerRequestMiddleware

LAN = "http://192.168.1.53:2028"
PUBLIC = "https://plane.example.com"
HYBRID = dict(
    CORS_ALLOWED_ORIGINS=[PUBLIC, LAN],
    WEB_URL=PUBLIC,
    APP_BASE_URL=None,
    ADMIN_BASE_URL=None,
    SPACE_BASE_URL=None,
)

rf = RequestFactory()
lan_request = lambda: rf.get("/", HTTP_HOST="192.168.1.53:2028")  # noqa: E731
public_request = lambda: rf.get("/", secure=True, HTTP_HOST="plane.example.com")  # noqa: E731


@pytest.fixture
def hybrid(settings):
    for name, value in HYBRID.items():
        setattr(settings, name, value)


@pytest.mark.unit
@pytest.mark.usefixtures("hybrid")
class TestRequestOrigin:
    def test_configured_origins_are_used(self):
        assert request_origin(lan_request()) == LAN
        assert request_origin(public_request()) == PUBLIC

    def test_unknown_host_falls_back_to_web_url(self):
        forged = rf.get("/", HTTP_HOST="evil.example.com")
        assert request_origin(forged) is None
        assert base_host(request=forged, is_app=True) == PUBLIC

    def test_scheme_must_match(self):
        # the public host over plain http is not a configured origin
        assert request_origin(rf.get("/", HTTP_HOST="plane.example.com")) is None

    def test_no_request_falls_back_to_web_url(self):
        assert request_origin(None) is None
        assert base_host(request=None, is_admin=True) == PUBLIC + "/god-mode/"

    def test_disallowed_host_is_ignored(self, settings):
        settings.ALLOWED_HOSTS = ["plane.example.com"]
        assert request_origin(lan_request()) is None

    def test_redirects_follow_the_address_used(self):
        assert base_host(request=lan_request(), is_app=True) == LAN
        assert base_host(request=public_request(), is_app=True) == PUBLIC
        assert base_host(request=lan_request(), is_admin=True) == LAN + "/god-mode/"
        assert base_host(request=public_request(), is_space=True) == PUBLIC + "/spaces/"


@pytest.mark.unit
class TestSecureCookiesPerRequest:
    @staticmethod
    def respond(request):
        def view(_request):
            response = HttpResponse()
            response.set_cookie("session-id", "s", secure=True)
            response.set_cookie("csrftoken", "c")
            return response

        return SecureCookiesPerRequestMiddleware(view)(request)

    def test_http_request_gets_plain_cookies(self):
        cookies = self.respond(lan_request()).cookies
        assert not cookies["session-id"]["secure"]
        assert not cookies["csrftoken"]["secure"]

    def test_https_request_gets_secure_cookies(self):
        cookies = self.respond(public_request()).cookies
        assert cookies["session-id"]["secure"] is True
        assert cookies["csrftoken"]["secure"] is True
