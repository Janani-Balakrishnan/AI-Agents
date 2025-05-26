import json
import pandas as pd
import re
from llm_client import client
from intent_keywords import DATA_QUERY_KEYWORDS 
from query_handler import (
    get_db_schema,
    get_db_connection,
    convert_bson,
    clean_generated_query,
    extract_mongo_query,
    format_query_for_eval,
    map_status_in_query
)
# Agent to generate mongo query
def generate_mongo_query_from_user_query(user_query, history_context=""):
    schema = get_db_schema() 
    # Get schema and sample data
    schema_str = json.dumps(schema, indent=2)[:5000]
    
    #  Convert status names to numbers in user query
    if any(keyword in user_query.lower() for keyword in ["trip", "trips", "tripplanners"]):
        user_query = map_status_in_query(user_query)  # Apply status mapping only for trip queries
        print(user_query)

    prompt = f"""
    You are an expert in MongoDB. Give your prompt

    Database Schema and Sample Data: {schema_str}

    Conversation history: {history_context}
 
    Current User Question: {user_query}

    MongoDB Query:
    """

    response = client.chat.completions.create(
        model="give any gemini model of your choice & requirement",
        n=1,
        messages=[{"role": "user", "content": prompt}]
    )

    mongo_query = response.choices[0].message.content.strip()
    
    #  Extract only the valid query
    mongo_query = extract_mongo_query(mongo_query)
    #  Fix incorrect syntax before execution
    mongo_query = format_query_for_eval(mongo_query)
    if "package_code" in mongo_query:
    # Find package_code value and replace spaces with hyphens correctly
        mongo_query = re.sub(r'("package_code"\s*:\s*")([^"]+)"', lambda m: f'{m.group(1)}{m.group(2).replace(" ", "-")}"', mongo_query)

    mongo_query = clean_generated_query(mongo_query,user_query)
    return mongo_query

def generate_natural_response(user_query, history_context=""):
    try:
        #  First: Handle system-level/general/smalltalk responses
        fallback_response = handle_no_query_case(user_query, history_context)

        #  Intent check for data-related terms
        if any(keyword in user_query.lower() for keyword in DATA_QUERY_KEYWORDS):
            mongo_query = generate_mongo_query_from_user_query(user_query, history_context)

            #  If query is invalid or empty, fallback
            if not mongo_query or not is_valid_mongo_query(mongo_query):
                return fallback_response

            #  Execute MongoDB query
            db = get_db_connection()
            results = eval(mongo_query, {"db": db})

            #  Format results
            if isinstance(results, int):
                results_list = [{"count": results}]
            else:
                results_list = [convert_bson(doc) for doc in results]

            results_str = json.dumps(results_list, indent=2)

            #  Use LLM to summarize result
            return generate_llm_response(user_query, history_context, mongo_query, results_list, results_str)

        #  If not a data query, return fallback (general/system response)
        return fallback_response

    except Exception as e:
        print("exception:", e)
        #  Redirect any unexpected failure to fallback logic
        return handle_no_query_case(user_query, history_context)

#Agent to generate natural response with query results
def generate_llm_response(user_query, history_context, mongo_query, results_list, results_str):
    format_prompt = f"""
    Conversation so far: "{history_context}"
    Current user query: "{user_query}"
    The MongoDB query executed was: "{mongo_query}"
    The raw results are: {results_str}
    ***Give me your prompt***
    """

    messages = [
        {"role": "system", "content": format_prompt},
        {"role": "user", "content": user_query},
        {"role": "user", "content": f"The MongoDB query executed was: {mongo_query}"},
        {"role": "user", "content": f"The raw results are: {results_str}"}
    ]

    response = client.chat.completions.create(
        model="give any gemini model of your choice & requirement",
        n=1,
        messages=messages
    )

    return {
        "natural_response": response.choices[0].message.content,
        "mongo_query": mongo_query,
        "results_df": pd.DataFrame(results_list)
    }

# Agent to handle general talks
def handle_no_query_case(user_query, history_context=""):
    fallback_prompt = f""" 
Conversation so far: "{history_context}"
Current user query: "{user_query}"

You are Fleet Management Assist.
Since no database query was needed, respond naturally and appropriately.

"""


    messages = [
        {"role": "system", "content": fallback_prompt},
        {"role": "user", "content": user_query}
    ]

    response = client.chat.completions.create(
        model="give any gemini model of your choice & requirement",
        n=1,
        messages=messages
    )

    return {
        "natural_response": response.choices[0].message.content,
        "mongo_query": "No valid query generated",
        "results_df": pd.DataFrame()
    }

def is_valid_mongo_query(query: str) -> bool:
    """Check if the generated string looks like a real MongoDB query."""
    allowed_prefixes = ["db.", "db.getCollection(", "list(db.",  "len(db."]
    return any(query.strip().startswith(prefix) for prefix in allowed_prefixes)
