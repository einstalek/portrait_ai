import os
from dotenv import load_dotenv

import glob
import streamlit as st
import streamlit_authenticator as stauth
from streamlit_authenticator import LoginError
from streamlit_image_select import image_select
import yaml
import time
from yaml.loader import SafeLoader
from PIL import Image, ImageOps
import io
import hashlib
from comfy import (runpond_submit_job,
                   runpod_job_status)
from aws import (upload_and_get_presigned_url, 
                 upload_images_concurrently,
                 download_image_from_s3)

def generate_unique_id(email: str) -> str:
    # Hash the email to create a unique, anonymized identifier
    email_hash = hashlib.sha256(email.encode()).hexdigest()
    return email_hash

########################### Create necessary dirs ###########################
os.makedirs("./user_uploads/", exist_ok=True)
os.makedirs("./output/", exist_ok=True)


########################### State variables ###########################
st.session_state.all_generated_images = []
st.session_state.job_running = False
st.session_state.job_id = None


########################### UI configurations ###########################
st.set_page_config(page_title="AI Portrait Generator",
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
            st.info("**Adjust the settings here**", icon="🛠")
            # with st.expander(":orange[**Refine your settings here**]"):
            resemblance = st.slider(
                "Identity control strength", 
                value=1.2, min_value=0.5, max_value=2., step=0.1, 
                help="Higher value preserves your identity more but may reduce naturalness.")
            cn_strength = st.slider(
                "Pose control strength", 
                value=0.1, min_value=0., max_value=1., step=0.1, 
                help="Higher value increases conformity to the template composition.")
            steps = st.slider(
                "Number of generation steps", 
                value=8, min_value=5, max_value=12, step=1, 
                help="A higher value generally improves quality but increases processing time.")
            prompt = st.text_area(
                ":orange[**Adjust positive prompt: ✍🏾**]",
                value="dressed casually, soft natural lighting",
                help="Describe what you want to see in the generated image.")
            negative_prompt = st.text_area(":orange[**Adjust negative prompt: 🙅🏽‍♂️**]",
                                        value="grinning, looking away",
                                        help="Describe what you want to avoid in the generated image.")
            

            submitted = st.form_submit_button(
                "Submit", 
                type="primary", 
                use_container_width=True, 
                disabled=st.session_state.job_running)

        # Credits and resources
        st.markdown(
            """
            ---
            Follow me on:

            𝕏 → [@arganbanan](https://x.com/arganbanan)

            LinkedIn → [Alexander Arganaidi](https://www.linkedin.com/in/alexander-arganaidi/)
            """
        )
    return resemblance, cn_strength, steps, prompt, negative_prompt, submitted


def configure_gallery():
    global gallery_placeholder
    # Gallery display for inspo
    with gallery_placeholder.container():
        img = image_select(
            label="Choose a template, it's gonna be used for your general look 👩‍💻. Or just go with a random one.",
            images=sorted(glob.glob("./gallery/*.png")),
            use_container_width=False,
            key="gallery"
        )
    return img


########################### Google auth ###########################

def google_callback(user_dict):
    if type(user_dict) == dict and "email" in user_dict:
        client_id = generate_unique_id(user_dict["email"])
        st.session_state.client_id = client_id


def poll_job_status(job_id, update_ui_callback, period=3):
    """
    Runs in the background to check job status periodically.
    When completed, it downloads the image and updates the UI.
    """
    global CLIENT_ID
    status = "PENDING"
    
    while status not in ["COMPLETED", "FAILED"]:
        time.sleep(period)  # Wait before polling again
        job_response = runpod_job_status(job_id)
        status = job_response.get("status")
        
        if status == "FAILED":
            update_ui_callback(job_failed=True)
            return []

    # Once completed, get the output image
    output_urls = job_response.get("output", [])
    if output_urls:
        image_paths = []
        for i, url in enumerate(output_urls):
            local_filename = f"./output/{CLIENT_ID}-{job_id}-{i+1}.jpg"
            download_image_from_s3(url, local_filename)
            image_paths.append(local_filename)
        update_ui_callback(job_completed=True, images=image_paths)

try:
    load_dotenv()
except:
    print('WARNING: .env file not found, set env variables')

COOKIE_KEY = os.getenv('COOKIE_KEY')
CLIENT_ID = os.getenv('CLIENT_ID')
CLIENT_SECRET = os.getenv('CLIENT_SECRET')
REDIRECT_URI = os.getenv('REDIRECT_URI')
MAX_DISPLAY_IMAGES = int(os.getenv('MAX_DISPLAY_IMAGES'))

with open('./config.yaml') as file:
    config = yaml.load(file, Loader=SafeLoader)

config['cookie']['key'] = COOKIE_KEY
config['oauth2']['google']['client_id'] = CLIENT_ID
config['oauth2']['google']['client_secret'] = CLIENT_SECRET
config['oauth2']['google']['redirect_uri'] = REDIRECT_URI

authenticator = stauth.Authenticate(
    config['credentials'],
    config['cookie']['name'],
    config['cookie']['key'],
    config['cookie']['expiry_days']
)

########################### App ###########################

generations = glob.glob(f"./output/{CLIENT_ID}-*")
generations.sort(key=os.path.getmtime)
if len(generations) > MAX_DISPLAY_IMAGES:
    for fp in generations[:-MAX_DISPLAY_IMAGES]:
        try:
            os.remove(fp)
        except:
            print(f"Couldn't remove generation {fp}")
    generations = generations[-MAX_DISPLAY_IMAGES:]
st.session_state.all_generated_images.extend(
    generations
)


if st.session_state['authentication_status']:
    authenticator.logout()
    if st.session_state["email"] is not None:
        st.session_state.client_id = generate_unique_id(st.session_state["email"])
    
    st.info(f'**Welcome {st.session_state["name"]}**', icon="👋🏾")

    st.info("**Upload your selfies, adjust settings (if needed) and click Submit in the pannel on the left**")
   
    '---'
    uploaded_files = st.file_uploader(label="Upload up to 6 selfies. More images and clearer faces yield better results 🙃",
                                      accept_multiple_files=True,
                                      type=['png', 'jpg', 'jpeg', 'webp']
                                      )
    MAX_SELFIE_NUMBER = int(os.environ.get('MAX_SELFIE_NUMBER'))
    if len(uploaded_files) > MAX_SELFIE_NUMBER:
        uploaded_files = uploaded_files[-MAX_SELFIE_NUMBER:]
    
    if uploaded_files:
        st.subheader("Uploaded Images")
        cols = st.columns(len(uploaded_files))
        for col, file in zip(cols, uploaded_files):
            img = Image.open(io.BytesIO(file.getvalue()))
            img = ImageOps.exif_transpose(img)
            h, w = img.size
            scale = max(h, w) / 512
            new_size = [int(t / scale) for t in (h, w)]
            img.thumbnail(new_size)
            col.image(img, use_container_width=True)

    '---'

    # Placeholders for gallery
    gallery_placeholder = st.empty()
    
    resemblance, cn_strength, steps, prompt, negative_prompt, submitted = configure_sidebar()
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

    def update_ui(job_completed=False, job_failed=False, images=None):
        if job_failed:
            st.session_state.job_running = False
            st.error("Job failed. Please try again.")
        elif job_completed and images:
            st.session_state.all_generated_images.extend(images)
            st.session_state.job_running = False
            st.rerun()  # Refresh Streamlit UI


    if submitted and not st.session_state.job_running:
        st.session_state.job_running = True
        # make sure photos were uploaded
        if uploaded_files is None or len(uploaded_files) < 1:
            st.toast('Upload selfies before submitting', icon="🚨")
        else:
            selfie_filepaths = []
            for uploaded_file in uploaded_files:
                bytes_data = uploaded_file.getvalue()
                image = Image.open(io.BytesIO(bytes_data)).convert('RGB')
                image = ImageOps.exif_transpose(image)
                image.save(f'./user_uploads/{uploaded_file.name}')
                selfie_filepaths.append(f'./user_uploads/{uploaded_file.name}')

            st.toast("Uploading template image")
            # upload to aws
            template_url = upload_and_get_presigned_url(image_path=template_image_filepath, 
                                                        client_id=CLIENT_ID, 
                                                        folder='input')
            st.toast("Uploading selfies")
            selfie_urls = upload_images_concurrently(selfie_filepaths, 
                                                     client_id=CLIENT_ID, 
                                                     folder='input')
            
            for fp in selfie_filepaths:
                os.remove(fp)
        
            st.toast("Submitting your job! Result will appear below in about a minute.")
            
            job_id = runpond_submit_job(template_url, 
                                       selfie_urls, 
                                       prompt, 
                                       negative_prompt, 
                                       resemblance, 
                                       cn_strength,
                                       steps)
            poll_job_status(job_id, update_ui)

            st.toast("It's done!", icon='😍')

    elif submitted and st.session_state.job_running:
        st.toast("Wait until the previous job is finished!")

    if st.session_state.all_generated_images:
        with generated_images_placeholder.container():
            # st.session_state.all_generated_images = outputs_filepaths + st.session_state.all_generated_images
            with generated_images_placeholder.container():
                img = image_select(
                    label="Your generations 🔥",
                    images=st.session_state.all_generated_images,
                    use_container_width=False,
                    key="generated"
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