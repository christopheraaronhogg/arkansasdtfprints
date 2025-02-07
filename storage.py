import os
import base64
from replit import db

class ObjectStorage:
    def __init__(self):
        """Initialize the storage with a namespace for our files"""
        self.namespace = "quickprints"
        if self.namespace not in db:
            db[self.namespace] = {}

    def upload_file(self, file_data, filename):
        """Upload a file to object storage"""
        try:
            # Convert binary data to base64 before storing
            key = f"{self.namespace}:{filename}"
            binary_data = file_data.read()
            base64_data = base64.b64encode(binary_data).decode('utf-8')
            db[key] = base64_data
            return True
        except Exception as e:
            print(f"Error uploading file to object storage: {e}")
            return False

    def get_file(self, filename):
        """Get a file from object storage"""
        try:
            key = f"{self.namespace}:{filename}"
            base64_data = db[key]
            return base64.b64decode(base64_data.encode('utf-8'))
        except Exception as e:
            print(f"Error retrieving file from object storage: {e}")
            return None

    def delete_file(self, filename):
        """Delete a file from object storage"""
        try:
            key = f"{self.namespace}:{filename}"
            del db[key]
            return True
        except Exception as e:
            print(f"Error deleting file from object storage: {e}")
            return False