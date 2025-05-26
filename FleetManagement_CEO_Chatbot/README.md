#Fleet Management Chatbot 
It is an intelligent chatbot built for Fleet Management CEOs to interact with their fleet data stored in MongoDB. This chatbot enables natural language queries like:

"Show all delivery trips from yesterday."

"can you share the breakdown of all the trips by status."

"List all the Fleet that are malfunctioned"

The chatbot translates natural language into MongoDB queries and retrieves meaningful, structured responses. It’s implemented without LangChain, offering a lightweight and modular architecture.

🚚 Key Features
✅ Conversational querying of MongoDB collections
✅ Intelligent parsing of trip types, statuses, and dates
✅ MongoDB $lookup support for relational-like data retrieval
✅ Natural language to MongoDB query generation using LLM (via Gemini API)
✅ Streamlit UI for user interaction
✅ BSON-to-JSON conversion for human-readable outputs
✅ Modular codebase for easy extension
✅ Dummy data generation script for local testing

⚙️ Setup Instructions
1️⃣ Install Dependencies
Create a virtual environment and install the requirements:

pip install -r requirements.txt

2️⃣ Set Up Environment Variables
Create a .env file in the project root:

MONGODB_URI=mongodb://localhost:27017
GEMINI_API_KEY=your_gemini_api_key_here

3️⃣ Insert Dummy Data
Before testing the chatbot, insert dummy data into your local MongoDB:

python insert_dummy_data.py

This script will create collections like tripplanners and add sample records.

4️⃣ Run the Chatbot
Launch the Streamlit app:
streamlit run app.py
