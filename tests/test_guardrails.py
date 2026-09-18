# Certificate issue resolve

import os

os.environ["REQUESTS_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"
os.environ["SSL_CERT_FILE"] = "/etc/ssl/certs/ca-certificates.crt"

from src.guardrails import (
    check_permission,
    enforce_surge_policy,
    classify_surge_risk,
    request_human_approval,
    evaluate_action,
    execute_guarded_action,
    clear_audit_trail,
    get_audit_trail,
)


def test_admin_has_execute_permission():

    result = check_permission(
        "admin",
        "execute_surge"
    )

    assert result["status"] == "allowed"


def test_analyst_cannot_execute_surge():

    result = check_permission(
        "analyst",
        "execute_surge"
    )

    assert result["status"] == "denied"


def test_surge_within_policy_limit():

    result = enforce_surge_policy(
        "SFO",
        1.4
    )

    assert result["status"] == "allowed"


def test_surge_above_policy_limit():

    result = enforce_surge_policy(
        "SFO",
        1.6
    )

    assert result["status"] == "blocked"


def test_high_risk_surge_requires_approval():

    result = classify_surge_risk(
        "SFO",
        1.4
    )

    assert result["risk_level"] == "high"
    assert result["requires_approval"] is True


def test_low_risk_surge_does_not_require_approval():

    result = classify_surge_risk(
        "SFO",
        1.2
    )

    assert result["risk_level"] == "low"
    assert result["requires_approval"] is False


def test_human_approval_pending():

    result = request_human_approval(
        "SFO",
        1.4,
        "Improve supply",
        approved=False
    )

    assert result["status"] == "pending_approval"


def test_human_approval_received():

    result = request_human_approval(
        "SFO",
        1.4,
        "Improve supply",
        approved=True
    )

    assert result["status"] == "approved"


def test_action_requires_approval():

    result = evaluate_action(
        role="admin",
        airport_code="SFO",
        action="execute_surge",
        new_multiplier=1.4,
        reason="Improve supply",
        approved=False
    )

    assert result["status"] == "pending_approval"


def test_action_is_allowed_after_approval():

    result = evaluate_action(
        role="admin",
        airport_code="SFO",
        action="execute_surge",
        new_multiplier=1.4,
        reason="Improve supply",
        approved=True
    )

    assert result["status"] == "allowed"


def test_action_above_policy_limit_is_blocked():

    result = evaluate_action(
        role="admin",
        airport_code="SFO",
        action="execute_surge",
        new_multiplier=1.6,
        reason="Improve supply",
        approved=True
    )

    assert result["status"] == "blocked"


def test_execute_guarded_action():

    clear_audit_trail()

    result = execute_guarded_action(
        role="admin",
        airport_code="SFO",
        new_multiplier=1.4,
        reason="Improve supply",
        approved=True,
        audit_context={
            "user_request": "Increase surge to 1.4x at SFO",
            "agents_invoked": [
                "investigate_airport",
                "policy_agent",
                "resolution_agent"
            ],
            "tools_called": [
                "get_airport_metrics",
                "trigger_surge_override"
            ],
            "retrieved_policies": [
                "sfo_pricing.md"
            ],
            "recommendation": "Increase surge to 1.4x"
        }
    )

    assert result["status"] == "success"

    audit_trail = get_audit_trail()

    assert len(audit_trail) == 1
    assert audit_trail[0]["airport_code"] == "SFO"
    assert audit_trail[0]["new_multiplier"] == 1.4
    assert audit_trail[0]["approval"] is True
    assert audit_trail[0]["execution_status"] == "success"