# Certificate issue resolve

import os

os.environ["REQUESTS_CA_BUNDLE"] = "/etc/ssl/certs/ca-certificates.crt"
os.environ["SSL_CERT_FILE"] = "/etc/ssl/certs/ca-certificates.crt"

from src.tools import (
    get_airport_metrics,
    calculate_driver_incentive,
    trigger_surge_override,
)


def test_get_airport_metrics():

    result = get_airport_metrics("SFO")

    assert result["status"] == "success"
    assert result["airport_code"] == "SFO"
    assert result["completion_rate"] == 0.86
    assert result["surge_multiplier"] == 1.1


def test_invalid_airport():

    result = get_airport_metrics("ABC")

    assert result["status"] == "error"


def test_driver_incentive():

    result = calculate_driver_incentive(
        100,
        "high"
    )

    assert result["status"] == "success"
    assert result["recommended_incentive"] == 20
    assert result["estimated_total_cost"] == 2000


def test_invalid_driver_count():

    result = calculate_driver_incentive(
        -10,
        "high"
    )

    assert result["status"] == "error"


def test_surge_override():

    result = trigger_surge_override(
        "SFO",
        1.4,
        "Improve supply"
    )

    assert result["status"] == "success"
    assert result["new_multiplier"] == 1.4


def test_surge_above_tool_limit():

    result = trigger_surge_override(
        "SFO",
        2.1,
        "Improve supply"
    )

    assert result["status"] == "error"


def test_surge_requires_reason():

    result = trigger_surge_override(
        "SFO",
        1.4,
        ""
    )

    assert result["status"] == "error"