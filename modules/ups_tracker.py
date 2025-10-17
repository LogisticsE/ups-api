"""
UPS Tracker - Interface with UPS API
Reuses logic from existing application
"""

import requests
import logging
from typing import Dict, List, Any
import os
import time

class UPSTracker:
    def __init__(self):
        """Initialize UPS API client"""
        
        self.client_id = os.getenv('UPS_CLIENT_ID')
        self.client_secret = os.getenv('UPS_CLIENT_SECRET')
        self.base_url = "https://onlinetools.ups.com/api"
        
        if not self.client_id or not self.client_secret:
            raise ValueError("UPS API credentials not configured")
        
        self.access_token = None
        self.token_expiry = 0
    
    def _get_access_token(self) -> str:
        """Get OAuth access token from UPS"""
        
        current_time = time.time()
        
        # Reuse token if still valid
        if self.access_token and current_time < self.token_expiry:
            return self.access_token
        
        # Request new token
        auth_url = "https://onlinetools.ups.com/security/v1/oauth/token"
        
        response = requests.post(
            auth_url,
            headers={'Content-Type': 'application/x-www-form-urlencoded'},
            auth=(self.client_id, self.client_secret),
            data={'grant_type': 'client_credentials'}
        )
        
        response.raise_for_status()
        token_data = response.json()
        
        self.access_token = token_data['access_token']
        # FIX: Convert expires_in to int (UPS returns it as string)
        self.token_expiry = current_time + int(token_data['expires_in']) - 60  # 60s buffer
        
        return self.access_token
    
    def get_tracking_data(self, tracking_numbers: List[str]) -> Dict[str, Dict[str, Any]]:
        """
        Get tracking data from UPS API for multiple tracking numbers
        
        Args:
            tracking_numbers: List of UPS tracking numbers
            
        Returns:
            Dictionary with tracking_number as key and API response as value
        """
        
        results = {}
        token = self._get_access_token()
        
        for tracking_number in tracking_numbers:
            try:
                # Call UPS Tracking API
                url = f"{self.base_url}/track/v1/details/{tracking_number}"
                
                headers = {
                    'Authorization': f'Bearer {token}',
                    'transId': f'track_{tracking_number}',
                    'transactionSrc': 'AzureFunctionApp'
                }
                
                response = requests.get(url, headers=headers)
                
                if response.status_code == 200:
                    results[tracking_number] = response.json()
                    logging.info(f"✓ Retrieved tracking data for {tracking_number}")
                else:
                    logging.warning(f"⚠ API error for {tracking_number}: {response.status_code}")
                    results[tracking_number] = {'error': response.status_code}
                
                # Rate limiting - don't hammer the API
                time.sleep(0.2)
                
            except Exception as e:
                logging.error(f"✗ Error getting data for {tracking_number}: {str(e)}")
                results[tracking_number] = {'error': str(e)}
        
        return results