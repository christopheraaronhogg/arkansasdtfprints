import os
import zipfile
from storage import ObjectStorage

def upload_zip_contents():
    # Initialize storage with retry logic
    storage = ObjectStorage()

    # Zip file path
    zip_path = "DTF-9DD6A873-1_CAMP_QUALITY_-_LEFT_SLEEVE_-_BLACK_-_QTY_-_81_qty-81-min.zip"

    if not os.path.exists(zip_path):
        print(f"Error: Zip file not found at path: {zip_path}")
        return False

    total_files = 0
    successful_uploads = 0

    try:
        # Open and extract zip file contents
        with zipfile.ZipFile(zip_path, 'r') as zip_ref:
            total_files = len(zip_ref.filelist)
            print(f"Found {total_files} files in zip archive")

            # Iterate through each file in the zip
            for file_info in zip_ref.filelist:
                try:
                    # Read the file content
                    with zip_ref.open(file_info.filename) as file:
                        # Use the storage.upload_file method which includes retry logic
                        if storage.upload_file(file, file_info.filename):
                            successful_uploads += 1
                            print(f"Uploaded: {file_info.filename}")
                        else:
                            print(f"Failed to upload: {file_info.filename}")
                except Exception as e:
                    print(f"Error processing file {file_info.filename}: {str(e)}")

        print(f"\nUpload Summary:")
        print(f"Total files processed: {total_files}")
        print(f"Successfully uploaded: {successful_uploads}")
        print(f"Failed uploads: {total_files - successful_uploads}")

        return successful_uploads == total_files

    except Exception as e:
        print(f"Error processing zip file: {str(e)}")
        return False

if __name__ == "__main__":
    if upload_zip_contents():
        print("\nAll files uploaded successfully!")
    else:
        print("\nSome files failed to upload. Check the logs above for details.")