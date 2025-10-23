"""
Agent Query Processor for UPS Tracking API
Handles natural language and structured queries for shipment tracking.
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from azure.data.tables import TableServiceClient
from azure.core.exceptions import ResourceNotFoundError


class AgentQueryProcessor:
    """Process agent queries for shipment tracking information."""

    def __init__(self, table_storage_manager):
        """
        Initialize the agent query processor.

        Args:
            table_storage_manager: Instance of TableStorageManager
        """
        self.storage = table_storage_manager
        self.logger = logging.getLogger(__name__)

    def query_shipments(
        self,
        destination: Optional[str] = None,
        tracking_number: Optional[str] = None,
        reference_number: Optional[str] = None,
        status: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """
        Query shipments based on various criteria.

        Args:
            destination: Destination location (e.g., "Frankfurt", "Germany")
            tracking_number: Specific UPS tracking number
            reference_number: Reference/PO number
            status: Internal status (e.g., "Delivered", "In Transit")
            date_from: Start date for filtering (YYYY-MM-DD or "today", "yesterday")
            date_to: End date for filtering (YYYY-MM-DD or "today")
            limit: Maximum number of results to return

        Returns:
            List of matching shipment records
        """
        self.logger.info(
            f"Query: destination={destination}, tracking={tracking_number}, "
            f"reference={reference_number}, status={status}, "
            f"date_from={date_from}, date_to={date_to}"
        )

        # If tracking number is provided, do direct lookup
        if tracking_number:
            record = self.storage.get_tracking_record(tracking_number)
            if record:
                return [self._format_record(record)]
            return []

        # Otherwise, fetch all records and filter
        all_records = self.storage.get_all_tracking_records()
        filtered = []

        # Parse date filters
        from_date = self._parse_date(date_from) if date_from else None
        to_date = self._parse_date(date_to) if date_to else None

        for record in all_records:
            # Apply filters
            if destination and not self._matches_destination(record, destination):
                continue

            if reference_number and not self._matches_reference(record, reference_number):
                continue

            if status and not self._matches_status(record, status):
                continue

            if from_date or to_date:
                if not self._matches_date_range(record, from_date, to_date):
                    continue

            filtered.append(self._format_record(record))

            if len(filtered) >= limit:
                break

        self.logger.info(f"Found {len(filtered)} matching shipments")
        return filtered

    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string into datetime object."""
        if not date_str:
            return None

        date_str = date_str.lower().strip()
        today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)

        # Handle relative dates
        if date_str == "today":
            return today
        elif date_str == "yesterday":
            return today - timedelta(days=1)
        elif date_str == "this week":
            return today - timedelta(days=today.weekday())
        elif date_str == "last week":
            return today - timedelta(days=today.weekday() + 7)

        # Try parsing ISO format
        try:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        except:
            pass

        # Try common date formats
        for fmt in ["%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%Y/%m/%d"]:
            try:
                return datetime.strptime(date_str, fmt)
            except:
                continue

        self.logger.warning(f"Could not parse date: {date_str}")
        return None

    def _matches_destination(self, record: Dict, destination: str) -> bool:
        """Check if record matches destination filter."""
        dest = record.get('destination', '').lower()
        search = destination.lower()
        return search in dest

    def _matches_reference(self, record: Dict, reference: str) -> bool:
        """Check if record matches reference number filter."""
        ref = record.get('reference_number', '').lower()
        search = reference.lower()
        return search in ref

    def _matches_status(self, record: Dict, status: str) -> bool:
        """Check if record matches status filter."""
        internal_status = record.get('internal_status', '').lower()
        ups_status = record.get('ups_status', '').lower()
        search = status.lower()
        return search in internal_status or search in ups_status

    def _matches_date_range(
        self,
        record: Dict,
        from_date: Optional[datetime],
        to_date: Optional[datetime]
    ) -> bool:
        """Check if record falls within date range."""
        # Check multiple date fields
        date_fields = [
            'last_updated',
            'actual_delivery_date',
            'estimated_delivery_date',
            'planned_pickup_date'
        ]

        for field in date_fields:
            date_str = record.get(field)
            if not date_str:
                continue

            try:
                record_date = self._parse_date(date_str)
                if not record_date:
                    continue

                if from_date and record_date < from_date:
                    continue
                if to_date and record_date > to_date:
                    continue

                return True
            except:
                continue

        return False

    def _format_record(self, record: Dict) -> Dict[str, Any]:
        """Format a record for agent response."""
        return {
            'tracking_number': record.get('tracking_number', 'N/A'),
            'destination': record.get('destination', 'N/A'),
            'status': record.get('internal_status', 'Unknown'),
            'ups_status': record.get('ups_status', 'N/A'),
            'reference_number': record.get('reference_number', 'N/A'),
            'shipper_info': record.get('shipper_info', 'N/A'),
            'planned_pickup_date': record.get('planned_pickup_date', 'N/A'),
            'estimated_delivery_date': record.get('estimated_delivery_date', 'N/A'),
            'actual_delivery_date': record.get('actual_delivery_date', 'N/A'),
            'actual_delivery_time': record.get('actual_delivery_time', 'N/A'),
            'last_updated': record.get('last_updated', 'N/A'),
            'days_since_pickup': record.get('days_since_pickup'),
            'days_until_pickup': record.get('days_until_pickup'),
        }


class AgentResponseFormatter:
    """Format shipment data into natural language responses."""

    @staticmethod
    def format_response(shipments: List[Dict[str, Any]], query_summary: str = "") -> Dict[str, Any]:
        """
        Format shipments into an agent-friendly response.

        Args:
            shipments: List of shipment records
            query_summary: Summary of the query for context

        Returns:
            Formatted response with natural language summary
        """
        if not shipments:
            return {
                'success': True,
                'count': 0,
                'message': 'No shipments found matching your query.',
                'query': query_summary,
                'shipments': []
            }

        # Generate natural language summary
        summary_parts = []

        if len(shipments) == 1:
            shipment = shipments[0]
            summary_parts.append(f"I found 1 shipment matching your query:")
            summary_parts.append(
                f"• Tracking #{shipment['tracking_number']} to {shipment['destination']}"
            )
            summary_parts.append(f"  Status: {shipment['status']}")

            if shipment['actual_delivery_date'] != 'N/A':
                summary_parts.append(
                    f"  Delivered: {shipment['actual_delivery_date']} at {shipment['actual_delivery_time']}"
                )
            elif shipment['estimated_delivery_date'] != 'N/A':
                summary_parts.append(
                    f"  Estimated delivery: {shipment['estimated_delivery_date']}"
                )
        else:
            # Group by status
            status_groups = {}
            for shipment in shipments:
                status = shipment['status']
                if status not in status_groups:
                    status_groups[status] = []
                status_groups[status].append(shipment)

            summary_parts.append(f"I found {len(shipments)} shipments matching your query:")

            for status, group in sorted(status_groups.items()):
                summary_parts.append(f"• {status}: {len(group)} shipment(s)")

        return {
            'success': True,
            'count': len(shipments),
            'message': '\n'.join(summary_parts),
            'query': query_summary,
            'shipments': shipments,
            'status_breakdown': AgentResponseFormatter._get_status_breakdown(shipments)
        }

    @staticmethod
    def _get_status_breakdown(shipments: List[Dict[str, Any]]) -> Dict[str, int]:
        """Get a count of shipments by status."""
        breakdown = {}
        for shipment in shipments:
            status = shipment['status']
            breakdown[status] = breakdown.get(status, 0) + 1
        return breakdown
