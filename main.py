import os
from dotenv import load_dotenv
import glob
import streamlit as st
import streamlit_authenticator as stauth
from streamlit_authenticator import LoginError
from streamlit_image_select import image_select
import yaml
from yaml.loader import SafeLoader
from utils import icon
from PIL import Image
import io
import hashlib
from comfy import get_portrait, get_portrait_random

def generate_unique_id(email: str) -> str:
    # Hash the email to create a unique, anonymized identifier
    email_hash = hashlib.sha256(email.encode()).hexdigest()
    return email_hash


########################### Create necessary dirs ###########################
os.makedirs("./user_uploads/", exist_ok=True)
os.makedirs("./output/", exist_ok=True)


########################### UI configurations ###########################
st.set_page_config(page_title="AI portrait generator",
                   page_icon=":camera_with_flash:",
                   layout="centered",
                   menu_items={})


def configure_sidebar() -> None:
    """
    Setup and display the sidebar elements.

    This function configures the sidebar of the Streamlit application, 
    including the form for user inputs and the resources section.
    """
    with st.sidebar:
        with st.form("my_form"):
            st.info("**Yo! Here's your control panel! ↓**", icon="👋🏾")
            with st.expander(":orange[**Refine your settings here**]"):
                resemblance = st.slider(
                    "Resemblance strength", 
                    value=1.2, min_value=0.8, max_value=2., step=0.1, 
                    help="The bigger the value, the more your identity should be preserved during generation. High values may cause the restuls to appear less natural.")
            prompt = st.text_area(
                ":orange[**Adjust positive prompt: ✍🏾**]",
                value="headshot, dressed casually, soft natural lighting, wearing suit and tie, urban city background",
                help="This is a positive prompt, basically type what you want to see in the generated image")
            negative_prompt = st.text_area(":orange[**Adjust negative prompt: 🙅🏽‍♂️**]",
                                           value="grinning, looking away",
                                           help="This is a negative prompt, basically type what you DON'T want to see in the generated image")

            # The Big Red "Submit" Button!
            submitted = st.form_submit_button(
                "Submit", type="primary", use_container_width=True)

        # Credits and resources
        st.markdown(
            """
            ---
            Follow me on:

            𝕏 → [@arganbanan](https://x.com/arganbanan)

            LinkedIn → [Alexander Arganaidi](https://www.linkedin.com/in/alexander-arganaidi/)
            """
        )
    return resemblance, prompt, negative_prompt, submitted


def configure_gallery():
    global gallery_placeholder
    # Gallery display for inspo
    with gallery_placeholder.container():
        img = image_select(
            label="Choose a template, it's gonna be used for your general look 👩‍💻. Or just go with a random one.",
            images=sorted(glob.glob("./gallery/*.png")),
            use_container_width=False
        )
    return img


########################### Google auth ###########################

def google_callback(user_dict):
    if type(user_dict) == dict and "email" in user_dict:
        client_id = generate_unique_id(user_dict["email"])
        st.session_state.client_id = client_id

try:
    load_dotenv("./env")
except:
    print('WARNING: .env file not found, set env variables')
    pass

COOKIE_KEY = os.getenv('COOKIE_KEY')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URL = os.getenv('REDIRECT_URL')
with open('./config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

config['cookie']['key'] = COOKIE_KEY
config['oauth2']['google']['client_id'] = CLIENT_ID
config['oauth2']['google']['client_secret'] = CLIENT_SECRET
config['oauth2']['google']['redirect_url'] = REDIRECT_URL

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

########################### App ###########################

if st.session_state['authentication_status']:
    authenticator.logout()
    if st.session_state["email"] is not None:
        st.session_state.client_id = generate_unique_id(st.session_state["email"])
    
    st.markdown(f':orange[**Welcome {st.session_state["name"]}**]')
    
    files = [t for t in glob.glob("./output/*.png") if st.session_state.client_id in t]
    files.sort(key=lambda x: os.path.getmtime(x))
    st.session_state.all_generated_images = files[::-1]

    '---'
    uploaded_files = st.file_uploader(label="Upload up to 4 of your selfies. The clearer your face the better 🙃",
                                      accept_multiple_files=True,
                                      type=['png', 'jpg', 'webp']
                                      )

    '---'

    # Placeholders for gallery
    gallery_placeholder = st.empty()
    
    resemblance, prompt, negative_prompt, submitted = configure_sidebar()
    template_image_filepath = configure_gallery()

    '---'

    # all previously generated images: st.session_state.all_generated_images
    generated_images_placeholder = st.empty()
    if len(st.session_state.all_generated_images) > 0:
        with generated_images_placeholder.container():
            img = image_select(
                label="Your generations 🔥",
                images=st.session_state.all_generated_images,
                use_container_width=True,
            )


    if submitted:
        # make sure photos were uploaded
        if uploaded_files is None or len(uploaded_files) < 1:
            st.toast('Upload selfies before submitting', icon="🚨")
        else:
            selfie_filepaths = []
            for uploaded_file in uploaded_files:
                bytes_data = uploaded_file.getvalue()
                image = Image.open(io.BytesIO(bytes_data)).convert('RGB')
                image.save(f'./user_uploads/{uploaded_file.name}')
                selfie_filepaths.append(f'./user_uploads/{uploaded_file.name}')
            # send API request
            if "/0.png" in template_image_filepath:
                outputs_filepaths = get_portrait_random(selfie_filepaths, 
                                                 prompt, negative_prompt, 
                                                 resemblance, st.session_state.client_id)
            else:
                outputs_filepaths = get_portrait(template_image_filepath, selfie_filepaths, 
                                                prompt, negative_prompt, resemblance, st.session_state.client_id)
            st.toast("It's done!", icon='😍')
            with generated_images_placeholder.container():
                st.session_state.all_generated_images = outputs_filepaths + st.session_state.all_generated_images
                with generated_images_placeholder.container():
                    img = image_select(
                        label="Your generations 🔥",
                        images=st.session_state.all_generated_images,
                        use_container_width=True,
                    )
            
        
else:
    if st.session_state['authentication_status'] is False:
        st.error('Username/password is incorrect')
    elif st.session_state['authentication_status'] is None:
        st.warning('Waiting for authentification')

    try:
        authenticator.experimental_guest_login('Login with Google',
                                            provider='google',
                                            oauth2=config['oauth2'], 
                                            callback=google_callback)
    except LoginError as e:
        st.error(e)


with open('./config.yaml', 'w') as file:
    yaml.dump(config, file, default_flow_style=False)