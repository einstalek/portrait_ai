import os
import threading
import requests

from dotenv import load_dotenv
try:
    load_dotenv()
except:
    print('WARNING: .env file not found, set env variables')

RUNPOD_API_URI = os.environ.get('RUNPOD_API_URI')
RUNPOD_API_KEY = os.environ.get('RUNPOD_API_KEY')


def runpond_submit_job(template_url, 
                       selfie_urls, 
                       prompt, 
                       negative_prompt, 
                       resemblance, 
                       cn_strength,
                       steps
                    ) -> str:
    """
    Submits job and return job_id
    """
    headers = {
        'Content-Type': 'application/json',
        'Authorization': f'Bearer {RUNPOD_API_KEY}'
    }

    data = {
        'input': {
            "template_image": template_url,
            "selfie_images": selfie_urls,
            "positive_prompt": prompt,
            "negative_prompt": negative_prompt,
            "steps": [int(steps) for _ in range(4)],
            "ip_weight": resemblance,
            "cn_strength": cn_strength
            }
    }

    response = requests.post(f'{RUNPOD_API_URI}/run', 
                             headers=headers, 
                             json=data)

    return response.json().get("id")


def runpond_status_job(job_id):
    headers = {
        'Authorization': f'Bearer {RUNPOD_API_KEY}'
    }
    response = requests.get(f'{RUNPOD_API_URI}/status/{job_id}', headers=headers)
    return response


def runpod_job_status(job_id):
    headers = {
        'Authorization': f'Bearer {RUNPOD_API_KEY}'
    }
    response = requests.get(f'{RUNPOD_API_URI}/status/{job_id}', headers=headers)
    return response.json()

