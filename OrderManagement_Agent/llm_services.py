import pandas as pd
import json
from datetime import datetime
import streamlit as st
from rapidfuzz import process,fuzz
import google.generativeai as genai
from dotenv import load_dotenv
import os
import re
import time

# === Load environment variables ===
load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# === Gemini Setup ===
genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel("Use your model as per your requirement")

# Load material sheet
def load_material_sheet():
    df_material = pd.read_excel("materials.xlsx", sheet_name=None)
    materials = df_material[list(df_material.keys())[0]]
    customers = df_material[list(df_material.keys())[1]]
    materials.columns = materials.columns.str.strip().str.lower()
    customers.columns = customers.columns.str.strip().str.lower()
    return materials, customers

# === Gemini Parsing Function ===
def parse_with_gemini(message, materials, customers):
    material_list = [
        {"description": row['description'], "uom": row['uom']} for _, row in materials.iterrows()
    ]
    
    # Create customer list
    customer_list = [
        {"customer_name": row['cd_name'], "sales_area": row['ad_billing_address_city']} for _, row in customers.iterrows()
    ]
    
    today = datetime.today().strftime('%d/%m/%Y')

    prompt = f"""
    You are an AI assistant for order management.
    *Give your prompt to get customized response*
    WhatsApp message:
    {message}

    Product material list:
    {json.dumps(material_list, indent=2)}

    Customer list:
    {json.dumps(customer_list, indent=2)}

    Return the response as text, not JSON.
    """

    try:
        response = model.generate_content(prompt)
        raw_text = getattr(response, 'text', '') or getattr(response, 'parts', [{}])[0].get('text', '')

        if not raw_text.strip():
            raise ValueError("Empty response from Gemini")

        parsed = extract_order_details_from_text(raw_text)
        print(parsed)
        # Attempt to extract Sales Area from Gemini raw text
        if "sales_area" not in parsed or not parsed["sales_area"]:
            sales_area = extract_sales_area_from_text(raw_text)
            if sales_area:
                parsed["sales_area"] = sales_area
            else:
                # Match customer name and get sales area if not found in raw text
                customer_names = [customer['customer_name'] for customer in customer_list]
                match, score = process.extractOne(parsed["customer_name"], customer_names)
                if score > 70:
                    matched_customer = next(customer for customer in customer_list if customer['customer_name'] == match)
                    parsed["sales_area"] = matched_customer["sales_area"]
                else:
                    parsed["sales_area"] = "Unknown"

        return parsed
    except Exception as e:
        st.warning(f"Gemini parsing failed: {e}")
        return None


def extract_order_details_from_text(text):
    lines = text.splitlines()
    parsed = {
        "customer_name": "",
        "expected_delivery": "",
        "ordered_date": "",
        "sales_area": "",
        "items": []
    }

    current_item = {}
    for line in lines:
        line = line.strip()

        # Extract customer name
        if line.lower().startswith("customer name"):
            parsed["customer_name"] = line.split(":", 1)[1].strip()

        # Extract expected delivery date
        elif line.lower().startswith("expected delivery"):
            parsed["expected_delivery"] = line.split(":", 1)[1].strip()

        # Extract ordered date
        elif line.lower().startswith("ordered date"):
            parsed["ordered_date"] = line.split(":", 1)[1].strip()

        # Extract sales area (assuming it's the next line after the customer name)
        elif line.lower().startswith("sales area"):
            parsed["sales_area"] = line.split(":", 1)[1].strip()

        # Parse items - assuming format "- item <name>: <quantity> <unit>"
        elif line.lower().startswith("- item"):
            if current_item:
                parsed["items"].append(current_item)
                current_item = {}

            current_item["item"] = line.split(":", 1)[1].strip()

        # Extract quantity
        elif line.lower().startswith("quantity"):
            qty_text = line.split(":", 1)[1].strip()
            try:
                qty = float(qty_text)
                if qty < 0 or qty == 0.5:
                    qty = 1  # Treat invalid or small quantities as 1
            except:
                qty = 0  # If quantity is invalid or missing, assume 0

            current_item["quantity"] = qty

        # Extract UOM (unit of measure)
        elif line.lower().startswith("uom"):
            current_item["uom"] = line.split(":", 1)[1].strip()

    # Append the last item if it exists
    if current_item:
        parsed["items"].append(current_item)

    return parsed

# === Extract Sales Area ===
def extract_sales_area_from_text(text):
    # Try to find a line that explicitly mentions "sales area"
    sales_area_keywords = ['sales area', 'billing city', 'delivery area', 'city']
    lines = text.splitlines()

    for line in lines:
        line = line.strip().lower()
        if any(keyword in line for keyword in sales_area_keywords):
            # Simple extraction of city after colon (assumes the format "Sales Area: City Name")
            if ":" in line:
                return line.split(":", 1)[1].strip()
    return None

#Parse rough items from the WhatsApp text manually if Gemini fails.
def parse_raw_items_from_message(message):

    items = []

    # Split the message into lines
    lines = message.splitlines()

    # Updated pattern to match "Item Name - quantity", "Item Name = quantity", or "Item Name : quantity"
    pattern = re.compile(r"(.+?)\s*[-=:]\s*([\d.]+)")

    for line in lines:
        line = line.strip()
        if not line:
            continue  # Skip empty lines

        match = pattern.search(line)
        if match:
            item_name = match.group(1).strip()
            quantity = float(match.group(2).strip())

            items.append({
                "item": item_name,
                "quantity": quantity,
                "uom": ""  # UOM can be blank initially, will get filled during fallback_match
            })

    return items


# Helper: Clean and normalize text
def clean_text(text):
    if not isinstance(text, str):
        return ""
    text = text.lower()
    text = re.sub(r'[^a-z0-9\s]', '', text)  # Remove non-alphanumeric except space
    text = re.sub(r'\s+', ' ', text).strip()  # Remove extra spaces
    return text

# === Fallback Matching with Cleaning ===
def fallback_match_items(items, materials):
    matched = []
    
    # Pre-clean material descriptions once
    materials = materials.copy()
    materials['clean_description'] = materials['description'].apply(clean_text)
    
    for item in items:
        item_name = item.get('item', '').strip()
        quantity = item.get('quantity', 0)
        uom = item.get('uom', '').strip()

        if not item_name:
            continue
        
        if not isinstance(quantity, (int, float)):
            quantity = 0
        
        if quantity <= 0:
            continue

        # Clean the customer item name
        cleaned_item_name = clean_text(item_name)

        best_match = None
        best_score = 0

        for _, mat in materials.iterrows():
            score = fuzz.token_sort_ratio(cleaned_item_name, mat['clean_description'])
            if score > best_score:
                best_score = score
                best_match = mat

        # Threshold can be tuned: (e.g., 75 or 80)
        if best_match is not None and best_score >= 80:
            matched.append({
                "item": best_match['description'],
                "quantity": quantity,
                "uom": best_match['uom'] or uom
            })
        else:
            # If no good match, keep original
            matched.append({
                "item": item_name,
                "quantity": quantity,
                "uom": uom
            })
    
    return matched
