# A Una Milla de Tu Destino — Backend (HP-backend)

FastAPI backend service for **"A Una Milla de Tu Destino"**, a travel-hacking proof of concept (POC).

---

## 🏗 Project Architecture

- **Backend Framework:** Python 3.11+ with FastAPI & Uvicorn
- **API Pattern:** Modular routers (`app/routers/`), isolated provider service integrations (`app/services/`), and typed Pydantic models (`app/models/`)
- **Configuration:** Managed via Pydantic Settings and environment variables (`.env`)
- **Deployment Target:** Render (Web Service)
- **Frontend Target:** React + Vite deployed independently on Vercel

---

## 📁 Repository Structure

```
HP-backend/
├── app/
│   ├── __init__.py           # Package root
│   ├── main.py               # FastAPI initialization, CORS middleware, router registration
│   ├── config.py             # Settings loader, CORS parsing, production safety checks
│   ├── models/
│   │   ├── __init__.py
│   │   └── flights.py        # Pydantic request & response schemas for flight search
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── health.py         # GET /health endpoint for Render uptime monitoring
│   │   └── flights.py        # POST /api/v1/flights/cash endpoint
│   └── services/
│       ├── __init__.py
│       └── duffel.py         # Duffel API v2 HTTP client integration & response parsing
├── tests/
│   ├── __init__.py
│   ├── test_health.py        # Health check unit test
│   └── test_flights.py       # Mocked Duffel tests (success, errors, timeouts, validation)
├── .env.example              # Template for environment variables
├── .gitignore                # Excludes secrets, virtual environments, cache
├── render.yaml               # Render Infrastructure-as-Code deployment blueprint
├── requirements.txt          # Python package dependencies
└── README.md                 # Setup and deployment documentation
```

---

## 🚀 Local Development Setup

### 1. Prerequisites
- **Python 3.11 or higher** installed.

### 2. Create and Activate a Virtual Environment

**On Windows (PowerShell):**
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

*(If using `uv`: `uv venv .venv --python 3.11` then `.\.venv\Scripts\Activate.ps1`)*

**On macOS / Linux:**
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the `.env.example` file to create your local `.env`:

**Windows (PowerShell):**
```powershell
Copy-Item .env.example .env
```

**macOS / Linux:**
```bash
cp .env.example .env
```

In `.env`, configure your settings:
```env
ENVIRONMENT=development
PORT=8000
ALLOWED_ORIGINS=http://localhost:5173,http://127.0.0.1:5173
DUFFEL_API_KEY=duffel_test_your_token_here
```

### 5. Run the Local Server
```bash
uvicorn app.main:app --reload --port 8000
```

Once running:
- **API Base:** [http://127.0.0.1:8000](http://127.0.0.1:8000)
- **Health Check:** [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health)
- **Interactive API Docs (Swagger):** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## ✈️ API Endpoints

### 1. Health Check
- **Endpoint:** `GET /health`
- **Response:**
  ```json
  {
    "status": "ok"
  }
  ```

---

### 2. Cash Flight Search (Duffel API v2)
- **Endpoint:** `POST /api/v1/flights/cash`
- **Summary:** Searches live/test cash flight offers through Duffel without fabricating prices or availability.
- **Headers:** `Content-Type: application/json`

#### Request Parameters
| Field | Type | Required | Description |
|---|---|---|---|
| `origin` | `string` | **Yes** | 3-letter IATA code (e.g. `"JFK"`). Auto-uppercased. |
| `destination` | `string` | **Yes** | 3-letter IATA code (e.g. `"LHR"`). Must differ from origin. |
| `departure_date` | `string` (date) | **Yes** | YYYY-MM-DD. Cannot be in the past. |
| `return_date` | `string` (date) | No | YYYY-MM-DD. For round-trips. Must be on or after departure date. |
| `passengers` | `integer` | No | Adult count between 1 and 9 (default: `1`). |
| `cabin_class` | `string` | No | `"economy"`, `"premium_economy"`, `"business"`, or `"first"` (default: `"economy"`). |

#### Example Request Body (One-Way)
```json
{
  "origin": "JFK",
  "destination": "LHR",
  "departure_date": "2026-11-15",
  "passengers": 1,
  "cabin_class": "economy"
}
```

#### Example Request Body (Round-Trip)
```json
{
  "origin": "JFK",
  "destination": "MAD",
  "departure_date": "2026-11-15",
  "return_date": "2026-11-25",
  "passengers": 2,
  "cabin_class": "business"
}
```

#### Example Response Body
```json
{
  "search_id": "orq_0000BBoYyuVSBL129Q8c8z",
  "total_offers": 1,
  "provider": "duffel",
  "offers": [
    {
      "id": "off_034mnQ1d7mJXnqZ0uZyfR2",
      "total_price": 219.04,
      "total_amount": "219.04",
      "currency": "EUR",
      "airline_name": "American Airlines",
      "airline_code": "AA",
      "provider": "duffel",
      "slices": [
        {
          "id": "sli_0000BBoY...",
          "origin": {
            "iata_code": "JFK",
            "name": "John F. Kennedy International Airport",
            "city_name": "New York"
          },
          "destination": {
            "iata_code": "LHR",
            "name": "Heathrow Airport",
            "city_name": "London"
          },
          "duration": "PT7H58M",
          "segments": [
            {
              "id": "seg_0000BBoY...",
              "origin": {
                "iata_code": "JFK",
                "name": "John F. Kennedy International Airport",
                "city_name": "New York"
              },
              "destination": {
                "iata_code": "LHR",
                "name": "Heathrow Airport",
                "city_name": "London"
              },
              "departing_at": "2026-11-15T18:00:00",
              "arriving_at": "2026-11-16T06:58:00",
              "carrier_name": "American Airlines",
              "carrier_code": "AA",
              "flight_number": "100",
              "duration": "PT7H58M"
            }
          ]
        }
      ]
    }
  ]
}
```

#### Error Responses
- **`400 Bad Request`**: Downstream airline/provider rejected search parameters (e.g. no routes operated).
- **`422 Unprocessable Entity`**: Invalid request format (e.g., origin equals destination, past date, invalid airport code).
- **`502 Bad Gateway`**: Upstream Duffel provider network or schema issue.
- **`503 Service Unavailable`**: `DUFFEL_API_KEY` is not configured in backend environment.
- **`504 Gateway Timeout`**: Upstream Duffel search timed out (sensible 25-second limit).

---

## 🧪 Running Automated Tests

A comprehensive test suite is included in `tests/` featuring mocked Duffel HTTP responses so **no live token is required**:

```bash
pytest -v
```

Tests verify:
- Health check `GET /health` returns HTTP 200.
- Successful one-way and round-trip payload parsing.
- Input validation (invalid IATA codes, identical origin/destination, past dates, invalid passenger numbers).
- Error isolation (missing credentials 503, provider 400, timeout 504, network error 502, malformed response 502).
- Security assertion ensuring API keys or `Authorization` headers are never leaked in response text.

---

## 🌐 Connecting the React + Vite Frontend (CORS)

### Local Development
The default settings allow `http://localhost:5173` (Vite's default port). When running `npm run dev` in your frontend directory, requests are accepted automatically.

### Production (Vercel)
When deploying your React app on Vercel:
1. In your Render backend dashboard, update `ALLOWED_ORIGINS`:
   ```env
   ALLOWED_ORIGINS=https://your-frontend-app.vercel.app
   ```
2. In production mode (`ENVIRONMENT=production`), the backend strictly rejects wildcard `*` origins to protect against cross-origin attacks.

---

## ☁️ Deploying to Render

### Option A: Using `render.yaml` (Recommended)
1. Push this repository to GitHub.
2. In Render, create a new **Blueprint** and connect your `HP-backend` repository.
3. Render will configure the service automatically.

### Option B: Manual Web Service Setup on Render
1. Create a **New Web Service** and select your GitHub repository.
2. Configure settings:
   - **Environment:** `Python`
   - **Build Command:** `pip install -r requirements.txt`
   - **Start Command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
   - **Health Check Path:** `/health`
3. Add Environment Variables in the Render dashboard:
   - `ENVIRONMENT`: `production`
   - `ALLOWED_ORIGINS`: `https://your-frontend-app.vercel.app`
   - `DUFFEL_API_KEY`: `duffel_test_...` or `duffel_live_...`

---

## 🔒 Security Best Practices
- **No Hardcoded Secrets:** API keys and sensitive credentials remain in `.env` (locally) or Render environment settings (production).
- **Never Log Secrets:** Endpoints and logging handlers never dump raw environment variables or auth tokens.
- **Service Isolation:** External providers (like Duffel) reside exclusively in `app/services/` behind domain interfaces.
