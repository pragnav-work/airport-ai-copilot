from src.tools import trigger_surge_override


# Define permissions for each user role
ROLE_PERMISSIONS = {
    "analyst": [
        "view_metrics",
        "generate_recommendation"
    ],
    "operations_manager": [
        "view_metrics",
        "generate_recommendation",
        "approve_surge"
    ],
    "admin": [
        "view_metrics",
        "generate_recommendation",
        "approve_surge",
        "execute_surge"
    ]
}


# Store audit records for guarded actions
audit_trail = []


def check_permission(role, action):
    # Reject unknown roles
    if role not in ROLE_PERMISSIONS:
        return {
            "status": "error",
            "message": f"Unknown role: {role}"
        }

    # Check whether the role can perform the action
    if action not in ROLE_PERMISSIONS[role]:
        return {
            "status": "denied",
            "message": f"Role '{role}' cannot perform '{action}'"
        }

    return {
        "status": "allowed",
        "role": role,
        "action": action
    }


def enforce_surge_policy(airport_code, new_multiplier):
    # Define airport-specific maximum surge limits
    max_surge = {
        "SFO": 1.5,
        "LAX": 1.6,
        "JFK": 1.5
    }

    # Reject unsupported airports
    if airport_code not in max_surge:
        return {
            "status": "error",
            "message": f"Invalid airport code: {airport_code}"
        }

    # Block surge above the airport maximum
    if new_multiplier > max_surge[airport_code]:
        return {
            "status": "blocked",
            "message": (
                f"{airport_code} maximum surge is "
                f"{max_surge[airport_code]}x"
            )
        }

    return {
        "status": "allowed",
        "airport_code": airport_code,
        "new_multiplier": new_multiplier
    }


def classify_surge_risk(airport_code, new_multiplier):
    # Define airport-specific maximum surge limits
    max_surge = {
        "SFO": 1.5,
        "LAX": 1.6,
        "JFK": 1.5
    }

    # Validate the airport
    if airport_code not in max_surge:
        return {
            "status": "error",
            "message": f"Invalid airport code: {airport_code}"
        }

    # Block values above the airport policy limit
    if new_multiplier > max_surge[airport_code]:
        return {
            "status": "blocked",
            "risk_level": "high",
            "requires_approval": False,
            "message": "Requested surge exceeds the maximum permitted limit"
        }

    # Require approval above 1.3x
    if new_multiplier > 1.3:
        return {
            "status": "approval_required",
            "risk_level": "high",
            "requires_approval": True,
            "message": "Operations Manager approval is required"
        }

    return {
        "status": "allowed",
        "risk_level": "low",
        "requires_approval": False,
        "message": "Surge is within the standard approval range"
    }


def request_human_approval(
    airport_code,
    new_multiplier,
    reason,
    approved=False
):
    # Stop until explicit approval is provided
    if not approved:
        return {
            "status": "pending_approval",
            "airport_code": airport_code,
            "new_multiplier": new_multiplier,
            "reason": reason,
            "message": "Human approval is required before execution"
        }

    return {
        "status": "approved",
        "airport_code": airport_code,
        "new_multiplier": new_multiplier,
        "reason": reason,
        "message": "Human approval received"
    }


def evaluate_action(
    role,
    airport_code,
    action,
    new_multiplier=None,
    reason=None,
    approved=False
):
    # Check whether the requested action is supported
    if action != "execute_surge":
        return {
            "status": "blocked",
            "message": f"Unsupported action: {action}"
        }

    # Check execution permission
    permission = check_permission(role, action)

    if permission["status"] != "allowed":
        return permission

    # Validate required parameters
    if new_multiplier is None or reason is None:
        return {
            "status": "error",
            "message": "new_multiplier and reason are required"
        }

    # Check the airport-specific policy
    policy = enforce_surge_policy(
        airport_code,
        new_multiplier
    )

    if policy["status"] != "allowed":
        return policy

    # Determine whether approval is required
    risk = classify_surge_risk(
        airport_code,
        new_multiplier
    )

    if risk["requires_approval"] and not approved:
        return {
            "status": "pending_approval",
            "risk_level": risk["risk_level"],
            "message": "Operations Manager approval required"
        }

    return {
        "status": "allowed",
        "risk_level": risk["risk_level"],
        "message": "Action passed all guardrails"
    }


def execute_guarded_action(
    role,
    airport_code,
    new_multiplier,
    reason,
    approved=False
):
    # Evaluate the action before execution
    decision = evaluate_action(
        role,
        airport_code,
        "execute_surge",
        new_multiplier,
        reason,
        approved
    )

    # Store the complete guardrail decision
    audit_record = {
        "role": role,
        "airport_code": airport_code,
        "action": "execute_surge",
        "new_multiplier": new_multiplier,
        "reason": reason,
        "approval": approved,
        "guardrail_status": decision["status"],
        "risk_level": decision.get("risk_level"),
        "execution_status": "not_executed"
    }

    # Stop when any guardrail rejects the action
    if decision["status"] != "allowed":
        audit_trail.append(audit_record)
        return decision

    # Execute the Day 2 tool only after all checks pass
    result = trigger_surge_override(
        airport_code,
        new_multiplier,
        reason
    )

    # Record the execution result
    audit_record["execution_status"] = result["status"]
    audit_trail.append(audit_record)

    return result


def get_audit_trail():
    # Return all recorded guarded decisions
    return audit_trail


def clear_audit_trail():
    # Clear previous audit records
    audit_trail.clear()


def create_distilled_record(
    instruction,
    context,
    tool_calls,
    recommendation,
    policy_check,
    human_approval,
    final_action
):
    # Create one structured interaction record
    return {
        "instruction": instruction,
        "context": context,
        "tool_calls": tool_calls,
        "recommendation": recommendation,
        "policy_check": policy_check,
        "human_approval": human_approval,
        "final_action": final_action
    }