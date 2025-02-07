import os
import logging
from replit.object_storage import Client as ObjectStorageClient

logger = logging.getLogger(__name__)

class ObjectStorage:
    def __init__(self):
        """Initialize object storage client"""
        try:
            self.client = ObjectStorageClient()  # connects to default bucket
            logger.info("Successfully initialized Replit Object Storage client")
        except Exception as e:
            logger.error(f"Failed to initialize Replit Object Storage client: {str(e)}")
            raise RuntimeError(f"Failed to initialize storage: {str(e)}")

    def upload_file(self, file_data, filename):
        """Upload a file to object storage"""
        try:
            # Read file content
            file_content = file_data.read()
            # Upload using the client's method
            self.client.upload_from_bytes(filename, file_content)
            logger.info(f"Successfully uploaded file {filename} to storage")
            return True
        except Exception as e:
            logger.error(f"Error uploading file to object storage: {str(e)}")
            return False

    def get_file(self, filename):
        """Get a file from object storage"""
        try:
            logger.debug(f"Attempting to retrieve file {filename}")
            # Download file content as bytes
            return self.client.download_as_bytes(filename)
        except Exception as e:
            logger.error(f"Error retrieving file from object storage: {str(e)}")
            return None

    def delete_file(self, filename):
        """Delete a file from object storage"""
        try:
            self.client.delete(filename)
            logger.info(f"Successfully deleted file {filename} from storage")
            return True
        except Exception as e:
            logger.error(f"Error deleting file from object storage: {str(e)}")
            return False