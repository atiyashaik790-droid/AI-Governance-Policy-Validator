"""Local test instrumentation: verify issuance, persistence and cookies without age assumptions."""

from contextlib import contextmanager
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime
from http.cookies import SimpleCookie
from unittest.mock import patch


def utc(value):
    stamp = datetime.fromisoformat(value) if isinstance(value, str) else value
    assert stamp.tzinfo is not None and stamp.utcoffset() == timedelta(0), (
        "Expected absolute UTC timestamp"
    )
    return stamp


@contextmanager
def observe_issuance(sso, expected_minutes):
    """Observe the unchanged expiry function; never log tokens, cookies or identities."""
    original = sso.expiry
    observations = []

    def observed(minutes):
        before = utc(sso.now())
        result = original(minutes)
        after = utc(sso.now())
        observations.append(
            {
                "minutes": minutes,
                "before": before,
                "after": after,
                "expires": utc(result),
            }
        )
        return result

    with patch.object(sso, "expiry", observed):
        yield observations
    assert len(observations) == 1, "Expected exactly one session issuance"
    issued = observations[0]
    assert issued["minutes"] == expected_minutes, "Wrong session lifetime configuration"
    duration = timedelta(minutes=expected_minutes)
    assert (
        issued["before"] + duration <= issued["expires"] <= issued["after"] + duration
    ), "Incorrect issued duration"


def verify_session(sso, issued, callback, database_expiry, me):
    """Compare exact original expiry; remaining lifetime can decrease by any valid request age."""
    assert len(issued) == 1
    issued = issued[0]
    expires = issued["expires"]
    ttl = issued["minutes"] * 60
    cookies = SimpleCookie()
    for header in callback.headers.get_list("set-cookie"):
        cookies.load(header)
    cookie = cookies[sso.COOKIE]
    assert cookie["max-age"] == str(ttl), (
        "Cookie Max-Age disagrees with configured duration"
    )
    assert (
        cookie["secure"]
        and cookie["httponly"]
        and cookie["samesite"].lower() == "lax"
        and cookie["path"] == "/"
    )
    # HTTP cookie dates have second precision, while DB timestamps retain microseconds.
    assert parsedate_to_datetime(cookie["expires"]) == expires.replace(microsecond=0), (
        "Cookie/DB expiry mismatch"
    )
    assert utc(database_expiry) == expires, "Persisted expiry differs from issuance"
    assert utc(me["expires_at"]) == expires, "Session was renewed or shortened"
    server_now = utc(me["server_now"])
    remaining = (expires - server_now).total_seconds()
    assert issued["before"] <= server_now < expires, (
        "Invalid server time or expired authenticated session"
    )
    assert 0 < remaining <= ttl, "Invalid remaining lifetime"
    return {
        "configured_minutes": issued["minutes"],
        "issued_before_utc": issued["before"].isoformat(),
        "issued_after_utc": issued["after"].isoformat(),
        "database_expires_utc": expires.isoformat(),
        "cookie_max_age_seconds": ttl,
        "cookie_expires_utc": parsedate_to_datetime(cookie["expires"]).isoformat(),
        "server_now_utc": server_now.isoformat(),
        "remaining_seconds": remaining,
        "issued_duration_lower_seconds": (expires - issued["after"]).total_seconds(),
        "issued_duration_upper_seconds": (expires - issued["before"]).total_seconds(),
    }
