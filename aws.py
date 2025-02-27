from dotenv import load_dotenv
try:
    load_dotenv()
except:
    print('WARNING: .env file not found, set env variables')

import os
import boto3
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from botocore.exceptions import ClientError
import os


BUCKET_NAME = os.environ.get('AWS_BUCKET')

_s3_client = None


def get_s3_client():
    """
    Create and return an S3 client using credentials from environment variables.
    Requires AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY to be set in environment.
    """
    global _s3_client
    if _s3_client is not None:
        return _s3_client
    try:
        s3_client = boto3.client(
            's3',
            aws_access_key_id=os.environ.get('AWS_ACCESS_KEY_ID'),
            aws_secret_access_key=os.environ.get('AWS_SECRET_ACCESS_KEY'),
        )
        _s3_client = s3_client
        return s3_client
    except Exception as e:
        raise Exception(f"Failed to create S3 client: {str(e)}")


def upload_and_get_presigned_url(image_path, client_id, folder='temp', bucket_name=BUCKET_NAME, expiration_hours=24, make_public=False):
    """
    Upload an image to an S3 bucket and generate a URL for public access.
    
    Parameters:
    - image_path (str): Local path to the image file
    - client_id (str): Unique identifier for the client/user
    - folder (str): Folder within the bucket to store the image
    - bucket_name (str): Name of the S3 bucket
    - expiration_hours (int): Number of hours before the URL expires
    - make_public (bool): If True, makes the object publicly accessible instead of using presigned URLs
    
    Returns:
    - str: URL for accessing the uploaded image (presigned or public)
    
    Raises:
    - ValueError: If bucket_name is not provided
    - FileNotFoundError: If the image file doesn't exist
    - ClientError: If there's an issue with the S3 client
    """
    if not bucket_name:
        raise ValueError("Bucket name must be provided")
    
    if not os.path.exists(image_path):
        raise FileNotFoundError(f"Image not found at: {image_path}")
    
    # Extract the filename from the path
    filename = os.path.basename(image_path)
    
    # Create a unique key for the image
    # key = f"{folder}/{client_id}/{filename}"
    key = f"{folder}/{client_id}-{datetime.now().strftime('%Y%m%d_%H%M%S')}{filename}"
    
    # Initialize the S3 client
    s3_client = get_s3_client()
    
    try:
        extra_args = {
            'ContentType': get_content_type(filename)
        }
        
        # If make_public is True, add public-read ACL
        if make_public:
            extra_args['ACL'] = 'public-read'
        
        # Upload the file to S3
        s3_client.upload_file(
            image_path, 
            bucket_name, 
            key, 
            ExtraArgs=extra_args
        )
        
        if make_public:
            # Return a direct S3 URL for public objects
            return f"https://{bucket_name}.s3.amazonaws.com/{key}"
        else:
            # Generate a presigned URL
            expiration = expiration_hours * 3600  # Convert hours to seconds
            presigned_url = s3_client.generate_presigned_url(
                'get_object',
                Params={'Bucket': bucket_name, 'Key': key},
                ExpiresIn=expiration
            )

            if '?' in presigned_url:
                presigned_url = presigned_url.split('?')[0]

            return presigned_url
    
    except ClientError as e:
        print(f"Error: {e}")
        raise

def get_content_type(filename):
    """
    Determine the content type based on file extension.
    
    Parameters:
    - filename (str): Name of the file
    
    Returns:
    - str: Content type for the file
    """
    extension = os.path.splitext(filename)[1].lower()
    
    content_types = {
        '.jpg': 'image/jpeg',
        '.jpeg': 'image/jpeg',
        '.png': 'image/png',
        '.gif': 'image/gif',
        '.bmp': 'image/bmp',
        '.webp': 'image/webp',
        '.svg': 'image/svg+xml',
        '.tiff': 'image/tiff',
        '.tif': 'image/tiff'
    }
    
    return content_types.get(extension, 'application/octet-stream')


def upload_images_concurrently(image_paths, client_id, folder='temp', bucket_name=BUCKET_NAME, expiration_hours=24):
    """Upload multiple images in parallel and return their presigned URLs."""
    with ThreadPoolExecutor() as executor:
        results = executor.map(lambda path: upload_and_get_presigned_url(path, client_id, folder, bucket_name, expiration_hours), image_paths)
    return list(results)
    

def download_image_from_s3(url, save_path):
    """
    Download an image from a given presigned S3 URL and save it to a specified path.

    Args:
        url (str): Presigned URL of the image
        save_path (str): Local path to save the downloaded image

    Returns:
        str: Path to the downloaded image
    """
    try:
        s3_client = get_s3_client()
        
        # Parse the bucket name and object key from the URL
        parsed_url = url.split('?')[0]
        path_parts = parsed_url.split('/')
        bucket_name = BUCKET_NAME
        object_key = '/'.join(path_parts[3:])
        
        # Ensure the directory exists
        os.makedirs(os.path.dirname(save_path), exist_ok=True)
        
        # Download the file
        s3_client.download_file(bucket_name, object_key, save_path)
        
        return save_path
    except Exception as e:
        raise Exception(f"Failed to download image: {str(e)}")
