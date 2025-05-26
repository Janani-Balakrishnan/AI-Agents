import re
import json
from datetime import datetime
from bson import ObjectId
from pymongo import MongoClient

# MongoDB connection
def get_db_connection():
    client = MongoClient("mongodb://localhost:27017/")
    db = client["DRS"]
    return db

# Get database schema

def convert_bson(doc):
    """Recursively convert MongoDB BSON types to JSON-serializable formats"""
    if isinstance(doc, dict):
        return {k: convert_bson(v) for k, v in doc.items()}
    elif isinstance(doc, list):
        return [convert_bson(i) for i in doc]
    elif isinstance(doc, ObjectId):
        return str(doc)  # Convert ObjectId to string
    elif isinstance(doc, datetime):
        return doc.isoformat()  # Convert datetime to ISO format string
    else:
        return doc


def get_db_schema():
    db = get_db_connection()
    collections = db.list_collection_names()
    schema = {}

    for collection_name in collections:

        # Special handling for tripplanners using lookup
        if collection_name == "tripplanners":
            pipeline = [
                {"$limit": 1},
                {
                    "$lookup": {
                        "from": "fleets",
                        "localField": "genericdata.fleet",
                        "foreignField": "_id",
                        "as": "fleet_info"
                    }
                },
                {
                    "$lookup": {
                        "from": "users",
                        "localField": "genericdata.driver",
                        "foreignField": "_id",
                        "as": "driver_info"
                    }
                }
            ]
            sample_docs = list(db[collection_name].aggregate(pipeline))
            #print("sampledocs:", sample_docs)
            sample_doc = sample_docs[0] if sample_docs else None
        else:
            sample_doc = db[collection_name].find_one()

        if sample_doc:
            schema[collection_name] = []
            field_count = 0

            def process_field(field, value, parent=""):
                nonlocal field_count
                if field_count >= 20:
                    return

                full_field = f"{parent}.{field}" if parent else field
                field_type = type(value).__name__

                # Handle ObjectId fields
                if isinstance(value, ObjectId):
                    referenced_collection = find_referenced_collection(db, field)
                    schema[collection_name].append({
                        "name": full_field,
                        "type": "ObjectId",
                        "references": referenced_collection
                    })
                    field_count += 1
                # Recurse into dicts
                elif isinstance(value, dict):
                    for sub_field, sub_value in value.items():
                        process_field(sub_field, sub_value, parent=full_field)
                # Recurse into array of dicts (like from $lookup)
                elif isinstance(value, list) and len(value) > 0 and isinstance(value[0], dict):
                    for sub_field, sub_value in value[0].items():
                        process_field(sub_field, sub_value, parent=full_field)
                else:
                    schema[collection_name].append({
                        "name": full_field,
                        "type": field_type
                    })
                    field_count += 1

            for field, value in sample_doc.items():
                process_field(field, value)

    return schema



def find_referenced_collection(db, field_name):
    """Check which collection has this field as _id"""
    for collection in db.list_collection_names():
        if db[collection].find_one({field_name: {"$exists": True}}):
            #print(collection)
            return collection
    return None

# 🔹 Status Mapping for `tripplanners`
STATUS_MAPPING = {
    "assigned": 0,
    "scheduled": 1,
    "ongoing": 2,
    "rejected": 3,
    "cancelled": 4,
    "completed": 5,
    "verified": 6,
    "interrupted": 7,
    "malfunctioned": 8,
    "recalled": 9
}

def map_status_in_query(user_query):
    """Replace status names with corresponding numbers in the query and ensure correct filtering."""
    for status_name, status_value in STATUS_MAPPING.items():
        # Use regex to replace exact words only (case-insensitive)
        pattern = rf"\b{status_name}\b"
        if re.search(pattern, user_query, re.IGNORECASE):
            # Instead of just replacing, ensure the query filters by status
            if "status" not in user_query.lower():
                user_query += f' with status {status_value}'  # Append status filter if missing
            else:
                user_query = re.sub(pattern, str(status_value), user_query, flags=re.IGNORECASE)
    return user_query
#Extracts the first valid MongoDB query from the LLM response.
def extract_mongo_query(llm_response):
        
    # Step 1: Remove Markdown code blocks (```python, ```json, etc.)
    code_blocks = re.findall(r'```(?:python|json|plaintext)?(.*?)```', llm_response, re.DOTALL)

    if code_blocks:
        # Step 2: Extract first valid query block
        mongo_query = code_blocks[0].strip()
    else:
        # If no Markdown blocks found, assume raw query in text
        lines = llm_response.split("\n")
        mongo_query = next((line.strip() for line in lines if "db." in line), None)

    if not mongo_query:
        return "Error: No valid MongoDB query found."

    return mongo_query

def format_query_for_eval(query_str):
    """Fix common LLM formatting issues in MongoDB queries."""
    # Ensure field names are in quotes (e.g., { status: 1 } → { "status": 1 })
    query_str = re.sub(r"(\{)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:", r'\1 "\2":', query_str)
    return query_str.strip()
 
#Ensures that the generated MongoDB query does not contain contract-based filtering unless explicitly requested by the user.
def clean_generated_query(mongo_query, user_query):
    """Ensures contract filtering is retained when explicitly required."""

    # Convert to lowercase for case-insensitive matching
    user_query_lower = user_query.lower()

    # If user asks about contract fleets, DO NOT REMOVE contract filtering
    if "contract fleet" in user_query_lower or "contract fleets" in user_query_lower:
        return mongo_query  # Keep as is!

    # Otherwise, remove contract filter if mistakenly included
    mongo_query = re.sub(r',?\s*"contracter_details\.contract_number":\s*{\s*\$ne:\s*""\s*}', '', mongo_query)

    return mongo_query