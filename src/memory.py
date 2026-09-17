# Store conversation context for follow-up questions

conversation_memory = {
    "last_airport": None,
    "last_investigation": None,
    "last_user_query": None
}


def update_memory(airport_code, user_query, investigation=None):
    # Save the latest conversation context
    conversation_memory["last_airport"] = airport_code
    conversation_memory["last_user_query"] = user_query
    conversation_memory["last_investigation"] = investigation


def resolve_airport_reference(user_query):
    # Check whether the user explicitly mentioned an airport
    query = user_query.upper()

    for airport_code in ["SFO", "LAX", "JFK"]:
        if airport_code in query:
            return airport_code

    # Otherwise use the previous airport
    return conversation_memory["last_airport"]


def clear_memory():
    # Reset conversation context
    conversation_memory["last_airport"] = None
    conversation_memory["last_investigation"] = None
    conversation_memory["last_user_query"] = None
    