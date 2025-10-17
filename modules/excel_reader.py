import pandas as pd
import os
from azure.storage.blob import BlobServiceClient
import tempfile

class ExcelReader:
    def __init__(self):
        self.excel_file_path = os.getenv('EXCEL_FILE_PATH')
        self.connection_string = os.getenv('AZURE_STORAGE_CONNECTION_STRING')
        
    def load_tracking_numbers(self):
        """Load tracking numbers from Excel file in blob storage"""
        
        # Download file from blob storage to temp location
        blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
        
        # Parse container and blob name from path
        parts = self.excel_file_path.split('/', 1)
        container_name = parts[0]
        blob_name = parts[1]
        
        # Download blob to temp file
        blob_client = blob_service_client.get_blob_client(container=container_name, blob=blob_name)
        
        with tempfile.NamedTemporaryFile(delete=False, suffix='.xlsm') as temp_file:
            download_stream = blob_client.download_blob()
            temp_file.write(download_stream.readall())
            temp_path = temp_file.name
        
        try:
            # Read Excel file
            df = pd.read_excel(temp_path, sheet_name='Your_Sheet_Name')  # Update sheet name
            
            # Process and return tracking numbers
            tracking_data = {}
            for index, row in df.iterrows():
                tracking_number = row.get('Tracking Number')  # Update column name
                if tracking_number:
                    tracking_data[tracking_number] = {
                        'pickup_date': row.get('Pickup Date'),
                        # Add other fields as needed
                    }
            
            return tracking_data
            
        finally:
            # Clean up temp file
            os.unlink(temp_path)
