# Certificate issue resolve

import os

os.environ["REQUESTS_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"
os.environ["SSL_CERT_FILE"] = "/etc/ssl/certs/ca-certificates.crt"

import re

import streamlit as st

from dotenv import load_dotenv
from google import genai

from src.agents import (
    run_agent_loop,
    load_policy_resources,
    answer_policy_query,
)

from src.guardrails import (
    classify_user_intent,
    execute_guarded_action,
    get_audit_trail,
    get_intent_response,
)

from src.memory import (
    resolve_airport_reference,
    update_memory,
)


# ---------------------------------------------------------
# Configuration
# ---------------------------------------------------------

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY")
)

st.set_page_config(
    page_title="Airport Operations Copilot",
    page_icon="✈️",
    layout="wide"
)


# ---------------------------------------------------------
# Header
# ---------------------------------------------------------

st.title("✈️ Uber Global Airport Operations & Supply Disruption Resolver")
st.caption("Agentic Copilot for airport operations")


# ---------------------------------------------------------
# Session State
# ---------------------------------------------------------

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "last_result" not in st.session_state:
    st.session_state.last_result = None

if "pending_action" not in st.session_state:
    st.session_state.pending_action = None

if "requested_multiplier" not in st.session_state:
    st.session_state.requested_multiplier = None

if "last_intent" not in st.session_state:
    st.session_state.last_intent = None

if "last_action_query" not in st.session_state:
    st.session_state.last_action_query = None

if "last_action_airport" not in st.session_state:
    st.session_state.last_action_airport = None


# ---------------------------------------------------------
# Sidebar
# ---------------------------------------------------------

st.sidebar.header("Airport")

airport_code = st.sidebar.selectbox(
    "Select airport",
    ["SFO", "LAX", "JFK"]
)

resolved_airport = airport_code

st.sidebar.markdown("---")

st.sidebar.write(
    "**Supported airports:** SFO, LAX, JFK"
)

if st.sidebar.button("Clear conversation"):

    st.session_state.chat_history = []
    st.session_state.last_result = None
    st.session_state.pending_action = None
    st.session_state.requested_multiplier = None
    st.session_state.last_intent = None
    st.session_state.last_action_query = None
    st.session_state.last_action_airport = None

    st.rerun()


# ---------------------------------------------------------
# Chat Input
# ---------------------------------------------------------

st.subheader("Ask the Operations Copilot")

user_query = st.chat_input(
    "Example: Can we increase surge to 1.4x?"
)


# ---------------------------------------------------------
# Process User Query
# ---------------------------------------------------------

if user_query:

    # Store user message
    st.session_state.chat_history.append(
        {
            "role": "user",
            "content": user_query
        }
    )


    # -----------------------------------------------------
    # Classify Intent
    # -----------------------------------------------------

    intent = classify_user_intent(user_query)


    # -----------------------------------------------------
    # Detect Follow-up Action
    # -----------------------------------------------------

    multiplier_match = re.fullmatch(
        r"\s*(\d+(?:\.\d+)?)\s*x?\s*",
        user_query,
        re.IGNORECASE
    )

    is_multiplier_followup = (
        multiplier_match is not None
        and st.session_state.last_action_query is not None
    )


    if is_multiplier_followup:

        # Continue the previous action conversation
        intent = "action"

        requested_multiplier = float(
            multiplier_match.group(1)
        )

        resolved_airport = (
            st.session_state.last_action_airport
            or airport_code
        )

    else:

        requested_multiplier = None


    st.session_state.last_intent = intent


    # -----------------------------------------------------
    # Conversational / Out-of-Scope
    # -----------------------------------------------------

    if intent in ["conversational", "out_of_scope"]:

        response = get_intent_response(intent)

        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": response
            }
        )

        st.rerun()


    # -----------------------------------------------------
    # Resolve Airport
    # -----------------------------------------------------

    if not is_multiplier_followup:

        query_airport = resolve_airport_reference(
            user_query
        )

        if query_airport is not None:
            resolved_airport = query_airport


    # -----------------------------------------------------
    # RAG Query
    # -----------------------------------------------------

    if intent == "rag":

        update_memory(
            resolved_airport,
            user_query
        )

        with st.spinner("Searching airport policies..."):

            chunks, policy_index = load_policy_resources()

            result = answer_policy_query(
                user_query,
                chunks,
                policy_index,
                client,
                airport_code=resolved_airport
            )

        st.session_state.last_result = result

        if result["status"] == "success":

            response = result["answer"]

            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": response
                }
            )

        else:

            st.session_state.chat_history.append(
                {
                    "role": "assistant",
                    "content": result.get(
                        "message",
                        "Unable to answer the policy question."
                    )
                }
            )

        st.rerun()


    # -----------------------------------------------------
    # Extract Surge Multiplier
    # -----------------------------------------------------

    if not is_multiplier_followup:

        match = re.search(
            r"(\d+(?:\.\d+)?)\s*x\b",
            user_query,
            re.IGNORECASE
        )

        if match:
            requested_multiplier = float(
                match.group(1)
            )


    st.session_state.requested_multiplier = (
        requested_multiplier
    )


    # -----------------------------------------------------
    # Action Context
    # -----------------------------------------------------

    # Remember the action so a follow-up like "1.4x"
    # can continue the previous request.
    st.session_state.last_action_query = user_query
    st.session_state.last_action_airport = resolved_airport


    # -----------------------------------------------------
    # Update Memory
    # -----------------------------------------------------

    update_memory(
        resolved_airport,
        user_query
    )


    # -----------------------------------------------------
    # Action Workflow
    # -----------------------------------------------------

    with st.spinner("Analyzing airport operations..."):

        result = run_agent_loop(
            resolved_airport,
            client,
            requested_multiplier=requested_multiplier
        )

    st.session_state.last_result = result


    # -----------------------------------------------------
    # Add Short Chat Response
    # -----------------------------------------------------

    if result["status"] == "success":

        recommendation = (
            result["state"]["recommendation"]
        )


        # No multiplier detected
        if requested_multiplier is None:

            response = (
                f"I can help with the {resolved_airport} surge request, "
                "but I couldn't identify a valid surge multiplier.\n\n"
                "Please specify a target such as **1.2x** or **1.4x**."
            )

        else:

            response = recommendation


        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": response
            }
        )

    else:

        st.session_state.chat_history.append(
            {
                "role": "assistant",
                "content": result.get(
                    "message",
                    "Unable to complete the investigation."
                )
            }
        )

    st.rerun()


# ---------------------------------------------------------
# Display Conversation
# ---------------------------------------------------------

for message in st.session_state.chat_history:

    with st.chat_message(message["role"]):

        st.write(message["content"])


# ---------------------------------------------------------
# Result Dashboard
# ---------------------------------------------------------

result = st.session_state.last_result


# =========================================================
# RAG RESULT
# =========================================================

if (
    result
    and result["status"] == "success"
    and st.session_state.last_intent == "rag"
):

    st.markdown("---")

    st.subheader("📚 Policy Information")

    st.write(result["answer"])

    with st.expander("Policy Sources"):

        for source in result["sources"]:

            st.write(
                f"- {source}"
            )

    with st.expander("View Retrieved Policy Context"):

        st.write(
            result["context"]
        )


# =========================================================
# ACTION RESULT
# =========================================================

if (
    result
    and result["status"] == "success"
    and st.session_state.last_intent == "action"
):

    investigation = (
        result["state"]["investigation"]
    )

    policy = (
        result["state"]["policy"]
    )

    recommendation = (
        result["state"]["recommendation"]
    )

    metrics = investigation["metrics"]

    requested_multiplier = (
        st.session_state.requested_multiplier
    )


    # -----------------------------------------------------
    # Compact Operational Summary
    # -----------------------------------------------------

    st.markdown("---")

    st.subheader(
        f"{resolved_airport} Operational Summary"
    )

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Completion Rate",
        f"{metrics['completion_rate']:.0%}"
    )

    col2.metric(
        "Average ETA",
        f"{metrics['average_eta']} min"
    )

    col3.metric(
        "Active Drivers",
        metrics["active_drivers"]
    )

    col4.metric(
        "Current Surge",
        f"{metrics['surge_multiplier']}x"
    )

    st.write(
        f"**Severity:** "
        f"{investigation['severity'].upper()}  ·  "
        f"**Issue:** "
        f"{investigation['issue']}"
    )


    # -----------------------------------------------------
    # Human Approval
    # -----------------------------------------------------

    if requested_multiplier is not None:

        st.markdown("---")

        st.subheader("⚡ Surge Action")

        proposed_multiplier = st.number_input(
            "Proposed surge multiplier",
            min_value=1.0,
            max_value=2.0,
            value=float(requested_multiplier),
            step=0.1
        )

        reason = st.text_input(
            "Reason",
            value=(
                "Improve supply during "
                "below-normal completion rate"
            )
        )


        # High-risk action
        if proposed_multiplier > 1.3:

            st.warning(
                f"Requested surge: "
                f"**{proposed_multiplier}x**\n\n"
                "Operations Manager approval is required "
                "before execution."
            )

            col1, col2 = st.columns(2)

            with col1:

                if st.button(
                    "Approve & Execute",
                    type="primary"
                ):

                    audit_context = {
                        "user_request": (
                            st.session_state.last_action_query
                        ),
                        "agents_invoked": [
                            "investigate_airport",
                            "policy_agent",
                            "resolution_agent"
                        ],
                        "tools_called": [
                            "get_airport_metrics",
                            "trigger_surge_override"
                        ],
                        "retrieved_policies": (
                            policy["sources"]
                        ),
                        "recommendation": recommendation
                    }

                    execution_result = (
                        execute_guarded_action(
                            role="admin",
                            airport_code=resolved_airport,
                            new_multiplier=proposed_multiplier,
                            reason=reason,
                            approved=True,
                            audit_context=audit_context
                        )
                    )

                    st.session_state.pending_action = (
                        execution_result
                    )

                    st.rerun()


            with col2:

                if st.button("Reject"):

                    st.session_state.pending_action = {
                        "status": "rejected",
                        "message": (
                            "Human approval rejected."
                        )
                    }

                    st.rerun()


        # Low-risk action
        else:

            st.info(
                f"Requested surge: "
                f"**{proposed_multiplier}x**\n\n"
                "This value is within the standard "
                "approval range."
            )


    # -----------------------------------------------------
    # Execution Result
    # -----------------------------------------------------

    if st.session_state.pending_action:

        execution_result = (
            st.session_state.pending_action
        )

        if execution_result["status"] == "success":

            st.success(
                execution_result["message"]
            )

        elif execution_result["status"] == "rejected":

            st.info(
                execution_result["message"]
            )

        else:

            st.error(
                execution_result.get(
                    "message",
                    "Action was not executed."
                )
            )


    # -----------------------------------------------------
    # Expandable Operational Details
    # -----------------------------------------------------

    st.markdown("---")

    with st.expander("📊 Operational Details"):

        st.write(
            f"**Airport:** {resolved_airport}"
        )

        st.write(
            f"**Completion Rate:** "
            f"{metrics['completion_rate']:.0%}"
        )

        st.write(
            f"**Average ETA:** "
            f"{metrics['average_eta']} minutes"
        )

        st.write(
            f"**Active Drivers:** "
            f"{metrics['active_drivers']}"
        )

        st.write(
            f"**Driver Cancellation Rate:** "
            f"{metrics['driver_cancellation_rate']:.0%}"
        )

        st.write(
            f"**Queue Size:** "
            f"{metrics['queue_size']}"
        )

        st.write(
            f"**Current Surge:** "
            f"{metrics['surge_multiplier']}x"
        )

        st.write(
            f"**Severity:** "
            f"{investigation['severity'].upper()}"
        )

        st.write(
            f"**Issue:** "
            f"{investigation['issue']}"
        )


    # -----------------------------------------------------
    # Agent Activity
    # -----------------------------------------------------

    with st.expander("🤖 Agent Activity"):

        for step in result["trace"]:

            st.write(
                f"**Iteration {step['iteration']}** — "
                f"{step['action']} → "
                f"{step['observation']}"
            )


    # -----------------------------------------------------
    # RAG / Policy Details
    # -----------------------------------------------------

    with st.expander("📚 Policy Sources & RAG"):

        st.write(
            "Retrieved policy documents:"
        )

        for source in policy["sources"]:

            st.write(
                f"- {source}"
            )

        with st.expander(
            "View Retrieved Policy Context"
        ):

            st.write(
                policy["context"]
            )


    # -----------------------------------------------------
    # Audit Trail
    # -----------------------------------------------------

    with st.expander("🔍 Audit Trail"):

        audit_trail = get_audit_trail()

        if audit_trail:

            for record in audit_trail:

                st.json(record)

        else:

            st.info(
                "No guarded actions have been executed yet."
            )