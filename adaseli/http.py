# -*- coding: utf-8 -*-
"""One shared, fail-soft HTTP helper used by every tool.

Tools import the *module* (``from .. import http``) and call ``http.http_get``
so the function can be monkeypatched in one place during tests.
"""

import requests

from .config import HTTP_HEADERS, HTTP_TIMEOUT


def http_get(url, params=None, accept_json=True):
    """GET a URL and return parsed JSON (or raw text). Never raises.

    Returns the decoded payload on success, or ``{"error": "..."}`` on any
    failure (timeout, connection error, HTTP error, bad JSON). Tools build on
    this so the agent can simply note "source X came up empty/failed" and move on.
    """
    try:
        resp = requests.get(url, params=params, headers=HTTP_HEADERS, timeout=HTTP_TIMEOUT)
        resp.raise_for_status()
        if accept_json:
            return resp.json()
        return resp.text
    except requests.exceptions.Timeout:
        return {"error": "timeout after %ss" % HTTP_TIMEOUT}
    except requests.exceptions.HTTPError as e:
        return {"error": "http %s" % getattr(e.response, "status_code", "?")}
    except ValueError:
        return {"error": "could not decode JSON response"}
    except requests.exceptions.RequestException as e:
        return {"error": "request failed: %s" % e}


def is_err(obj):
    """True if a payload is one of our soft-error sentinels."""
    return isinstance(obj, dict) and "error" in obj
