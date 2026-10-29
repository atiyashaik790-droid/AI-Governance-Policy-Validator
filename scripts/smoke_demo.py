"""Exercise the running local API with clearly labeled synthetic fixture scenarios."""

import json
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]


# Fail visibly on unexpected statuses without printing tokens or content.
def call(client, method, path, body=None, expected=200):
    response = client.request(method, path, json=body)
    if response.status_code != expected:
        raise RuntimeError(
            f"{method} {path}: expected {expected}, received {response.status_code}"
        )
    return response.json()


# Generate actual persisted demo results rather than inserting fake dashboard metrics.
def run_demo():
    token = json.loads((ROOT / ".demo-tokens.json").read_text())["Admin"]
    outcomes = []
    with httpx.Client(
        base_url="http://localhost:8000",
        headers={"Authorization": f"Bearer {token}"},
        timeout=60,
    ) as client:
        diagnostics = call(client, "GET", "/api/settings")
        if diagnostics["provider_mode"] != "fixture":
            raise RuntimeError(
                "This reproducible demo is fixture-only; live provider calls are not implied"
            )
        document = {
            "name": "Demo enterprise protection",
            "description": "Synthetic demonstration policy",
            "rules": {
                "secret_detection": {"enabled": True, "action": "BLOCK"},
                "pii_detection": {"enabled": True, "action": "REDACT"},
                "moderation": {"enabled": True, "action": "BLOCK"},
                "blocked_keywords": {
                    "enabled": True,
                    "action": "BLOCK",
                    "values": ["internal-only"],
                },
            },
        }
        policy = call(client, "POST", "/api/policies", document, 201)
        policy_id = policy["id"]
        call(client, "PUT", f"/api/policies/{policy_id}", document)
        simulated = call(
            client,
            "POST",
            f"/api/policies/{policy_id}/simulate",
            {"text": "test.person@example.com"},
        )
        assert simulated["decision"] == "REDACT"
        for operation in ("submit", "approve", "publish", "activate"):
            call(client, "POST", f"/api/policies/{policy_id}/{operation}")
        assert len(call(client, "GET", f"/api/policies/{policy_id}/versions")) == 1
        outcomes.append(
            {"scenario": "Policy lifecycle and simulation", "status": "PASSED"}
        )
        for name, prompt, expected in [
            (
                "Safe prompt",
                "Explain the benefits of data governance in simple terms.",
                "ALLOW",
            ),
            (
                "Synthetic secret",
                "api_key=sk-test-ABCDEFGHIJKLMNOPQRSTUVWXYZ12345",
                "BLOCK",
            ),
            (
                "Synthetic PII",
                "Contact test.person@example.com about governance.",
                "REDACT",
            ),
            ("Fixture moderation", "[MODERATION_FLAG]", "BLOCK"),
            ("Fixture unavailable moderation", "[MODERATION_UNAVAILABLE]", "BLOCK"),
            ("Fixture output secret", "[OUTPUT_SECRET]", "BLOCK"),
        ]:
            result = call(client, "POST", "/api/governance/generate", {"text": prompt})
            assert result["decision"] == expected, (name, result["decision"])
            if name == "Synthetic PII":
                assert (
                    result["input"]["decision"] == "REDACT"
                    and result["input"]["revalidated"]
                )
            if expected == "BLOCK":
                assert result["safe_response"] is None
            outcomes.append(
                {
                    "scenario": name,
                    "status": "PASSED",
                    "request_id": result["request_id"],
                }
            )
        call(client, "POST", f"/api/policies/{policy_id}/disable")
        call(client, "POST", "/api/governance/generate", {"text": "safe"}, 409)
        call(client, "POST", f"/api/policies/{policy_id}/enable")
        outcomes.append(
            {
                "scenario": "Disable fails closed and enable restores assignment",
                "status": "PASSED",
            }
        )
        document["rules"]["blocked_keywords"]["action"] = "HUMAN_REVIEW"
        call(client, "PUT", f"/api/policies/{policy_id}", document)
        for operation in ("submit", "approve", "publish", "activate"):
            call(client, "POST", f"/api/policies/{policy_id}/{operation}")
        held = call(
            client, "POST", "/api/governance/generate", {"text": "internal-only"}
        )
        assert held["decision"] == "HUMAN_REVIEW" and not held["model_invoked"]
        resolution = call(client, "POST", f"/api/reviews/{held['review_id']}/approve")
        assert resolution["status"] == "APPROVED_RESUBMIT_REQUIRED"
        outcomes.append(
            {"scenario": "Human review cannot release held content", "status": "PASSED"}
        )
        summary = call(client, "GET", "/api/analytics/overview")
        assert summary["total_validations"] >= 7
        assert call(client, "GET", "/api/audit/events")
        outcomes.append(
            {"scenario": "Audit and analytics persistence", "status": "PASSED"}
        )
    report = {
        "mode": "DETERMINISTIC LOCAL FIXTURE — NOT LIVE AZURE",
        "pii_mode": diagnostics["pii_mode"],
        "scenarios": outcomes,
    }
    (ROOT / "docs" / "demo-results.json").write_text(json.dumps(report, indent=2))
    print(
        f"{len(outcomes)} synthetic API demonstration scenarios PASSED. No live cloud verification claimed."
    )


if __name__ == "__main__":
    run_demo()
