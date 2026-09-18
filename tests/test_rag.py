# Certificate issue resolve

import os

os.environ["REQUESTS_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"
os.environ["SSL_CERT_FILE"] = "/etc/ssl/certs/ca-certificates.crt"

from src.agents import load_policy_resources, search_policy


def test_policy_resources_load():

    chunks, policy_index = load_policy_resources()

    assert len(chunks) > 0
    assert policy_index.ntotal == len(chunks)


def test_sfo_policy_retrieval():

    chunks, policy_index = load_policy_resources()

    results = search_policy(
        "SFO surge multiplier maximum limit",
        chunks,
        policy_index,
        top_k=3,
        airport_code="SFO"
    )

    assert len(results) > 0

    sources = [result["source"] for result in results]

    assert all(
        source.lower().startswith("sfo")
        for source in sources
    )


def test_policy_retrieval_contains_pricing_policy():

    chunks, policy_index = load_policy_resources()

    results = search_policy(
        "SFO surge pricing maximum permitted multiplier",
        chunks,
        policy_index,
        top_k=3,
        airport_code="SFO"
    )

    sources = [result["source"] for result in results]

    assert "sfo_pricing.md" in sources