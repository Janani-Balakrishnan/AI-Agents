### insert_dummy_data.py
from pymongo import MongoClient
from bson import ObjectId
import random
from datetime import datetime, timedelta

client = MongoClient("mongodb://localhost:27017/")
db = client["fleetwise"]

# Clear existing data
db.fleets.delete_many({})
db.tripplanners.delete_many({})

# Insert 10 dummy fleets
fleets = []
for i in range(10):
    fleet = {
        "_id": ObjectId(),
        "short_name": f"Fleet {chr(65 + i)}",
        "number_plate": f"TN0{i+1:02d}XY{1000 + i}"
    }
    fleets.append(fleet)
db.fleets.insert_many(fleets)

# Sample drivers and customers
drivers = ["Arun Kumar", "Priya R", "Suresh M", "Divya S", "Karthik N"]
customers = ["Aavin Depot 1", "Retail Shop 23", "Wholesale Buyer X", "School Canteen", "Hospital Supply"]

# Trip type prefixes
trip_types = ["D", "S"]

# Diverse materials
delivery_items = ["Milk", "Paneer", "Butter", "Ghee"]
sale_items = ["Curd", "Lassi", "Yogurt", "Buttermilk"]

# Insert 20 dummy trips
trips = []
start_date = datetime(2025, 5, 20)

for i in range(20):
    trip_type = random.choice(trip_types)
    trip_date = start_date + timedelta(days=i)
    trip_no = f"{trip_type}#{trip_date.strftime('%Y%m%d')} - {i+1:04d}"
    fleet = random.choice(fleets)
    driver = random.choice(drivers)
    customer = random.choice(customers)

    delivery_order = [
        {"item": random.choice(delivery_items), "qty": random.randint(30, 150)}
        for _ in range(random.randint(1, 2))
    ] if trip_type == "D" else []

    sale_order = [
        {"item": random.choice(sale_items), "qty": random.randint(10, 100)}
        for _ in range(random.randint(1, 2))
    ] if trip_type == "S" else []

    trip = {
        "trip_no": trip_no,
        "trip_schedule": {"date": trip_date.strftime('%Y-%m-%d')},
        "status": random.randint(0, 5),
        "genericdata": {
            "fleet": fleet["_id"],
            "driver_name": driver,
            "customer_name": customer
        },
        "odometer_start": random.randint(5000, 15000),
        "odometer_end": random.randint(15001, 25000),
        "orders": {
            "delivery": delivery_order,
            "sale": sale_order
        }
    }
    trips.append(trip)

db.tripplanners.insert_many(trips)

print("✅ Inserted 10 fleets and 20 enriched trips with drivers, customers, and diverse items.")
