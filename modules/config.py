"""
Configuration constants
"""

import os

# UPS API Configuration
UPS_CLIENT_ID = os.getenv('UPS_CLIENT_ID', '')
UPS_CLIENT_SECRET = os.getenv('UPS_CLIENT_SECRET', '')
UPS_BASE_URL = "https://onlinetools.ups.com/api"

# Excel Configuration
EXCEL_FILE_PATH = os.getenv('EXCEL_FILE_PATH', '')

# Database Configuration
DATABASE_PATH = os.getenv('DATABASE_PATH', 'tracking_data.db')

# Update frequency (for reference)
UPDATE_SCHEDULE = "0 0 * * * *"  # Every hour