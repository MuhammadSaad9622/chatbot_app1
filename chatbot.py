from openai import OpenAI


import streamlit as st
client = OpenAI(api_key=st.secrets["OPENAI_API_KEY"])
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





gmaps = googlemaps.Client(key=st.secrets["GOOGLE_PLACES_API_KEY"])
twilio_client = TwilioClient(st.secrets["TWILIO_ACCOUNT_SID"], st.secrets["TWILIO_AUTH_TOKEN"])

# Streamlit UI
st.title("HART - Your Experience & Restaurant Recommender Chatbot")

# Initialize chat history and user info
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'user_info' not in st.session_state:
    st.session_state.user_info = {}
if 'step' not in st.session_state:
    st.session_state.step = 0  # Track the current step in the flow
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
        from_email="info@mydatejar.com",  # Update this to your actual email address
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
    # Validate phone number (E.164 format)
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

    # Proceed with geocoding and fetching places as before
    geocode_result = gmaps.geocode(location)
    if not geocode_result:
        return "Invalid location provided. Please try again.", "No address available."

    location_latlng = geocode_result[0]['geometry']['location']

    # Fetch experience using the archetype query
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
    
    # Getting latitude and longitude for restaurants search
    location_latlng = geocode_result[0]['geometry']['location']
    
    # Fetch results from Google Places API for restaurants near the location
    places_result = gmaps.places(query, location=f"{location_latlng['lat']},{location_latlng['lng']}", radius=8000)
    
    # Prepare restaurant results in list form
    restaurants = []
    for place in places_result.get('results', [])[:3]:  # Limit to 3 restaurants
        name = place.get('name', 'No name found.')
        address = place.get('formatted_address', 'No address found.')
        rating = place.get('rating', 'N/A')
        if rating >= 4.0:
            restaurants.append(f"- {name} - Rating: {rating}\n  Location: {address}")
    
    # Return the restaurant list or a default message
    return restaurants if restaurants else ["No restaurants found nearby."]


# Display chat history above input field
st.write("### Chat History")
for chat in st.session_state.chat_history:
    if chat["role"] == "user":
        st.write(f"You: {chat['content']}")
    else:
        st.write(f"HART: {chat['content']}")

# Handle flow based on the current step 
if st.session_state.step == 0:
    # Welcome & Name Input
    user_name = st.text_input("Hi, I'm HART! What's your name? Let's find your next great experience!", "")
    
    if st.button("Submit Name") or user_name:
        if user_name.strip() == "":
            st.warning("Please enter your name before proceeding.")
        else:
            first_name = user_name.split()[0]
            st.session_state.user_info['name'] = user_name
            st.session_state.chat_history.append({"role": "user", "content": user_name})
            st.session_state.chat_history.append({"role": "assistant", "content": f"Awesome, {first_name}! What type of experience are you in the mood for today?"})
            st.session_state.step += 1


# Step 1: Experience Archetype Selection
elif st.session_state.step == 1:
    # List of available archetypes
    archetypes = ["Thrill Seeking", "Creative & Artsy", "Super Chill & Leisurely", "Foodie", "Live Entertainment & Shows"]

    # Ensure the selectbox dynamically captures the user's selection
    user_archetype = st.selectbox("What type of experience are you in the mood for today?", archetypes, index=archetypes.index(st.session_state.user_info.get('archetype', archetypes[0])))

    # Only proceed if the user selects an archetype and clicks the submit button
    if st.button("Submit Archetype"):
        if user_archetype.strip() == "":
            st.warning("Please enter your Archetype before proceeding.")
            
        else:    
            
            st.session_state.user_info['archetype'] = user_archetype
            st.session_state.chat_history.append({"role": "user", "content": user_archetype})

            # Fetch a description for the selected experience type using OpenAI
            description = generate_human_like_response(f"Describe a {user_archetype} experience in 3-4 lines.")
            st.session_state.chat_history.append({"role": "assistant", "content": description})

            # Ask for the user's location next
            st.session_state.chat_history.append({"role": "assistant", "content": "Where are you located? Please enter your city and state (e.g., New York, NY)."})
            st.session_state.step += 1


elif st.session_state.step == 2:
    user_location = st.text_input("Where are you located? Just your city and state will do!", "")
    if st.button("Submit Location") or user_location:
        if user_location.strip() == "":
            st.warning("Please enter your location before proceeding.")
        else:
            st.session_state.user_info['location'] = user_location
            st.session_state.chat_history.append({"role": "user", "content": user_location})

            # Fetch dynamic recommendations from Google Places API
            experience_name, experience_location = fetch_experience(st.session_state.user_info['location'], st.session_state.user_info['archetype'])

            st.session_state.experience = f"Here is an experience you might love:\n\n- {experience_name}\nLocation: {experience_location}"

            st.session_state.chat_history.append({"role": "assistant", "content": st.session_state.experience})
            st.session_state.step += 1


# Step 3 - Ask if the user likes the suggestion (radio buttons without pre-selection)
elif st.session_state.step == 3:
    st.write(st.session_state.experience)
    
    # Initialize an empty user_response to avoid default selection
    user_response = st.radio("Do you like this suggestion?", ("", "Yes", "No"), index=0)  # Empty string acts as no selection

    # Proceed based on user's explicit choice
    if st.button("Submit Response") or user_response != "":
        
            if user_response == "Yes":
                st.session_state.chat_history.append({"role": "user", "content": "Yes, I like the suggestion."})
                st.session_state.chat_history.append({"role": "assistant", "content": "Great! Would you like a restaurant recommendation nearby?"})
                st.session_state.step += 1
            elif user_response == "No":
                st.session_state.chat_history.append({"role": "user", "content": "No, I don't like the suggestion."})
                st.session_state.chat_history.append({"role": "assistant", "content": "No problem! I can find something else for you."})
                st.session_state.step = 1  # Go back to step 1 to choose a new archetype
    elif user_response == "":
        st.warning("Please select an option to continue.")  # Show a warning if no option is selected

elif st.session_state.step == 4:
    # Step 4 - Restaurant Recommendation
    if st.button("Get Restaurant Recommendations"):
        with st.spinner("Fetching restaurant recommendations..."):
            # Pass both location and archetype to the fetch_restaurants function
            st.session_state.restaurants = fetch_restaurants(st.session_state.user_info['location'], st.session_state.user_info['archetype'])
            st.session_state.restaurant_message = "Here are some restaurant recommendations near your experience:\n\n" + "\n".join(st.session_state.restaurants)
            st.session_state.chat_history.append({"role": "assistant", "content": st.session_state.restaurant_message})

            # Show restaurant recommendations
            st.write(st.session_state.restaurant_message)


    # Option to send recommendations via email
    user_email = st.text_input("Enter your email to receive recommendations", "")
    if st.button("Send Email") and user_email:
        email_subject = "Your Experience & Restaurant Recommendations"
        email_content = f"<p>{st.session_state.experience}</p>"
        if st.session_state.restaurants:
            email_content += f"<p>{st.session_state.restaurant_message}</p>"
        send_email(user_email, email_subject, email_content)

    # # Option to send recommendations via SMS
    # user_phone = st.text_input("Enter your phone number to receive SMS recommendations", "")
    # if st.button("Send SMS") and user_phone:
    #     sms_message = st.session_state.experience + "\n\n" + "\n".join(st.session_state.restaurants)
    #     send_sms(user_phone, sms_message)

# Reset the chat history if the user wants to start over
if st.button("Start Over"):
    st.session_state.clear()
