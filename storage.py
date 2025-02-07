import os
import base64
import logging
from replit import db

logger = logging.getLogger(__name__)

class ObjectStorage:
    def __init__(self):
        """Initialize the storage with a namespace for our files"""
        try:
            self.namespace = "quickprints"
            # Initialize the namespace if it doesn't exist
            if self.namespace not in db.keys():
                db[self.namespace] = {}
                logger.info(f"Created new storage namespace: {self.namespace}")
            else:
                logger.info(f"Using existing storage namespace: {self.namespace}")
        except Exception as e:
            logger.error(f"Storage initialization error: {str(e)}")
            raise RuntimeError(f"Failed to initialize storage: {str(e)}")

    def upload_file(self, file_data, filename):
        """Upload a file to object storage"""
        try:
            # Convert binary data to base64 before storing
            key = f"{self.namespace}:{filename}"
            binary_data = file_data.read()
            base64_data = base64.b64encode(binary_data).decode('utf-8')

            # Store in Replit DB
            logger.debug(f"Attempting to store file {filename} with key {key}")
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
            logger.debug(f"Attempting to retrieve file {filename} with key {key}")

            if key not in db.keys():
                logger.error(f"File {filename} not found in storage")
                return None

            base64_data = db[key]
            return base64.b64decode(base64_data.encode('utf-8'))
        except Exception as e:
            logger.error(f"Error retrieving file from object storage: {str(e)}")
            return None

    def delete_file(self, filename):
        """Delete a file from object storage"""
        try:
            key = f"{self.namespace}:{filename}"
            if key not in db.keys():
                logger.error(f"File {filename} not found in storage")
                return False

            del db[key]
            logger.info(f"Successfully deleted file {filename} from storage")
            return True
        except Exception as e:
            logger.error(f"Error deleting file from object storage: {str(e)}")
            return False