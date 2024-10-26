import websocket #NOTE: websocket-client (https://github.com/websocket-client/websocket-client)
import uuid
import json
import random
import urllib.request
import urllib.parse
import requests
from PIL import Image
import io
import os

server_address = "https://e0dyf81kl423t5-8188.proxy.runpod.net/api"

def queue_prompt(prompt, client_id):
    p = {"prompt": prompt, "client_id": client_id}
    response = requests.post(f"{server_address}/prompt", json=p)
    response.raise_for_status()  # Raise an error for bad status codes
    return response.json()  # Parse JSON directly from the response

def get_image(filename, subfolder, folder_type):
    params = {"filename": filename, "subfolder": subfolder, "type": folder_type}
    response = requests.get(f"{server_address}/view", params=params)
    response.raise_for_status()  # Raise an error for bad status codes
    return response.content  # Return the raw image data

def get_history(prompt_id):
    response = requests.get(f"{server_address}/history/{prompt_id}")
    response.raise_for_status()  # Raise an error for bad status codes
    return response.json()  # Parse JSON directly from the response

def get_images(ws, prompt, client_id):
    prompt_id = queue_prompt(prompt, client_id)['prompt_id']
    output_images = {}
    while True:
        out = ws.recv()
        if isinstance(out, str):
            message = json.loads(out)
            if message['type'] == 'executing':
                data = message['data']
                if data['node'] is None and data['prompt_id'] == prompt_id:
                    break 
        else:
            continue 

    history = get_history(prompt_id)[prompt_id]
    for o in history['outputs']:
        for node_id in history['outputs']:
            node_output = history['outputs'][node_id]
            if 'images' in node_output:
                images_output = []
                for image in node_output['images']:
                    image_data = get_image(image['filename'], image['subfolder'], image['type'])
                    images_output.append(image_data)
            output_images[node_id] = images_output
    return output_images


def upload_image(img_path):
    with open(img_path, "rb") as image_file:
        files = {
            "image": image_file,
        }
        data = {
            "overwrite": True,
        }
        response = requests.post(f"{server_address}/upload/image", files=files, data=data)
        assert response.status_code == 200, response.status_code
        comfy_path = response.json()["name"]
        return comfy_path
    

def get_portrait(template_filepath, selfie_filepaths, positive_prompt, negative_prompt, resemblance, client_id):
    file_path = "./workflow_fast_runpod_api.json"
    with open(file_path, 'r') as file:
        prompt = json.load(file)

    # upload images to comfy
    comfy_template_filepath = upload_image(template_filepath)

    comfy_selfie_filepaths = []
    for fp in selfie_filepaths:
        comfy_selfie_filepaths.append(upload_image(fp))

    # image nodes info
    prompt['18']['inputs']['image'] = comfy_template_filepath
    for i, node_id in enumerate([66, 67, 68, 70]):
        if i >= len(comfy_selfie_filepaths):
            prompt[str(node_id)]['inputs']['image'] = comfy_selfie_filepaths[0]
            continue
        prompt[str(node_id)]['inputs']['image'] = comfy_selfie_filepaths[i]
    # KSampler seeds
    prompt["17"]["inputs"]["seed"] = random.getrandbits(48)
    prompt["22"]["inputs"]["seed"] = random.getrandbits(48)
    # Positive prompts
    prompt["74"]["inputs"]["text"] = prompt["74"]["inputs"]["text"] + f" ({positive_prompt})"
    prompt["9"]["inputs"]["text"] = prompt["9"]["inputs"]["text"] + f" ({positive_prompt})"
    # Negative prompts
    prompt["75"]["inputs"]["text"] = prompt["75"]["inputs"]["text"] + f" ({negative_prompt})"
    prompt["11"]["inputs"]["text"] = prompt["11"]["inputs"]["text"] + f" ({negative_prompt})"
    # InstantID weight
    prompt["64"]["inputs"]["ip_weight"] = resemblance
    prompt["64"]["inputs"]["cn_strength"] = resemblance
    prompt["72"]["inputs"]["ip_weight"] = resemblance
    prompt["72"]["inputs"]["cn_strength"] = resemblance

    ws = websocket.WebSocket()
    ws.connect("wss://{}/ws?clientId={}".format(server_address.replace('https://', ''), client_id))

    images = get_images(ws, prompt, client_id)

    outputs_filepaths = []
    for node_id in images:
        for image_data in images[node_id]:
            image = Image.open(io.BytesIO(image_data))
            save_file_name = f"./output/{client_id}-{uuid.uuid4()}.png"
            outputs_filepaths.append(save_file_name)
            image.save(save_file_name)
    return outputs_filepaths


def get_portrait_random(selfie_filepaths, positive_prompt, negative_prompt, resemblance, client_id):
    file_path = "./workflow_no_template_api.json"
    with open(file_path, 'r') as file:
        prompt = json.load(file)

    comfy_selfie_filepaths = []
    for fp in selfie_filepaths:
        comfy_selfie_filepaths.append(upload_image(fp))

    # image nodes info
    for i, node_id in enumerate([66, 67, 68, 70]):
        if i >= len(comfy_selfie_filepaths):
            prompt[str(node_id)]['inputs']['image'] = comfy_selfie_filepaths[0]
            continue
        prompt[str(node_id)]['inputs']['image'] = comfy_selfie_filepaths[i]
    # KSampler seeds
    prompt["17"]["inputs"]["seed"] = random.getrandbits(48)
    prompt["22"]["inputs"]["seed"] = random.getrandbits(48)
    # Positive prompts
    prompt["74"]["inputs"]["text"] = prompt["74"]["inputs"]["text"] + f" ({positive_prompt})"
    prompt["9"]["inputs"]["text"] = prompt["9"]["inputs"]["text"] + f" ({positive_prompt})"
    # Negative prompts
    prompt["75"]["inputs"]["text"] = prompt["75"]["inputs"]["text"] + f" ({negative_prompt})"
    prompt["11"]["inputs"]["text"] = prompt["11"]["inputs"]["text"] + f" ({negative_prompt})"
    # InstantID weight
    prompt["64"]["inputs"]["ip_weight"] = resemblance
    prompt["64"]["inputs"]["cn_strength"] = resemblance
    prompt["72"]["inputs"]["ip_weight"] = resemblance
    prompt["72"]["inputs"]["cn_strength"] = resemblance

    ws = websocket.WebSocket()
    ws.connect("wss://{}/ws?clientId={}".format(server_address.replace('https://', ''), client_id))

    images = get_images(ws, prompt, client_id)

    outputs_filepaths = []
    for node_id in images:
        for image_data in images[node_id]:
            image = Image.open(io.BytesIO(image_data))
            save_file_name = f"./output/{client_id}-{uuid.uuid4()}.png"
            outputs_filepaths.append(save_file_name)
            image.save(save_file_name)
    return outputs_filepaths
