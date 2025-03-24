import os
import logging
from replit.object_storage import Client as ObjectStorageClient
import time

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)  # Changed from DEBUG to INFO to reduce logging overhead

BUCKET_ID = "replit-objstore-c3fb67d8-cc58-4f6a-8303-0ada7212ebd1"

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
                files = self.client.list()
                logger.info(f"Successfully initialized Replit Object Storage client for bucket: {BUCKET_ID}")
                logger.debug(f"Found {len(files)} files in bucket")
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
        """Upload a file to object storage with retry logic"""
        attempt = 0
        while attempt < self.max_retries:
            try:
                logger.debug(f"Attempting to upload file: {filename}")
                # Read file content
                file_content = file_data.read()
                # Upload using the client's method
                self.client.upload_from_bytes(filename, file_content)
                logger.info(f"Successfully uploaded file {filename} to storage")
                return True
            except Exception as e:
                attempt += 1
                if attempt < self.max_retries:
                    logger.warning(f"Failed to upload file (attempt {attempt}): {str(e)}")
                    time.sleep(self.retry_delay)
                    # Reset file pointer for next attempt
                    file_data.seek(0)
                else:
                    logger.error(f"Error uploading file to object storage after {self.max_retries} attempts: {str(e)}")
                    return False

    def get_file(self, filename):
        """Get a file from object storage with retry logic"""
        attempt = 0
        while attempt < self.max_retries:
            try:
                logger.debug(f"Attempting to retrieve file {filename}")
                # Download file content as bytes
                data = self.client.download_as_bytes(filename)
                logger.info(f"Successfully retrieved file {filename} from storage")
                return data
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

    def list_files(self):
        """List all files in the bucket"""
        try:
            files = self.client.list()
            logger.info(f"Successfully listed {len(files)} files from storage")
            return files
        except Exception as e:
            logger.error(f"Error listing files in storage: {str(e)}")
            return []