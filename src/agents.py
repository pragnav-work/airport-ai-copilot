from pathlib import Path

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


def search_policy(query, chunks, policy_index, top_k=3):
    # Convert the query into an embedding
    query_embedding = embedding_model.encode(
        [query],
        convert_to_numpy=True
    )

    # Normalize for cosine similarity using inner product
    faiss.normalize_L2(query_embedding)

    # Retrieve the most relevant policy chunks
    scores, indices = policy_index.search(
        query_embedding,
        top_k
    )

    results = []

    for score, idx in zip(scores[0], indices[0]):
        result = chunks[idx].copy()
        result["score"] = float(score)
        results.append(result)

    return results


def policy_agent(query, chunks, policy_index):
    # Retrieve relevant policy chunks
    results = search_policy(
        query,
        chunks,
        policy_index
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


def resolution_agent(investigation, policy_result, client):
    # Build the resolution prompt from collected evidence
    prompt = f"""
{RESOLUTION_INSTRUCTION}

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
    client
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
        policy_index
    )

    # Generate the final resolution recommendation
    recommendation = resolution_agent(
        investigation,
        policy_result,
        client
    )

    return {
        "status": "success",
        "airport_code": airport_code,
        "investigation": investigation,
        "policy": policy_result,
        "recommendation": recommendation
    }


MAX_ITERATIONS = 5


def run_agent_loop(
    airport_code,
    client
):
    # Load RAG resources inside the application
    chunks, policy_index = load_policy_resources()

    # Store visible workflow actions and observations
    trace = []

    state = {
        "airport_code": airport_code,
        "investigation": None,
        "policy": None,
        "recommendation": None
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
                policy_index
            )

            state["policy"] = result
            observation = "Relevant airport policy retrieved"

        elif state["recommendation"] is None:
            # Third action: generate resolution
            action = "generate_recommendation"

            state["recommendation"] = resolution_agent(
                state["investigation"],
                state["policy"],
                client
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