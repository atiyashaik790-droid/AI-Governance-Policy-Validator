"""Browser credentialed requests must use the configured exact origin."""

from app.config import settings


def test_local_origin_preflight_and_actual_responses(client):
    origin = settings.cors_origin
    preflight = client.options(
        "/api/auth/session",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type",
        },
    )
    assert preflight.status_code == 200
    assert preflight.headers["access-control-allow-origin"] == origin
    assert preflight.headers["access-control-allow-credentials"] == "true"

    for method, path in (("GET", "/api/sso/status"), ("GET", "/api/auth/me"), ("POST", "/api/auth/session")):
        response = client.request(method, path, headers={"Origin": origin})
        assert response.headers["access-control-allow-origin"] == origin
        assert response.headers["access-control-allow-credentials"] == "true"

    foreign = client.options(
        "/api/auth/session",
        headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"},
    )
    assert foreign.status_code == 400
    assert "access-control-allow-origin" not in foreign.headers
