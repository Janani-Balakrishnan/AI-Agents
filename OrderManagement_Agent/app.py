# === Streamlit UI ===
import streamlit as st
import time
from llm_services import load_material_sheet,parse_with_gemini,parse_raw_items_from_message, fallback_match_items

st.title("📦 Order Management Bot (POC)")

material_df, customer_df = load_material_sheet()
whatsapp_input = st.text_area("WhatsApp Order Message:")

# Process Order button
if st.button("Process Order") and whatsapp_input:
    parsed_data = parse_with_gemini(whatsapp_input, material_df, customer_df)
    if parsed_data:
        st.session_state["parsed_data"] = parsed_data
         # 🧹 -- Fallback Condition --
        if not parsed_data.get('items') or len(parsed_data['items']) == 0:
            st.warning("⚠️ Gemini didn't parse items properly. Using fallback matching...")
            raw_items = parse_raw_items_from_message(whatsapp_input)
            parsed_data['items'] = fallback_match_items(raw_items, material_df)
        else:
            # Extra safety: fallback match the Gemini extracted items
            parsed_data['items'] = fallback_match_items(parsed_data['items'], material_df)


        # Save matched items
        st.session_state["final_items"] = parsed_data['items']

# Ensure session state initialized
if "final_items" not in st.session_state:
    st.session_state["final_items"] = []
if "parsed_data" not in st.session_state:
    st.session_state["parsed_data"] = {}
# --- Only if parsed_data is available ---
if st.session_state["parsed_data"]:
    parsed_data = st.session_state["parsed_data"]

    st.subheader("🧾 Order Summary")
    parsed_data["customer_name"] = st.text_input("Customer Name", parsed_data.get("customer_name", ""))
    parsed_data["sales_area"] = st.text_input("Sales Area", parsed_data.get("sales_area", ""))
    st.markdown(f"**Expected Delivery Date:** {parsed_data.get('expected_delivery', '')}")
    st.markdown(f"**Ordered Date:** {parsed_data.get('ordered_date', '')}")

    st.markdown("**Items:**")

    # --- 🧹 Handle adding new item ---
    if st.button("➕ Add Item"):
        st.session_state["final_items"].append({
            "item": "",
            "quantity": 0.0,
            "uom": ""
        })
    raw_items = parse_raw_items_from_message(whatsapp_input)
    # Fallback match
    parsed_data['items'] = fallback_match_items(raw_items, material_df)

    # Render Header Row
    header_cols = st.columns([4, 2, 2, 1])
    header_cols[0].markdown("**Item**")
    header_cols[1].markdown("**Quantity**")
    header_cols[2].markdown("**UOM**")
    header_cols[3].markdown("**Delete**")

    # Iterate final items
    new_final_items = []
    delete_triggered = False
    item_to_delete_idx = None

    for idx, item in enumerate(st.session_state["final_items"]):
        quantity = item.get('quantity', 0)
        if quantity <= 0:
            continue

        col1, col2, col3, col4 = st.columns([4, 2, 2, 1])
        with col1:
            item_name = st.text_input("", item['item'], key=f"name_{idx}", placeholder="Enter item name")
        with col2:
            qty = st.number_input("", min_value=0.0, value=float(quantity), key=f"qty_{idx}")
        with col3:
            uom = st.text_input("", item['uom'], key=f"uom_{idx}", placeholder="e.g., kg, pcs")
        with col4:
            delete = st.button("🗑️", key=f"delete_{idx}")

        if delete:
            delete_triggered = True
            item_to_delete_idx = idx
            break

        new_final_items.append({
            "item": item_name,
            "quantity": qty,
            "uom": uom
        })

    # --- After loop ---
    if delete_triggered and item_to_delete_idx is not None:
        st.session_state["final_items"].pop(item_to_delete_idx)
        with st.spinner('Removing item...'):
            time.sleep(0.3)
        st.success(f"Item {item_to_delete_idx+1} deleted successfully ✅", icon="✅")
        time.sleep(0.5)
        st.rerun()
    else:
        st.session_state["final_items"] = new_final_items

    # --- If no items ---
    if not st.session_state["final_items"]:
        st.info("🛒 No items to display. Please add items to create an order!")

    # --- Create Order ---
    if st.button("Create Order"):
        order_json = {
            "customer_name": parsed_data.get("customer_name", ""),
            "sales_area": parsed_data.get("sales_area", ""),
            "expected_delivery": parsed_data.get("expected_delivery", ""),
            "ordered_date": parsed_data.get("ordered_date", ""),
            "items": st.session_state["final_items"]
        }
        st.success("Order created successfully!")
        st.json(order_json)