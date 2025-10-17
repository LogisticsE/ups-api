"""
Excel Reader - Load tracking numbers from Excel file
Updated to handle HaDEA Order Entry Excel format with multiple sheets and column variations
"""

import pandas as pd
import logging
from datetime import datetime
from typing import Dict, Any, List
import os

class ExcelReader:
    def __init__(self, excel_path: str = None):
        """
        Initialize Excel reader
        
        Args:
            excel_path: Path to Excel file (can be set via environment variable)
        """
        self.excel_path = excel_path or os.getenv('EXCEL_FILE_PATH')
        
        if not self.excel_path:
            raise ValueError("Excel file path not configured. Set EXCEL_FILE_PATH environment variable")
    
    def load_tracking_numbers(self) -> Dict[str, Dict[str, Any]]:
        """
        Load tracking numbers from all relevant sheets in HaDEA Order Entry Excel file
        
        Returns:
            Dictionary with tracking_number as key and row data as value
        """
        
        logging.info(f"Reading Excel file: {self.excel_path}")
        
        try:
            # Load Excel file to check sheets
            excel_file = pd.ExcelFile(self.excel_path, engine='openpyxl')
            
            logging.info(f"✓ Found sheets: {excel_file.sheet_names}")
            
            # Define which sheets to read
            sheets_to_read = []
            for sheet_name in excel_file.sheet_names:
                sheet_lower = sheet_name.lower()
                # Read sheets that contain tracking data
                if any(keyword in sheet_lower for keyword in ['outbound', 'sample', 'inbound', 'shipment']):
                    sheets_to_read.append(sheet_name)
            
            if not sheets_to_read:
                logging.warning("No specific sheets found, reading all sheets")
                sheets_to_read = excel_file.sheet_names
            
            logging.info(f"📊 Reading sheets: {sheets_to_read}")
            
            # Combine tracking data from all sheets
            all_tracking_data = {}
            
            for sheet_name in sheets_to_read:
                logging.info(f"Processing sheet: {sheet_name}")
                sheet_data = self._read_sheet(sheet_name)
                
                # Merge with existing data
                all_tracking_data.update(sheet_data)
                logging.info(f"  ✓ Added {len(sheet_data)} tracking numbers from '{sheet_name}'")
            
            logging.info(f"✅ Total: {len(all_tracking_data)} tracking numbers from {len(sheets_to_read)} sheet(s)")
            
            return all_tracking_data
            
        except Exception as e:
            logging.error(f"✗ Error reading Excel file: {str(e)}")
            raise
    
    def _read_sheet(self, sheet_name: str) -> Dict[str, Dict[str, Any]]:
        """
        Read tracking numbers from a single sheet
        
        Args:
            sheet_name: Name of the sheet to read
            
        Returns:
            Dictionary with tracking numbers from this sheet
        """
        
        try:
            # Try different header rows
            for header_row in [3, 2, 1, 0]:
                try:
                    df = pd.read_excel(
                        self.excel_path, 
                        sheet_name=sheet_name,
                        engine='openpyxl',
                        header=header_row
                    )
                    
                    # Check if this row contains WAYBILLNUMBER
                    if 'WAYBILLNUMBER' in df.columns:
                        logging.info(f"  Found headers at row {header_row} in sheet '{sheet_name}'")
                        break
                except:
                    continue
            else:
                logging.warning(f"  Could not find WAYBILLNUMBER column in sheet '{sheet_name}', skipping")
                return {}
            
            # Identify which pickup date column to use
            pickup_date_column = None
            if 'Shipping Date (SD-14)' in df.columns:
                pickup_date_column = 'Shipping Date (SD-14)'
            elif 'Confirmed Pick-up Date' in df.columns:
                pickup_date_column = 'Confirmed Pick-up Date'
            else:
                logging.warning(f"  No pickup date column found in sheet '{sheet_name}', skipping")
                return {}
            
            logging.info(f"  Using pickup date column: '{pickup_date_column}'")
            
            # Convert to dictionary
            tracking_data = {}
            
            for _, row in df.iterrows():
                # Get tracking numbers (can be multiple, separated by semicolons)
                waybill_str = str(row['WAYBILLNUMBER']).strip()
                
                # Skip empty rows
                if not waybill_str or waybill_str.lower() == 'nan':
                    continue
                
                # Split multiple tracking numbers
                tracking_numbers = [tn.strip() for tn in waybill_str.split(';') if tn.strip()]
                
                # Parse pickup date
                pickup_date = row[pickup_date_column]
                
                # Handle different date formats
                if pd.isna(pickup_date):
                    continue
                elif isinstance(pickup_date, str):
                    try:
                        pickup_date = datetime.strptime(pickup_date, '%Y-%m-%d').date()
                    except ValueError:
                        try:
                            pickup_date = datetime.strptime(pickup_date, '%d-%m-%Y').date()
                        except ValueError:
                            continue
                elif hasattr(pickup_date, 'date'):
                    pickup_date = pickup_date.date()
                else:
                    continue
                
                # Build destination from CITY + COUNTRY
                city = str(row.get('CITY', '')).strip() if pd.notna(row.get('CITY')) else ''
                country = str(row.get('COUNTRY', '')).strip() if pd.notna(row.get('COUNTRY')) else ''
                destination = f"{city}, {country}" if city and country else (city or country or '')
                
                # Get other fields (column names vary by sheet)
                reference_number = str(row.get('ID', '')).strip() if pd.notna(row.get('ID')) else ''
                
                # Shipper info - different columns in different sheets
                shipper_info = ''
                if pd.notna(row.get('ToSite-UPSName')):
                    shipper_info = str(row.get('ToSite-UPSName', '')).strip()
                elif pd.notna(row.get('FromSite-UPS')):
                    shipper_info = str(row.get('FromSite-UPS', '')).strip()
                
                # Site name - different columns
                site_name = ''
                if pd.notna(row.get('ToSite-HaDEAName')):
                    site_name = str(row.get('ToSite-HaDEAName', '')).strip()
                elif pd.notna(row.get('FromSiteName')):
                    site_name = str(row.get('FromSiteName', '')).strip()
                
                # Add each tracking number with the same row data
                for tracking_number in tracking_numbers:
                    if len(tracking_number) < 10:  # Skip invalid tracking numbers
                        continue
                    
                    tracking_data[tracking_number] = {
                        'tracking_number': tracking_number,
                        'planned_pickup_date': pickup_date,
                        'destination': destination,
                        'reference_number': reference_number,
                        'shipper_info': shipper_info,
                        'sheet_name': sheet_name,
                        # Store additional fields
                        'city': city,
                        'country': country,
                        'delivery_address': str(row.get('DELIVERYADDRESS', row.get('deliveryadres', ''))).strip() if pd.notna(row.get('DELIVERYADDRESS', row.get('deliveryadres', ''))) else '',
                        'expected_delivery': row.get('EXPECTEDDELIVERYDATE'),
                        'site_name': site_name,
                        'type': str(row.get('Type', '')).strip() if pd.notna(row.get('Type')) else '',
                        'quantity': str(row.get('Quantity', '')).strip() if pd.notna(row.get('Quantity')) else ''
                    }
            
            return tracking_data
            
        except Exception as e:
            logging.warning(f"  Error reading sheet '{sheet_name}': {str(e)}")
            return {}
