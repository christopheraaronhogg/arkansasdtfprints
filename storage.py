import os
import base64
import logging
from replit import db

logger = logging.getLogger(__name__)

class ObjectStorage:
    def __init__(self):
        """Initialize the storage with a namespace for our files"""
        self.namespace = "quickprints"
        try:
            if self.namespace not in db:
                db[self.namespace] = {}
                logger.info(f"Initialized storage namespace: {self.namespace}")
        except Exception as e:
            logger.error(f"Error initializing storage: {str(e)}")

    def upload_file(self, file_data, filename):
        """Upload a file to object storage"""
        try:
            # Convert binary data to base64 before storing
            key = f"{self.namespace}:{filename}"
            binary_data = file_data.read()
            base64_data = base64.b64encode(binary_data).decode('utf-8')
            db[key] = base64_data
            logger.info(f"Successfully stored file {filename} in storage")
            return True
        except Exception as e:
            logger.error(f"Error uploading file to object storage: {str(e)}")
            return False

    def get_file(self, filename):
        """Get a file from object storage"""
        try:
            key = f"{self.namespace}:{filename}"
            base64_data = db[key]
            return base64.b64decode(base64_data.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error retrieving file from object storage: {str(e)}")
            return None

    def delete_file(self, filename):
        """Delete a file from object storage"""
        try:
            key = f"{self.namespace}:{filename}"
            del db[key]
            logger.info(f"Successfully deleted file {filename} from storage")
            return True
        except Exception as e:
            logger.error(f"Error deleting file from object storage: {str(e)}")
            return False