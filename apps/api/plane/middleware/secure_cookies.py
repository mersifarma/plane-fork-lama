# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.


class SecureCookiesPerRequestMiddleware:
    """
    Mark every response cookie Secure exactly when the request came in over https.

    A global SESSION_COOKIE_SECURE breaks an instance that is reachable both over
    plain http (e.g. on the LAN) and over https (e.g. through a TLS-terminating
    tunnel): browsers drop Secure cookies on http, so one of the two can't log in.
    Behind a proxy this relies on SECURE_PROXY_SSL_HEADER, set in production settings.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        secure = request.is_secure()
        for morsel in response.cookies.values():
            morsel["secure"] = secure or ""
        return response
