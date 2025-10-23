# UPS Tracking API

Azure Functions-based API for tracking UPS shipments with agent-friendly query capabilities.

## Features

- Automatic hourly UPS tracking updates
- Azure Table Storage for reliable data persistence
- Excel integration for bulk tracking number import
- RESTful API endpoints
- **NEW: Agent-friendly natural language query interface**

## API Endpoints

### 1. Health Check
```
GET /health
```
Returns API health status and database statistics.

### 2. Get Tracking Status
```
GET /tracking/{tracking_number}
```
Retrieve detailed information for a specific tracking number.

**Example:**
```bash
curl https://your-function-app.azurewebsites.net/api/tracking/1Z999AA10123456784
```

### 3. Agent Query (NEW!)
```
GET /agent/query
POST /agent/query
```

**Agent-friendly endpoint for flexible shipment searches with natural language responses.**

#### Query Parameters

| Parameter | Type | Description | Examples |
|-----------|------|-------------|----------|
| `destination` | string | Search by destination city/country | "Frankfurt", "Germany" |
| `tracking_number` | string | Specific tracking number | "1Z999AA10123456784" |
| `reference_number` | string | Reference/PO number | "PO-12345" |
| `status` | string | Filter by shipment status | "Delivered", "In Transit" |
| `date_from` | string | Start date for filtering | "today", "yesterday", "2025-01-15" |
| `date_to` | string | End date for filtering | "today", "2025-01-20" |
| `limit` | integer | Max results (default: 100) | 50 |

#### Example Queries

**1. Find all Frankfurt shipments today:**
```bash
curl "https://your-function-app.azurewebsites.net/api/agent/query?destination=Frankfurt&date_from=today"
```

**2. Find all in-transit shipments:**
```bash
curl "https://your-function-app.azurewebsites.net/api/agent/query?status=In%20Transit"
```

**3. Using POST with JSON:**
```bash
curl -X POST https://your-function-app.azurewebsites.net/api/agent/query \
  -H "Content-Type: application/json" \
  -d '{
    "destination": "Frankfurt",
    "date_from": "today",
    "status": "Delivered"
  }'
```

#### Response Format

```json
{
  "success": true,
  "count": 2,
  "message": "I found 2 shipments matching your query:\n• Delivered: 2 shipment(s)",
  "query": "destination='Frankfurt', from='today'",
  "shipments": [
    {
      "tracking_number": "1Z999AA10123456784",
      "destination": "Frankfurt, Germany",
      "status": "Delivered",
      "ups_status": "Delivered",
      "reference_number": "PO-12345",
      "shipper_info": "Company Name",
      "planned_pickup_date": "2025-01-20",
      "estimated_delivery_date": "2025-01-22",
      "actual_delivery_date": "2025-01-22",
      "actual_delivery_time": "14:30:00",
      "last_updated": "2025-01-22T14:35:00",
      "days_since_pickup": 2,
      "days_until_pickup": null
    }
  ],
  "status_breakdown": {
    "Delivered": 2
  }
}
```

### 4. Manual Trigger
```
POST /trigger
```
Manually trigger an immediate tracking update (for testing).

## Agent Integration Examples

### Example 1: Natural Language Query
**User asks:** "What happened to my Frankfurt shipment today?"

**Agent calls:**
```
GET /agent/query?destination=Frankfurt&date_from=today
```

**Response includes:**
- Natural language summary
- List of matching shipments
- Status breakdown
- Full shipment details

### Example 2: Status Check
**User asks:** "Show me all delivered packages"

**Agent calls:**
```
GET /agent/query?status=Delivered
```

### Example 3: Time-based Query
**User asks:** "What shipments were updated yesterday?"

**Agent calls:**
```
GET /agent/query?date_from=yesterday&date_to=yesterday
```

## Date Format Support

The agent query endpoint supports multiple date formats:
- **Relative:** "today", "yesterday", "this week", "last week"
- **ISO format:** "2025-01-22"
- **Common formats:** "22/01/2025", "01/22/2025", "2025/01/22"

## Status Types

The system tracks the following internal statuses:
- Delivered
- In Transit
- Out for Delivery
- Exception
- Held at Facility
- Picked Up
- Origin Scan
- Departure Scan
- Arrival Scan
- Destination Scan
- Order Processed
- Label Created
- Return to Sender
- Delivered (Damaged)
- Unknown

## Architecture

- **Azure Functions:** Serverless compute
- **Azure Table Storage:** Persistent data storage
- **UPS Tracking API:** Real-time tracking data
- **Timer Trigger:** Hourly automatic updates

## Configuration

Set these environment variables in Azure Function App settings or `local.settings.json`:

```json
{
  "IsEncrypted": false,
  "Values": {
    "AzureWebJobsStorage": "your-storage-connection-string",
    "FUNCTIONS_WORKER_RUNTIME": "python",
    "UPS_CLIENT_ID": "your-ups-client-id",
    "UPS_CLIENT_SECRET": "your-ups-client-secret",
    "AZURE_STORAGE_CONNECTION_STRING": "your-storage-connection-string",
    "EXCEL_FILE_PATH": "/path/to/HaDEA_Order_Entry.xlsx"
  }
}
```

## Development

### Local Testing
```bash
# Install dependencies
pip install -r requirements.txt

# Run locally
func start
```

### Deploy to Azure
```bash
func azure functionapp publish your-function-app-name
```

## Version

v2.0.0 - Added agent query interface
