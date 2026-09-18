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
            "message": (
                "Requested surge exceeds the maximum "
                "permitted limit"
            )
        }

    # Require approval above 1.3x
    if new_multiplier > 1.3:
        return {
            "status": "approval_required",
            "risk_level": "high",
            "requires_approval": True,
            "message": (
                "Operations Manager approval is required"
            )
        }

    return {
        "status": "allowed",
        "risk_level": "low",
        "requires_approval": False,
        "message": (
            "Surge is within the standard approval range"
        )
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
            "message": (
                "Human approval is required before execution"
            )
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
            "message": (
                "new_multiplier and reason are required"
            )
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
            "message": (
                "Operations Manager approval required"
            )
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
    approved=False,
    audit_context=None
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

    # Use additional workflow information when provided
    audit_context = audit_context or {}

    # Store the complete decision trail
    audit_record = {
        "user_request": audit_context.get(
            "user_request"
        ),
        "agents_invoked": audit_context.get(
            "agents_invoked",
            []
        ),
        "tools_called": audit_context.get(
            "tools_called",
            []
        ),
        "retrieved_policies": audit_context.get(
            "retrieved_policies",
            []
        ),
        "recommendation": audit_context.get(
            "recommendation"
        ),
        "role": role,
        "airport_code": airport_code,
        "action": "execute_surge",
        "new_multiplier": new_multiplier,
        "reason": reason,
        "approval": approved,
        "guardrail_status": decision["status"],
        "risk_level": decision.get("risk_level"),
        "final_action": "execute_surge",
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


# ---------------------------------------------------------
# Intent Classification
# ---------------------------------------------------------

def classify_user_intent(user_query):
    """
    Classify the user's request before running the agent workflow.
    """

    query = user_query.strip().lower()

    if not query:
        return "out_of_scope"


    # -----------------------------------------------------
    # Conversational Requests
    # -----------------------------------------------------

    conversational_phrases = [
        "hi",
        "hello",
        "hey",
        "hi there",
        "hello there",
        "hey there",
        "good morning",
        "good afternoon",
        "good evening",
        "what can you do",
        "what can i do",
        "what can i ask",
        "what can i ask you",
        "what do you do",
        "how can you help",
        "how can you help me",
        "help",
        "help me",
        "who are you",
        "thanks",
        "thank you",
        "thankyou"
    ]

    if query in conversational_phrases:
        return "conversational"


    # -----------------------------------------------------
    # Action Requests
    # -----------------------------------------------------

    action_keywords = [
        "increase surge",
        "decrease surge",
        "change surge",
        "set surge",
        "trigger surge",
        "execute surge",
        "approve surge",
        "apply surge",
        "raise surge",
        "lower surge",
        "increase the surge",
        "decrease the surge",
        "change the surge",
        "set the surge",
        "driver incentive",
        "driver incentives",
        "give drivers",
        "calculate incentive",
        "calculate incentives",
        "validate trip",
        "validate",
        "execute",
        "approve"
    ]

    if any(keyword in query for keyword in action_keywords):
        return "action"


    # -----------------------------------------------------
    # RAG / Information Requests
    # -----------------------------------------------------

    rag_keywords = [
        "policy",
        "policies",
        "maximum surge",
        "max surge",
        "surge limit",
        "surge limits",
        "surge range",
        "surge",
        "completion rate",
        "average eta",
        "eta",
        "active drivers",
        "driver cancellation",
        "cancellation rate",
        "queue",
        "queue size",
        "pricing",
        "operations",
        "operational",
        "supply",
        "drivers",
        "metrics",
        "metric",
        "airport",
        "airport operations",
        "what is",
        "what are",
        "how many",
        "how much",
        "why is",
        "why are",
        "current"
    ]

    airport_codes = [
        "sfo",
        "lax",
        "jfk"
    ]

    if (
        any(keyword in query for keyword in rag_keywords)
        or any(airport in query for airport in airport_codes)
    ):
        return "rag"


    # -----------------------------------------------------
    # Out of Scope
    # -----------------------------------------------------

    return "out_of_scope"


# ---------------------------------------------------------
# Intent Responses
# ---------------------------------------------------------

def get_intent_response(intent):
    """
    Return a helpful response for conversational
    and out-of-scope requests.
    """

    if intent == "conversational":
        return (
            "Hello! 👋 I'm the Airport Operations Copilot.\n\n"
            "I can help with:\n"
            "- Airport operational metrics\n"
            "- Airport policies and pricing rules\n"
            "- Driver supply and incentives\n"
            "- Surge pricing validation\n"
            "- High-risk action approval and execution\n\n"
            "Supported airports: SFO, LAX, and JFK.\n\n"
            "Try asking:\n"
            "- \"What is the completion rate at SFO?\"\n"
            "- \"What is the maximum surge at SFO?\"\n"
            "- \"Can we increase surge to 1.4x at SFO?\""
        )


    if intent == "out_of_scope":
        return (
            "I can help with airport operations, but I'm not sure "
            "what you'd like me to do with that request.\n\n"
            "I can help with:\n"
            "- Airport operational metrics\n"
            "- Airport policies and pricing rules\n"
            "- Driver supply and incentives\n"
            "- Surge pricing validation\n"
            "- High-risk action approval and execution\n\n"
            "Supported airports: SFO, LAX, and JFK.\n\n"
            "For example, you can ask:\n"
            "- \"What is the current surge at SFO?\"\n"
            "- \"What is the maximum surge at SFO?\"\n"
            "- \"Can we increase surge to 1.4x at SFO?\""
        )

    return None