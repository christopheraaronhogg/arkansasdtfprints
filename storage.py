import os
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
            # Store the file data in the database under our namespace
            key = f"{self.namespace}:{filename}"
            db[key] = file_data.read()
            return True
        except Exception as e:
            print(f"Error uploading file to object storage: {e}")
            return False

    def get_file(self, filename):
        """Get a file from object storage"""
        try:
            key = f"{self.namespace}:{filename}"
            return db[key]
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