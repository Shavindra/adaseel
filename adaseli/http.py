# -*- coding: utf-8 -*-
"""One shared, fail-soft HTTP helper used by every tool.

Tools import the *module* (``from .. import http``) and call ``http.http_get``
so the function can be monkeypatched in one place during tests.
"""

import logging

import requests

from .config import HTTP_HEADERS, HTTP_TIMEOUT

log = logging.getLogger(__name__)


def http_get(url, params=None, accept_json=True):
    """GET a URL and return parsed JSON (or raw text). Never raises.

    Returns the decoded payload on success, or ``{"error": "..."}`` on any
    failure (timeout, connection error, HTTP error, bad JSON). Tools build on
    this so the agent can simply note "source X came up empty/failed" and move on.
    Full detail (URL, status, response body) is logged for inspection with -v.
    """
    log.debug("GET %s params=%s", url, params)
    try:
        resp = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        if accept_json:
            return resp.json()
        return resp.text
    except requests.exceptions.Timeout:
        log.warning("GET %s timed out after %ss", url, HTTP_TIMEOUT)
        return {"error": "timeout after %ss" % HTTP_TIMEOUT}
    except requests.exceptions.HTTPError as e:
        code = getattr(e.response, "status_code", "?")
        body = ""
        try:
            body = e.response.text[:500]
        except Exception:
            pass
        log.warning("GET %s -> HTTP %s; body: %s", url, code, body)
        return {"error": "http %s" % code}
    except ValueError:
        log.warning("GET %s -> could not decode JSON", url)
        return {"error": "could not decode JSON response"}
    except requests.exceptions.RequestException as e:
        log.warning("GET %s -> request failed: %s", url, e)
        return {"error": "request failed: %s" % e}


def is_err(obj):
    """True if a payload is one of our soft-error sentinels."""
    return isinstance(obj, dict) and "error" in obj
