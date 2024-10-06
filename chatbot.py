from openai import OpenAI
import streamlit as st
import googlemaps
from twilio.rest import Client as TwilioClient
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail
import os
import ssl
import re 

# Disable SSL certificate validation (temporary fix, not recommended for production)
ssl._create_default_https_context = ssl._create_unverified_context

# Initialize API keys
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
gmaps = googlemaps.Client(key=st.secrets["GOOGLE_PLACES_API_KEY"])
twilio_client = TwilioClient(st.secrets["TWILIO_ACCOUNT_SID"], st.secrets["TWILIO_AUTH_TOKEN"])

# Load CSS styles
def load_css():
    with open("css/styles.css") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

# Streamlit UI
load_css()  # Load CSS styles
st.title("HART - Your Experience & Restaurant Recommender Chatbot")

# Initialize chat history and user info
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}
if 'step' not in st.session_state:
    st.session_state.step = 0
if 'experience' not in st.session_state:
    st.session_state.experience = ""
if 'restaurant_message' not in st.session_state:
    st.session_state.restaurant_message = ""
if 'restaurants' not in st.session_state:
    st.session_state.restaurants = []

# Function to generate chatbot response with context
def generate_human_like_response(user_message):
    messages = [{"role": "system", "content": "You are a helpful and engaging chatbot."}]
    messages.extend(st.session_state.chat_history)
    messages.append({"role": "user", "content": user_message})

    try:
        response = client.chat.completions.create(model="gpt-3.5-turbo", messages=messages, max_tokens=150, temperature=0.8)
        return response.choices[0].message.content.strip()
    except Exception as e:
        st.error(f"Error generating response: {str(e)}")
        return "I'm sorry, something went wrong. Please try again later."

# Function to send email using SendGrid
def send_email(to_email, subject, content):
    message = Mail(
        from_email="info@mydatejar.com",
        to_emails=to_email,
        subject=subject,
        html_content=content
    )
    try:
        sg = SendGridAPIClient(st.secrets["SENDGRID_API_KEY"])
        response = sg.send(message)
        st.success(f"Email sent!")
    except Exception as e:
        st.error(f"Error sending email: {str(e)}")

# Function to send SMS using Twilio
def send_sms(to_phone, message):
    if not re.match(r'^\+\d{1,3}\d{9,15}$', to_phone):
        st.error("Error: Phone number must be in E.164 format, e.g., +12345678901")
        return

    try:
        twilio_client.messages.create(
            body=message,
            from_="+18049245738",  # Your Twilio number
            to=to_phone
        )
        st.success(f"SMS sent successfully to {to_phone}")
    except Exception as e:
        st.error(f"Error sending SMS: {str(e)}")

# Function to fetch experiences dynamically based on user-selected archetype and location
def fetch_experience(location, archetype):
    query_map = {
        "Thrill Seeking": "amusement park",
        "Creative & Artsy": "art gallery",
        "Super Chill & Leisurely": "spa",
        "Foodie": "restaurant",
        "Live Entertainment & Shows": "live music"
    }

    query = query_map.get(archetype, "")

    geocode_result = gmaps.geocode(location)
    if not geocode_result:
        return "Invalid location provided. Please try again.", "No address available."

    location_latlng = geocode_result[0]['geometry']['location']
    places_result = gmaps.places(query, location=f"{location_latlng['lat']},{location_latlng['lng']}", radius=5000)

    if places_result.get('results'):
        experience_name = places_result['results'][0].get('name', 'No experience found.')
        experience_address = places_result['results'][0].get('formatted_address', 'No address found.')
        return experience_name, experience_address
    else:
        return "No experiences found.", "Unknown location"

# Function to fetch restaurant recommendations near the experience
def fetch_restaurants(location, archetype):
    query_map = {
        "Thrill Seeking": "fast food",
        "Creative & Artsy": "cafe",
        "Super Chill & Leisurely": "fine dining",
        "Foodie": "restaurant",
        "Live Entertainment & Shows": "pub"
    }

    query = query_map.get(archetype, "restaurant")
    
    geocode_result = gmaps.geocode(location)
    if not geocode_result:
        return ["Invalid location provided. Please try again."]
    
    location_latlng = geocode_result[0]['geometry']['location']
    places_result = gmaps.places(query, location=f"{location_latlng['lat']},{location_latlng['lng']}", radius=8000)
    
    restaurants = []
    for place in places_result.get('results', [])[:3]:
        name = place.get('name', 'No name found.')
        address = place.get('formatted_address', 'No address found.')
        rating = place.get('rating', 'N/A')
        if rating >= 4.0:
            restaurants.append(f"- {name} - Rating: {rating}\n  Location: {address}")
    
    return restaurants if restaurants else ["No restaurants found nearby."]

# Display chat history above input field
st.write("### Chat History")
st.markdown('<div class="chat-history">', unsafe_allow_html=True)
for chat in st.session_state.chat_history:
    if chat["role"] == "user":
        st.markdown(f'<p class="user-message">You: {chat["content"]}</p>', unsafe_allow_html=True)
    else:
        st.markdown(f'<p class="assistant-message">HART: {chat["content"]}</p>', unsafe_allow_html=True)
st.markdown('</div>', unsafe_allow_html=True)

# Handle flow based on the current step 
if st.session_state.step == 0:
    user_name = st.text_input("Hi, I'm HART! What's your name? Let's find your next great experience!", "")
    
    if st.button("Submit Name") or user_name:
        first_name = user_name.split()[0]
        st.session_state.user_info['name'] = user_name
        st.session_state.chat_history.append({"role": "user", "content": user_name})
        st.session_state.chat_history.append({"role": "assistant", "content": f"Awesome, {first_name}! What type of experience are you in the mood for today?"})
        st.session_state.step += 1

elif st.session_state.step == 1:
    archetypes = ["Thrill Seeking", "Creative & Artsy", "Super Chill & Leisurely", "Foodie", "Live Entertainment & Shows"]
    selected_archetype = st.selectbox("Select your preferred archetype", archetypes)
    
    if st.button("Submit Archetype"):
        st.session_state.chat_history.append({"role": "user", "content": selected_archetype})
        experience_name, experience_address = fetch_experience(st.session_state.user_info['location'], selected_archetype)
        st.session_state.experience = experience_name
        st.session_state.chat_history.append({"role": "assistant", "content": f"I found a great experience for you: {experience_name}, located at {experience_address}."})
        st.session_state.step += 1

elif st.session_state.step == 2:
    st.write(f"**Recommended Experience:** {st.session_state.experience}")
    
    if st.button("Show Restaurants Nearby"):
        restaurants = fetch_restaurants(st.session_state.user_info['location'], selected_archetype)
        st.session_state.restaurants = restaurants
        st.session_state.chat_history.append({"role": "assistant", "content": "Here are some restaurants near your experience:"})
        for restaurant in restaurants:
            st.session_state.chat_history.append({"role": "assistant", "content": restaurant})
        st.session_state.step += 1

# Input field for chat
user_input = st.text_input("Type your message:")
if st.button("Send"):
    st.session_state.chat_history.append({"role": "user", "content": user_input})
    response = generate_human_like_response(user_input)
    st.session_state.chat_history.append({"role": "assistant", "content": response})

# Additional functionalities can be added as needed
