import os
import io
import time
import json
import logging
import math
import shutil
import datetime
import threading

# Third-party imports
import fitz  # PyMuPDF
import cloudinary
import cloudinary.uploader
from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google.oauth2 import service_account
from google.auth.transport.requests import Request

# ==========================================
# CONFIGURATION
# ==========================================
OUTPUT_FILE = 'books.json'
SCOPES = ['https://www.googleapis.com/auth/drive.readonly']

# ==========================================
# HELPER FUNCTIONS
# ==========================================

def log_message(log_callback, message, level="INFO"):
    """Emits a log message to the callback."""
    if log_callback:
        timestamp = datetime.datetime.now().strftime("%H:%M:%S")
        log_callback(f"[{timestamp}] [{level}] {message}")

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
        pass # Assuming empty or starting fresh
    except Exception as e:
        pass # Log error via callback if possible, but here we just fail safe
    
    return processed_ids

def append_record(record):
    """
    Appends a single record to the JSON array in the output file.
    """
    json_record = json.dumps(record, ensure_ascii=False, indent=4)
    
    try:
        if not os.path.exists(OUTPUT_FILE) or os.path.getsize(OUTPUT_FILE) == 0:
            with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
                f.write(f"[\n{json_record}\n]")
        else:
            with open(OUTPUT_FILE, 'rb+') as f:
                f.seek(0, os.SEEK_END)
                pos = f.tell() - 1
                while pos >= 0:
                    f.seek(pos)
                    char = f.read(1)
                    if char == b']':
                        f.seek(pos)
                        full_entry = f",\n{json_record}\n]"
                        f.write(full_entry.encode('utf-8'))
                        break
                    pos -= 1
    except Exception as e:
        print(f"Error appending record: {e}") # Fallback

# ==========================================
# MAIN SCANNING LOGIC
# ==========================================

def get_drive_service(service_account_json):
    try:
        service_account_info = json.loads(service_account_json)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in Service Account Key: {e}")

    creds = service_account.Credentials.from_service_account_info(
        service_account_info, scopes=SCOPES)
    return build('drive', 'v3', credentials=creds)

def download_file(service, file_id, file_name):
    request = service.files().get_media(fileId=file_id)
    temp_path = f"temp_{file_id}.pdf"
    
    with io.FileIO(temp_path, 'wb') as fh:
        downloader = MediaIoBaseDownload(fh, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
    return temp_path

def process_pdf(pdf_path, file_id, drive_file_name, log_callback):
    if not os.path.exists(pdf_path):
        return None

    try:
        size_bytes = os.path.getsize(pdf_path)
        file_size_mb = int(round(size_bytes / (1024 * 1024)))
        
        doc = fitz.open(pdf_path)
        page_count = doc.page_count
        
        target_page_index = 1 if page_count >= 2 else 0
        page = doc.load_page(target_page_index)
        pix = page.get_pixmap()
        
        temp_img_path = f"temp_{file_id}.png"
        pix.save(temp_img_path)
        doc.close()
        
        log_message(log_callback, f"Uploading thumbnail for {drive_file_name}...", "INFO")
        
        upload_result = cloudinary.uploader.upload(
            temp_img_path, 
            public_id=file_id, 
            folder="pdf_thumbnails"
        )
        secure_url = upload_result.get('secure_url')
        
        if os.path.exists(temp_img_path):
            os.remove(temp_img_path)
            
        return {
            "page_count": page_count,
            "file_size_mb": file_size_mb,
            "image_url": secure_url
        }
        
    except Exception as e:
        log_message(log_callback, f"Error processing PDF {drive_file_name}: {e}", "ERROR")
        return None

def process_level(service, parent_id, current_level, context_data, processed_ids, log_callback, progress_callback, stop_event, config):
    if stop_event.is_set():
        return

    # Levels: 0:Year -> 1:Term -> 2:Subject -> 3:Type -> 4:Release -> 5:Files
    if current_level < 5:
        query = f"'{parent_id}' in parents and mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    else:
        query = f"'{parent_id}' in parents and mimeType = 'application/pdf' and trashed = false"

    page_token = None
    while True:
        if stop_event.is_set():
            break
            
        try:
            results = service.files().list(
                q=query,
                pageSize=50,
                fields="nextPageToken, files(id, name)",
                pageToken=page_token
            ).execute()
            
            items = results.get('files', [])
            items.sort(key=lambda x: x['name'])
            
            # --- FLAT FOLDER MODE START ---
            if current_level == 0 and not items and not page_token:
                # Primary query returned no folders. Let's check for PDFs directly.
                log_message(log_callback, "No folders found matching the structure. Checking for PDF files...", "INFO")
                try:
                    pdf_query = f"'{parent_id}' in parents and mimeType = 'application/pdf' and trashed = false"
                    pdf_res = service.files().list(q=pdf_query, pageSize=100, fields="nextPageToken, files(id, name)").execute()
                    pdf_items = pdf_res.get('files', [])
                    
                    if pdf_items:
                        log_message(log_callback, f"FLAT FOLDER MODE: Found {len(pdf_items)} PDF files. Processing...", "SUCCESS")
                        
                        # Process PDFs directly without nested structure
                        for pdf_item in pdf_items:
                            if stop_event.is_set():
                                break
                                
                            pdf_id = pdf_item['id']
                            pdf_name = pdf_item['name']
                            
                            if pdf_id in processed_ids:
                                progress_callback(skipped=1)
                                continue
                            
                            log_message(log_callback, f"Processing: {pdf_name}", "INFO")
                            
                            try:
                                temp_pdf_path = download_file(service, pdf_id, pdf_name)
                                meta = process_pdf(temp_pdf_path, pdf_id, pdf_name, log_callback)
                                
                                if os.path.exists(temp_pdf_path):
                                    os.remove(temp_pdf_path)
                                
                                if meta:
                                    # Use metadata from config for flat folder
                                    record = {
                                        "name": pdf_name,
                                        "drive_file_id": pdf_id,
                                        "academic_year_id": config.get('academic_year_id', 'Direct'),
                                        "term_id": config.get('term_id', 'Direct'),
                                        "subject_id": config.get('subject_id', 'Direct'),
                                        "book_type_id": "Direct",
                                        "release_year": config.get('release_year', 'Direct'),
                                        **meta
                                    }
                                    append_record(record)
                                    processed_ids.add(pdf_id)
                                    log_message(log_callback, f"Finished: {pdf_name}", "SUCCESS")
                                    progress_callback(processed=1)
                                else:
                                    log_message(log_callback, f"Failed metadata extraction: {pdf_name}", "ERROR")
                                    progress_callback(errors=1)
                                    
                            except Exception as exc:
                                log_message(log_callback, f"Error on file {pdf_name}: {exc}", "ERROR")
                                progress_callback(errors=1)
                        
                        # Check for more pages
                        pdf_token = pdf_res.get('nextPageToken')
                        while pdf_token:
                            if stop_event.is_set():
                                break
                            pdf_res = service.files().list(
                                q=pdf_query,
                                pageSize=100,
                                fields="nextPageToken, files(id, name)",
                                pageToken=pdf_token
                            ).execute()
                            pdf_items = pdf_res.get('files', [])
                            
                            for pdf_item in pdf_items:
                                if stop_event.is_set():
                                    break
                                pdf_id = pdf_item['id']
                                pdf_name = pdf_item['name']
                                
                                if pdf_id in processed_ids:
                                    progress_callback(skipped=1)
                                    continue
                                
                                log_message(log_callback, f"Processing: {pdf_name}", "INFO")
                                
                                try:
                                    temp_pdf_path = download_file(service, pdf_id, pdf_name)
                                    meta = process_pdf(temp_pdf_path, pdf_id, pdf_name, log_callback)
                                    
                                    if os.path.exists(temp_pdf_path):
                                        os.remove(temp_pdf_path)
                                    
                                    if meta:
                                        record = {
                                            "name": pdf_name,
                                            "drive_file_id": pdf_id,
                                            "academic_year_id": config.get('academic_year_id', 'Direct'),
                                            "term_id": config.get('term_id', 'Direct'),
                                            "subject_id": config.get('subject_id', 'Direct'),
                                            "book_type_id": "Direct",
                                            "release_year": config.get('release_year', 'Direct'),
                                            **meta
                                        }
                                        append_record(record)
                                        processed_ids.add(pdf_id)
                                        log_message(log_callback, f"Finished: {pdf_name}", "SUCCESS")
                                        progress_callback(processed=1)
                                    else:
                                        log_message(log_callback, f"Failed metadata extraction: {pdf_name}", "ERROR")
                                        progress_callback(errors=1)
                                        
                                except Exception as exc:
                                    log_message(log_callback, f"Error on file {pdf_name}: {exc}", "ERROR")
                                    progress_callback(errors=1)
                            
                            pdf_token = pdf_res.get('nextPageToken')
                        
                        log_message(log_callback, "Flat folder processing complete.", "SUCCESS")
                        return  # Exit early, no need to continue with folder structure
                    else:
                        # No PDFs and no folders found
                        log_message(log_callback, "ABSOLUTELY NO ITEMS FOUND in this folder.", "CRITICAL")
                        log_message(log_callback, "1. Confirm the Folder ID is correct.", "CRITICAL")
                        log_message(log_callback, "2. Confirm you shared it with the Service Account Email.", "CRITICAL")
                        return
                except Exception as dbg_err:
                    log_message(log_callback, f"Flat folder check failed: {dbg_err}", "ERROR")
                    return
            # --- FLAT FOLDER MODE END ---

            for item in items:
                if stop_event.is_set():
                    break

                item_id = item['id']
                item_name = item['name']
                new_context = context_data.copy()
                
                if current_level < 5:
                    # Recursive traversal
                    levels = ["Academic Year", "Term", "Subject", "Book Type", "Release Year"]
                    log_message(log_callback, f"Entering {levels[current_level]}: {item_name}", "INFO")
                    
                    id_keys = ['academic_year_id', 'term_id', 'subject_id', 'book_type_id', 'release_year']
                    new_context[id_keys[current_level]] = item_name
                    
                    process_level(service, item_id, current_level + 1, new_context, processed_ids, log_callback, progress_callback, stop_event, config)
                    
                else:
                    # File Processing
                    if item_id in processed_ids:
                        progress_callback(skipped=1)
                        continue
                    
                    log_message(log_callback, f"Processing: {item_name}", "INFO")
                    
                    try:
                        temp_pdf_path = download_file(service, item_id, item_name)
                        meta = process_pdf(temp_pdf_path, item_id, item_name, log_callback)
                        
                        if os.path.exists(temp_pdf_path):
                            os.remove(temp_pdf_path)
                        
                        if meta:
                            record = {
                                "name": item_name,
                                "drive_file_id": item_id,
                                **new_context,
                                **meta
                            }
                            append_record(record)
                            processed_ids.add(item_id)
                            log_message(log_callback, f"Finished: {item_name}", "SUCCESS")
                            progress_callback(processed=1)
                        else:
                            log_message(log_callback, f"Failed metadata extraction: {item_name}", "ERROR")
                            progress_callback(errors=1)
                            
                    except Exception as exc:
                        log_message(log_callback, f"Error on file {item_name}: {exc}", "ERROR")
                        progress_callback(errors=1)

            page_token = results.get('nextPageToken')
            if not page_token:
                break
                
        except Exception as e:
            log_message(log_callback, f"Level {current_level} error: {e}", "ERROR")
            break

def start_scan_job(config, log_callback, progress_callback, stop_event):
    """
    Entry point for the background thread.
    """
    log_message(log_callback, "Starting scan job...", "INFO")
    
    # Setup Cloudinary
    try:
        cloudinary.config(
            cloud_name=config.get('cloudinary_cloud_name'),
            api_key=config.get('cloudinary_api_key'),
            api_secret=config.get('cloudinary_api_secret'),
            secure=True
        )
    except Exception as e:
        log_message(log_callback, f"Cloudinary Setup Error: {e}", "ERROR")
        return

    # Setup Google Drive
    try:
        service = get_drive_service(config.get('service_account_json'))
        log_message(log_callback, "Google Drive Authenticated.", "SUCCESS")
    except Exception as e:
        log_message(log_callback, f"Google Drive Auth Error: {e}", "CRITICAL")
        return

    processed_ids = load_processed_ids()
    log_message(log_callback, f"Loaded {len(processed_ids)} previously processed files.", "INFO")
    
    root_id = config.get('drive_root_id') or 'root'
    log_message(log_callback, f"Scanning from root ID: {root_id}", "INFO")
    
    process_level(service, root_id, 0, {}, processed_ids, log_callback, progress_callback, stop_event, config)
    
    log_message(log_callback, "Scan job finished.", "SUCCESS")
