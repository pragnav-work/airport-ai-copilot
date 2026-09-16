import pandas as pd
from pathlib import Path

# Load the airport telemetry dataset used by the operational tools
DATA_PATH = Path(__file__).resolve().parent.parent / "data" / "airport_metrics.csv"

airport_metrics = pd.read_csv(DATA_PATH)

# Keep only airports supported by the project
VALID_AIRPORTS = ["SFO", "LAX", "JFK"]


def get_airport_metrics(airport_code):
    # Validate the airport code before querying the dataset
    airport_code = airport_code.upper()

    if airport_code not in VALID_AIRPORTS:
        return {
            "status": "error",
            "message": f"Invalid airport code: {airport_code}"
        }

    # Select records belonging to the requested airport
    airport_data = airport_metrics[
        airport_metrics["airport_code"] == airport_code
    ]

    # Use the latest timestamp as the current operational state
    latest = airport_data.sort_values("timestamp").iloc[-1]

    return {
    "status": "success",
    "airport_code": airport_code,
    "completion_rate": float(latest["completion_rate"]),
    "average_eta": int(latest["average_eta"]),
    "active_drivers": int(latest["active_drivers"]),
    "driver_cancellation_rate": float(latest["driver_cancellation_rate"]),
    "queue_size": int(latest["queue_size"]),
    "surge_multiplier": float(latest["surge_multiplier"])
}


def calculate_driver_incentive(driver_count, severity_level):
    # Validate that driver count is a positive number
    if driver_count < 0:
        return {
            "status": "error",
            "message": "driver_count cannot be negative"
        }

    # Define incentive amounts based on shortage severity
    incentive_rates = {
        "low": 5,
        "medium": 10,
        "high": 20
    }

    # Normalize the severity value for consistent lookup
    severity_level = severity_level.lower()

    # Reject unsupported severity levels
    if severity_level not in incentive_rates:
        return {
            "status": "error",
            "message": "severity_level must be low, medium, or high"
        }

    # Calculate the recommended incentive and estimated total cost
    incentive = incentive_rates[severity_level]
    total_cost = driver_count * incentive

    return {
        "status": "success",
        "driver_count": driver_count,
        "severity_level": severity_level,
        "recommended_incentive": incentive,
        "estimated_total_cost": total_cost
    }


def trigger_surge_override(airport_code, new_multiplier, reason):
    # Validate the airport before attempting the mock override
    airport_code = airport_code.upper()

    if airport_code not in VALID_AIRPORTS:
        return {
            "status": "error",
            "message": f"Invalid airport code: {airport_code}"
        }

    # Validate that the surge multiplier is within a reasonable range
    if new_multiplier < 1.0 or new_multiplier > 2.0:
        return {
            "status": "error",
            "message": "Surge multiplier must be between 1.0x and 2.0x"
        }

    # Require a reason so the action has an operational explanation
    if not reason or not reason.strip():
        return {
            "status": "error",
            "message": "Reason is required for surge override"
        }

    # Return a mock execution result; real approval comes on Day 4
    return {
        "status": "success",
        "airport_code": airport_code,
        "new_multiplier": new_multiplier,
        "reason": reason,
        "message": "Surge override executed successfully (mock)"
    }