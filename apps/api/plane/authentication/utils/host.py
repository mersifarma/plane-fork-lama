# Copyright (c) 2023-present Plane Software, Inc. and contributors
# SPDX-License-Identifier: AGPL-3.0-only
# See the LICENSE file for details.

# Django imports
from django.conf import settings
from django.core.exceptions import DisallowedHost
from django.http import HttpRequest

# Third party imports
from rest_framework.request import Request

# Module imports
from plane.utils.ip_address import get_client_ip


def base_host(
    request: Request | HttpRequest,
    is_admin: bool = False,
    is_space: bool = False,
    is_app: bool = False,
) -> str:
    """Utility function to return host / origin from the request"""
    # Calculate the base origin from request
    base_origin = request_origin(request) or settings.WEB_URL or settings.APP_BASE_URL

    # Admin redirection
    if is_admin:
        admin_base_path = getattr(settings, "ADMIN_BASE_PATH", None)
        if not isinstance(admin_base_path, str):
            admin_base_path = "/god-mode/"
        if not admin_base_path.startswith("/"):
            admin_base_path = "/" + admin_base_path
        if not admin_base_path.endswith("/"):
            admin_base_path += "/"

        if settings.ADMIN_BASE_URL:
            return settings.ADMIN_BASE_URL + admin_base_path
        else:
            return base_origin + admin_base_path

    # Space redirection
    if is_space:
        space_base_path = getattr(settings, "SPACE_BASE_PATH", None)
        if not isinstance(space_base_path, str):
            space_base_path = "/spaces/"
        if not space_base_path.startswith("/"):
            space_base_path = "/" + space_base_path
        if not space_base_path.endswith("/"):
            space_base_path += "/"

        if settings.SPACE_BASE_URL:
            return settings.SPACE_BASE_URL + space_base_path
        else:
            return base_origin + space_base_path

    # App Redirection
    if is_app:
        if settings.APP_BASE_URL:
            return settings.APP_BASE_URL
        else:
            return base_origin

    return base_origin


def request_origin(request: Request | HttpRequest | None) -> str | None:
    """
    The origin the request came in on, when it is one of CORS_ALLOWED_ORIGINS.

    Lets one instance serve several addresses at once (e.g. http on the LAN and
    https through a tunnel) and send users back to the address they used. Only
    configured origins qualify, so a forged Host header can't steer redirects.
    """
    if request is None:  # some callers (e.g. the admin auth throttle) have no request
        return None
    try:
        origin = f"{request.scheme}://{request.get_host()}".lower()
    except DisallowedHost:
        return None
    allowed = {o.strip().rstrip("/").lower() for o in settings.CORS_ALLOWED_ORIGINS}
    return origin if origin in allowed else None


def user_ip(request: Request | HttpRequest) -> str:
    return get_client_ip(request=request)
