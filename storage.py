import os
import logging
from replit.object_storage import Client as ObjectStorageClient
import time

logger = logging.getLogger(__name__)

BUCKET_ID = "replit-objstore-b9495cba-12af-4e41-8388-3c12c11e5b8a"

class ObjectStorage:
    def __init__(self, max_retries=3, retry_delay=1):
        """Initialize object storage client with retry logic"""
        self.max_retries = max_retries
        self.retry_delay = retry_delay
        self._init_client()

    def _init_client(self):
        """Initialize the client with retry logic"""
        attempt = 0
        last_error = None

        while attempt < self.max_retries:
            try:
                # Initialize with specific bucket ID
                self.client = ObjectStorageClient(bucket_id=BUCKET_ID)
                # Test the connection by listing bucket contents
                self.client.list()
                logger.info(f"Successfully initialized Replit Object Storage client for bucket: {BUCKET_ID}")
                return
            except Exception as e:
                last_error = e
                attempt += 1
                if attempt < self.max_retries:
                    logger.warning(f"Failed to initialize storage (attempt {attempt}): {str(e)}")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Failed to initialize Replit Object Storage client after {self.max_retries} attempts: {str(e)}")
                    raise RuntimeError(f"Failed to initialize storage: {str(e)}")

    def upload_file(self, file_data, filename):
        """Upload a file to object storage with retry logic and improved streaming"""
        attempt = 0
        total_size = 0
        CHUNK_SIZE = 10 * 1024 * 1024  # 10MB chunks to match frontend
        
        while attempt < self.max_retries:
            try:
                # Stream upload with progress tracking
                uploader = self.client.get_uploader(filename)
                
                while True:
                    chunk = file_data.read(CHUNK_SIZE)
                    if not chunk:
                        break
                        
                    uploader.upload_chunk(chunk)
                    total_size += len(chunk)
                    logger.debug(f"Uploaded chunk of {len(chunk)} bytes for {filename}. Total: {total_size} bytes")
                
                uploader.finish()
                logger.info(f"Successfully uploaded file {filename} to storage ({total_size} bytes)")
                return True
                
            except Exception as e:
                attempt += 1
                logger.error(f"Upload attempt {attempt} failed for {filename}: {str(e)}")
                if attempt < self.max_retries:
                    logger.warning(f"Retrying upload in {self.retry_delay} seconds...")
                    time.sleep(self.retry_delay)
                    file_data.seek(0)  # Reset file pointer for retry
                    total_size = 0  # Reset size counter
                else:
                    logger.error(f"Failed to upload {filename} after {self.max_retries} attempts")
                    return False

    def get_file(self, filename):
        """Get a file from object storage with retry logic"""
        attempt = 0
        while attempt < self.max_retries:
            try:
                logger.debug(f"Attempting to retrieve file {filename}")
                # Download file content as bytes
                return self.client.download_as_bytes(filename)
            except Exception as e:
                attempt += 1
                if attempt < self.max_retries:
                    logger.warning(f"Failed to retrieve file (attempt {attempt}): {str(e)}")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Error retrieving file from object storage after {self.max_retries} attempts: {str(e)}")
                    return None

    def delete_file(self, filename):
        """Delete a file from object storage with retry logic"""
        attempt = 0
        while attempt < self.max_retries:
            try:
                self.client.delete(filename)
                logger.info(f"Successfully deleted file {filename} from storage")
                return True
            except Exception as e:
                attempt += 1
                if attempt < self.max_retries:
                    logger.warning(f"Failed to delete file (attempt {attempt}): {str(e)}")
                    time.sleep(self.retry_delay)
                else:
                    logger.error(f"Error deleting file from object storage after {self.max_retries} attempts: {str(e)}")
                    return False

    def delete_file_no_retry(self, filename):
        """Delete a file from object storage without retries"""
        try:
            self.client.delete(filename)
            logger.info(f"Successfully deleted file {filename} from storage")
            return True
        except Exception as e:
            logger.warning(f"Could not delete file {filename}: {str(e)}")
            return False

    def list_files(self):
        """List all files in the bucket"""
        try:
            return self.client.list()
        except Exception as e:
            logger.error(f"Error listing files in storage: {str(e)}")
            return []