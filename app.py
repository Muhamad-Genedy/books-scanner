import os
import io
import time
import json
import logging
import math
import shutil
import datetime

# Third-party imports
import fitz  # PyMuPDF
import cloudinary
import cloudinary.uploader
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from google.auth.transport.requests import Request

# ==========================================
# CONFIGURATION & SETUP
# ==========================================

# Logging Setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Environment Variables
# Ideally these should be set in the environment, but we can check them here.
REQUIRED_ENV_VARS = [
    'CLOUDINARY_CLOUD_NAME',
    'CLOUDINARY_API_KEY',
    'CLOUDINARY_API_SECRET'
]

# Google Service Account Env Var
SERVICE_ACCOUNT_JSON = os.getenv('GOOGLE_SERVICE_ACCOUNT_JSON')
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']
OUTPUT_FILE = 'books.json'
DRIVE_ROOT_ID = os.getenv('DRIVE_ROOT_ID', None) # Optional: start from a specific folder

# ==========================================
# CLOUDINARY CONFIG
# ==========================================
def setup_cloudinary():
    missing = [var for var in REQUIRED_ENV_VARS if not os.getenv(var)]
    if missing:
        logger.warning(f"Missing environment variables: {', '.join(missing)}. Cloudinary upload might fail.")
    
    cloudinary.config(
        cloud_name=os.getenv('CLOUDINARY_CLOUD_NAME'),
        api_key=os.getenv('CLOUDINARY_API_KEY'),
        api_secret=os.getenv('CLOUDINARY_API_SECRET'),
        secure=True
    )

# ==========================================
# JSON PERSISTENCE HELPERS
# ==========================================

def load_processed_ids():
    """Reads the existing JSON file and returns a set of processed drive_file_ids."""
    if not os.path.exists(OUTPUT_FILE):
        return set()
    
    processed_ids = set()
    try:
        with open(OUTPUT_FILE, 'r', encoding='utf-8') as f:
            data = json.load(f)
            if isinstance(data, list):
                for item in data:
                    if 'drive_file_id' in item:
                        processed_ids.add(item['drive_file_id'])
    except json.JSONDecodeError:
        logger.warning(f"Could not decode {OUTPUT_FILE}. Assuming empty or starting fresh.")
    except Exception as e:
        logger.error(f"Error reading {OUTPUT_FILE}: {e}")
    
    logger.info(f"Loaded {len(processed_ids)} processed IDs from cache.")
    return processed_ids

def append_record(record):
    """
    Appends a single record to the JSON array in the output file.
    Handles the file creation if it doesn't exist, and properly formats the array structure.
    """
    json_record = json.dumps(record, ensure_ascii=False, indent=4)
    
    try:
        if not os.path.exists(OUTPUT_FILE) or os.path.getsize(OUTPUT_FILE) == 0:
            # Create new file with a single element array
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.write(f"[\n{json_record}\n]")
        else:
            # Append to existing array
            # We need to open in binary mode to seek from the end efficiently and handle encoding manually if needed
            # but standard mode 'rb+' is fine for our purpose here.
            with open(OUTPUT_FILE, 'rb+') as f:
                f.seek(0, os.SEEK_END)
                # We need to find the last ']' to overwrite it.
                # In a well-formatted JSON file ending with "]", we assume the last non-whitespace char is ']'
                
                # Scan backwards for ']'
                pos = f.tell() - 1
                while pos >= 0:
                    f.seek(pos)
                    char = f.read(1)
                    if char == b']':
                        # Found the closing bracket.
                        # Move position here to overwrite it
                        f.seek(pos)
                        # Write the comma, the new record, and the closing bracket
                        # We need to handle the comma if the array was empty? 
                        # This logic assumes the file has at least "[\n...]" or "[]"
                        
                        # Note: If the file was "[]", we should check that
                        # If pos is basically just after '[', we don't need a comma.
                        # But typically our nice formatting means we have content.
                        
                        # Let's verify if array is empty by checking if there's content before.
                        # Easier strategy: just prepend comma unless it's the very first item (handled by file creation check)
                        
                        full_entry = f",\n{json_record}\n]"
                        f.write(full_entry.encode('utf-8'))
                        break
                    pos -= 1
    except Exception as e:
        logger.error(f"Failed to append record to {OUTPUT_FILE}: {e}")

# ==========================================
# GOOGLE DRIVE & PROCESSING LOGIC
# ==========================================

def get_drive_service():
    if not SERVICE_ACCOUNT_JSON:
        logger.critical("Process failed: GOOGLE_SERVICE_ACCOUNT_JSON environment variable is missing.")
        raise ValueError("Environment variable GOOGLE_SERVICE_ACCOUNT_JSON is not set.")
    
    try:
        service_account_info = json.loads(SERVICE_ACCOUNT_JSON)
    except json.JSONDecodeError as e:
        logger.critical("Process failed: GOOGLE_SERVICE_ACCOUNT_JSON contains invalid JSON.")
        raise ValueError(f"Invalid JSON in GOOGLE_SERVICE_ACCOUNT_JSON: {e}")

    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def download_file(service, file_id, file_name):
    """Downloads a file from Drive to a local temp path."""
    request = service.files().get_media(fileId=file_id)
    temp_path = f"temp_{file_id}.pdf" # Keep extension generic or derived
    
    with io.FileIO(temp_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
    
    return temp_path

def process_pdf(pdf_path, file_id, drive_file_name):
    """
    Extracts metadata, page count, size, and generates a thumbnail.
    Uploads thumbnail to Cloudinary.
    Returns a dict with extracted info.
    """
    if not os.path.exists(pdf_path):
        return None

    try:
        # File Size
        size_bytes = os.path.getsize(pdf_path)
        file_size_mb = int(round(size_bytes / (1024 * 1024)))
        
        # Open PDF
        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        
        # Thumbnail Generation (Page 2 or Page 1)
        target_page_index = 1 if page_count >= 2 else 0
        page = doc.load_page(target_page_index)
        pix = page.get_pixmap()
        
        temp_img_path = f"temp_{file_id}.png"
        pix.save(temp_img_path)
        doc.close()
        
        # Upload to Cloudinary
        logger.info(f"Uploading thumbnail for {drive_file_name} to Cloudinary...")
        upload_result = cloudinary.uploader.upload(
            temp_img_path, 
            public_id=file_id, 
            folder="pdf_thumbnails"
        )
        secure_url = upload_result.get('secure_url')
        
        # Cleanup Image
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)
            
        return {
            "page_count": page_count,
            "file_size_mb": file_size_mb,
            "image_url": secure_url
        }
        
    except Exception as e:
        logger.error(f"Error processing PDF {drive_file_name} ({file_id}): {e}")
        return None

def process_level(service, parent_id, current_level, context_data, processed_ids):
    """
    Recursive function to traverse the fixed folder hierarchy.
    
    Levels:
    0: Root -> Folders (Academic Year)
    1: Academic Year -> Folders (Term)
    2: Term -> Folders (Subject)
    3: Subject -> Folders (Book Type)
    4: Book Type -> Folders (Release Year)
    5: Release Year -> Files (PDFs)
    """
    
    # Define query based on level
    if current_level < 5:
        # Looking for folders
        query = f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    else:
        # Looking for PDF files
        query = f"'{parent_id}' in parents and mimeType = 'application/pdf' and trashed = false"

    # Execute Query
    page_token = None
    while True:
        try:
            results = service.files().list(
                q=query,
                pageSize=50,
                fields="nextPageToken, files(id, name)",
                pageToken=page_token
            ).execute()
            
            items = results.get('files', [])
            
            if not items:
                # logger.debug(f"No items found at level {current_level} under parent {parent_id}")
                pass
            
            # Sort items by name for consistent processing (optional but good for debugging)
            items.sort(key=lambda x: x['name'])
            
            for item in items:
                item_id = item['id']
                item_name = item['name']
                
                # Update Context
                new_context = context_data.copy()
                
                if current_level == 0:
                    new_context['academic_year_id'] = item_name
                    logger.info(f"Entered Academic Year: {item_name}")
                    process_level(service, item_id, 1, new_context, processed_ids)
                    
                elif current_level == 1:
                    new_context['term_id'] = item_name
                    logger.info(f"  Entered Term: {item_name}")
                    process_level(service, item_id, 2, new_context, processed_ids)
                    
                elif current_level == 2:
                    new_context['subject_id'] = item_name
                    logger.info(f"    Entered Subject: {item_name}")
                    process_level(service, item_id, 3, new_context, processed_ids)
                    
                elif current_level == 3:
                    new_context['book_type_id'] = item_name
                    logger.info(f"      Entered Book Type: {item_name}")
                    process_level(service, item_id, 4, new_context, processed_ids)
                    
                elif current_level == 4:
                    new_context['release_year'] = item_name
                    logger.info(f"        Entered Release Year: {item_name}")
                    process_level(service, item_id, 5, new_context, processed_ids)
                    
                elif current_level == 5:
                    # PDF FILE PROCESSING
                    if item_id in processed_ids:
                        logger.info(f"          [SKIP] Already processed: {item_name}")
                        continue
                    
                    logger.info(f"          Processing File: {item_name}")
                    
                    time.sleep(0.5) # Rate limit safeguard
                    
                    # 1. Download
                    try:
                        temp_pdf_path = download_file(service, item_id, item_name)
                    except Exception as exc:
                        logger.error(f"Failed to download {item_name}: {exc}")
                        continue
                        
                    # 2. Extract & Upload
                    meta = process_pdf(temp_pdf_path, item_id, item_name)
                    
                    # 3. Cleanup PDF
                    if os.path.exists(temp_pdf_path):
                        os.remove(temp_pdf_path)
                    
                    if meta:
                        # 4. Construct Record
                        record = {
                            "name": item_name,
                            "drive_file_id": item_id,
                            "academic_year_id": new_context.get('academic_year_id'),
                            "term_id": new_context.get('term_id'),
                            "subject_id": new_context.get('subject_id'),
                            "book_type_id": new_context.get('book_type_id'),
                            "release_year": new_context.get('release_year'),
                            "page_count": meta['page_count'],
                            "file_size_mb": meta['file_size_mb'],
                            "image_url": meta['image_url']
                        }
                        
                        # 5. Save Record
                        append_record(record)
                        processed_ids.add(item_id)
                        logger.info(f"          [DONE] Saved: {item_name}")
                    else:
                        logger.error(f"          [FAIL] Processing failed for: {item_name}")
            
            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        except Exception as e:
            logger.error(f"Error traversing level {current_level} (parent: {parent_id}): {e}")
            break

def main():
    logger.info("Script started.")
    
    setup_cloudinary()
    
    try:
        service = get_drive_service()
        logger.info("Google Drive Service Authenticated.")
    except Exception as e:
        logger.critical(f"Authentication Failed: {e}")
        return

    processed_ids = load_processed_ids()
    
    # Determine Root Folder
    # If DRIVE_ROOT_ID env var is set, use it. Otherwise, search for 'My Drive' root or prompt user/assume 'root'
    # 'root' alias works for My Drive root.
    root_id = DRIVE_ROOT_ID if DRIVE_ROOT_ID else 'root'
    
    logger.info(f"Starting traversal from ID: {root_id}")
    
    # Start Recursion
    # Context data accumulates folder names
    initial_context = {}
    
    process_level(service, root_id, 0, initial_context, processed_ids)
    
    logger.info("Script finished successfully.")

if __name__ == '__main__':
    main()
