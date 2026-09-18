# Certificate issue resolve
import os

os.environ["REQUESTS_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"
os.environ["SSL_CERT_FILE"] = "/etc/ssl/certs/ca-certificates.crt"

from pathlib import Path
import re

import faiss
import numpy as np
from sentence_transformers import SentenceTransformer

from src.tools import get_airport_metrics
from src.prompts import (
    INVESTIGATOR_INSTRUCTION,
    POLICY_INSTRUCTION,
    RESOLUTION_INSTRUCTION,
    ORCHESTRATOR_INSTRUCTION
)


# Load policy documents from the project
POLICY_PATH = (
    Path(__file__).resolve().parent.parent
    / "data"
    / "airport_policies"
)

# Load the embedding model once
embedding_model = SentenceTransformer("all-MiniLM-L6-v2")


def load_policy_resources():
    # Read policy files and create chunks
    chunks = []

    for file in POLICY_PATH.glob("*.md"):
        text = file.read_text()

        for i in range(0, len(text), 400):
            chunk = text[i:i + 500]

            if chunk.strip():
                chunks.append({
                    "text": chunk,
                    "source": file.name
                })

    # Create embeddings for all policy chunks
    texts = [chunk["text"] for chunk in chunks]

    embeddings = embedding_model.encode(
        texts,
        normalize_embeddings=True
    )

    # Build FAISS index using inner product similarity
    policy_index = faiss.IndexFlatIP(384)

    policy_index.add(
        np.array(embeddings, dtype="float32")
    )

    return chunks, policy_index


def investigate_airport(airport_code):
    # Get the latest operational metrics
    metrics = get_airport_metrics(airport_code)

    if metrics["status"] == "error":
        return metrics

    # Classify operational severity using completion rate
    if metrics["completion_rate"] < 0.85:
        severity = "high"
        issue = "Low completion rate"

    elif metrics["completion_rate"] < 0.90:
        severity = "medium"
        issue = "Below-normal completion rate"

    else:
        severity = "low"
        issue = "No major completion-rate anomaly"

    return {
        "status": "success",
        "airport_code": airport_code,
        "metrics": metrics,
        "severity": severity,
        "issue": issue
    }


def search_policy(
    query,
    chunks,
    policy_index,
    top_k=3,
    airport_code=None
):
    # Convert the query into an embedding
    query_embedding = embedding_model.encode(
        [query],
        convert_to_numpy=True
    )

    # Normalize for cosine similarity using inner product
    faiss.normalize_L2(query_embedding)

    # Restrict results to the selected airport
    if airport_code:
        airport_chunks = [
            chunk
            for chunk in chunks
            if chunk["source"].lower().startswith(
                airport_code.lower()
            )
        ]
    else:
        airport_chunks = chunks

    # Create embeddings for filtered policy chunks
    airport_texts = [
        chunk["text"]
        for chunk in airport_chunks
    ]

    airport_embeddings = embedding_model.encode(
        airport_texts,
        normalize_embeddings=True
    )

    airport_index = faiss.IndexFlatIP(384)

    airport_index.add(
        np.array(airport_embeddings, dtype="float32")
    )

    # Retrieve more chunks so unique policy sources can be selected
    scores, indices = airport_index.search(
        query_embedding,
        min(top_k * 3, len(airport_chunks))
    )

    results = []
    seen_sources = set()

    for score, idx in zip(scores[0], indices[0]):
        source = airport_chunks[idx]["source"]

        # Keep only one result per policy document
        if source in seen_sources:
            continue

        result = airport_chunks[idx].copy()
        result["score"] = float(score)

        results.append(result)
        seen_sources.add(source)

        if len(results) == top_k:
            break

    return results


def policy_agent(
    query,
    chunks,
    policy_index,
    airport_code=None
):
    # Retrieve relevant policy chunks
    results = search_policy(
        query,
        chunks,
        policy_index,
        airport_code=airport_code
    )

    # Build the policy context
    context = ""

    for result in results:
        context += f"Source: {result['source']}\n"
        context += f"{result['text']}\n\n"

    return {
        "status": "success",
        "context": context,
        "sources": [
            result["source"]
            for result in results
        ]
    }

def answer_policy_query(
    query,
    chunks,
    policy_index,
    client,
    airport_code=None
):
    policy_result = policy_agent(
        query,
        chunks,
        policy_index,
        airport_code=airport_code
    )

    prompt = f"""
You are an airport operations policy assistant.

Answer the user's question using only the retrieved policy context.

Rules:
- Give a concise answer.
- Do not perform or recommend an operational action.
- Do not invent information.
- If the policy does not contain the answer, say so.
- Use the airport specified by the user.
- Mention the relevant policy rule clearly.

User Question:
{query}

Retrieved Policy Context:
{policy_result["context"]}

Answer:
"""

    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    return {
        "status": "success",
        "answer": response.text,
        "sources": policy_result["sources"],
        "context": policy_result["context"]
    }


def resolution_agent(
    investigation,
    policy_result,
    client,
    requested_multiplier=None
):
    # Include the user's requested multiplier in the reasoning
    if requested_multiplier is not None:
        requested_action = (
            f"The user requested a surge multiplier of "
            f"{requested_multiplier}x."
        )
    else:
        requested_action = (
            "The user did not specify a surge multiplier."
        )

    # Build the resolution prompt from collected evidence
    prompt = f"""
{RESOLUTION_INSTRUCTION}

User Requested Action:
{requested_action}

Important:
- Evaluate the user's requested multiplier against the retrieved policy.
- Do not silently replace the requested multiplier with another value.
- If the requested multiplier is allowed, evaluate that exact multiplier.
- If the requested multiplier requires approval, explicitly state that approval is required.
- If the requested multiplier violates policy, explain why and propose a compliant alternative.
- Keep the recommendation consistent with the requested action and policy.

Operational Investigation:
{investigation}

Applicable Policy:
{policy_result["context"]}

Generate:
1. Issue
2. Evidence
3. Applicable Policy
4. Recommended Action
5. Reason
"""

    # Ask Gemini to generate the recommendation
    response = client.models.generate_content(
        model="gemini-3.5-flash-lite",
        contents=prompt
    )

    return response.text


def orchestrate_airport_issue(
    airport_code,
    chunks,
    policy_index,
    client,
    requested_multiplier=None
):
    # Investigate the airport first
    investigation = investigate_airport(airport_code)

    if investigation["status"] == "error":
        return investigation

    # Retrieve policies related to the investigation
    policy_query = f"""
    {airport_code} operational issue, completion rate,
    surge multiplier, maximum surge limit, and approval requirements
    """

    policy_result = policy_agent(
        policy_query,
        chunks,
        policy_index,
        airport_code=airport_code
    )

    # Generate the final resolution recommendation
    recommendation = resolution_agent(
        investigation,
        policy_result,
        client,
        requested_multiplier=requested_multiplier
    )

    return {
        "status": "success",
        "airport_code": airport_code,
        "investigation": investigation,
        "policy": policy_result,
        "recommendation": recommendation,
        "requested_multiplier": requested_multiplier
    }


MAX_ITERATIONS = 5


def run_agent_loop(
    airport_code,
    client,
    requested_multiplier=None
):
    # Load RAG resources inside the application
    chunks, policy_index = load_policy_resources()

    # Store visible workflow actions and observations
    trace = []

    state = {
        "airport_code": airport_code,
        "investigation": None,
        "policy": None,
        "recommendation": None,
        "requested_multiplier": requested_multiplier
    }

    for iteration in range(1, MAX_ITERATIONS + 1):

        if state["investigation"] is None:
            # First action: investigate operational conditions
            action = "investigate_airport"

            result = investigate_airport(airport_code)

            if result["status"] == "error":
                trace.append({
                    "iteration": iteration,
                    "action": action,
                    "observation": result["message"]
                })

                return {
                    "status": "error",
                    "trace": trace
                }

            state["investigation"] = result
            observation = "Airport investigation completed"

        elif state["policy"] is None:
            # Second action: retrieve applicable policy
            action = "retrieve_policy"

            policy_query = f"""
            {airport_code} completion rate, surge limits,
            approval requirements, and operational restrictions
            """

            result = policy_agent(
                policy_query,
                chunks,
                policy_index,
                airport_code=airport_code
            )

            state["policy"] = result
            observation = "Relevant airport policy retrieved"

        elif state["recommendation"] is None:
            # Third action: generate resolution
            action = "generate_recommendation"

            state["recommendation"] = resolution_agent(
                state["investigation"],
                state["policy"],
                client,
                requested_multiplier=state["requested_multiplier"]
            )

            observation = "Resolution recommendation generated"

        else:
            # Stop when all required stages are complete
            trace.append({
                "iteration": iteration,
                "action": "stop",
                "observation": "Investigation completed"
            })

            break

        # Record the visible action-observation trace
        trace.append({
            "iteration": iteration,
            "action": action,
            "observation": observation
        })

    return {
        "status": "success",
        "state": state,
        "trace": trace
    }