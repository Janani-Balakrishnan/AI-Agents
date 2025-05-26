import streamlit as st
import speech_recognition as sr
from llm_response_tools import generate_natural_response

# Set up the Streamlit app
st.set_page_config(page_title="FleetWise AI", layout="wide")
st.title("🚚 FleetWise AI")
st.write("🔹 Your intelligent logistics buddy — ask away: trips and fleets!")

#  Initialize Chat History
if "messages" not in st.session_state:
    st.session_state["messages"] = []

#  Sidebar - Styled Voice Input
with st.sidebar:
    st.markdown("## 🎙️ Voice Assistant")
    st.markdown("Use your microphone to ask your question.")

    # Language selector
    language_option = st.selectbox("🌐 Choose Language", ["English", "Tamil"])
    language_code = "en-IN" if language_option == "English" else "ta-IN"

    if st.button("🎤 Speak Now"):
        recognizer = sr.Recognizer()
        microphone = sr.Microphone()

        with st.spinner("🎧 Listening..."):
            with microphone as source:
                recognizer.adjust_for_ambient_noise(source)
                audio = recognizer.listen(source)

        try:
            speech_text = recognizer.recognize_google(audio, language=language_code)
            st.success(f"📝 Recognized: {speech_text}")
            st.session_state["voice_input"] = speech_text
        except sr.UnknownValueError:
            st.error("❌ Sorry, I couldn't understand the audio.")
        except sr.RequestError:
            st.error("⚠️ Could not request results from Google Speech Recognition.")

#  Display Chat History
for msg in st.session_state["messages"]:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

#  Use either typed or spoken input
user_query = st.chat_input("💬 Type your question here...", key="chatbox") or st.session_state.pop("voice_input", None)

if user_query:
    st.session_state["messages"].append({"role": "user", "content": user_query})
    with st.chat_message("user"):
        st.markdown(user_query)

    with st.spinner("🤖 Thinking..."):
        recent_messages = st.session_state["messages"][-5:]
        history_context = "\n".join(
            f"{'User' if m['role'] == 'user' else 'Assistant'}: {m['content']}" for m in recent_messages
        )
        response = generate_natural_response(user_query, history_context)

    st.session_state["messages"].append({"role": "assistant", "content": response["natural_response"]})
    with st.chat_message("assistant"):
        st.markdown(response['natural_response'])

#  Reset Chat Button
st.markdown("---")
if st.button("🔄 Reset Chat"):
    st.session_state["messages"] = []
    st.rerun()
