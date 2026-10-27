from datetime import date, timedelta
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient

from app.config import Settings, get_settings
from app.main import app
from app.routers.flights import get_duffel_service
from app.services.duffel import DuffelService

client = TestClient(app)

FUTURE_DEPARTURE = (date.today() + timedelta(days=30)).isoformat()
FUTURE_RETURN = (date.today() + timedelta(days=37)).isoformat()
PAST_DATE = (date.today() - timedelta(days=5)).isoformat()

MOCK_DUFFEL_SUCCESS = {
    "data": {
        "id": "orq_mock_001",
        "live_mode": False,
        "cabin_class": "economy",
        "offers": [
            {
                "id": "off_mock_101",
                "total_amount": "345.50",
                "total_currency": "USD",
                "owner": {
                    "name": "Iberia",
                    "iata_code": "IB",
                },
                "slices": [
                    {
                        "id": "sli_mock_201",
                        "duration": "PT7H30M",
                        "origin": {
                            "iata_code": "JFK",
                            "name": "John F. Kennedy International Airport",
                            "city_name": "New York",
                        },
                        "destination": {
                            "iata_code": "MAD",
                            "name": "Madrid-Barajas",
                            "city_name": "Madrid",
                        },
                        "segments": [
                            {
                                "id": "seg_mock_301",
                                "origin": {
                                    "iata_code": "JFK",
                                    "name": "John F. Kennedy International Airport",
                                },
                                "destination": {
                                    "iata_code": "MAD",
                                    "name": "Madrid-Barajas",
                                },
                                "departing_at": f"{FUTURE_DEPARTURE}T17:30:00",
                                "arriving_at": f"{FUTURE_DEPARTURE}T07:00:00",
                                "operating_carrier": {
                                    "name": "Iberia",
                                    "iata_code": "IB",
                                },
                                "operating_carrier_flight_number": "6250",
                                "duration": "PT7H30M",
                            }
                        ],
                    }
                ],
            }
        ],
    }
}


# --- Test 1: Successful Search with Mocked Duffel ---

@patch.object(httpx.AsyncClient, "post")
def test_cash_search_one_way_success(mock_post):
    mock_response = httpx.Response(
        status_code=201,
        json=MOCK_DUFFEL_SUCCESS,
        request=httpx.Request("POST", "https://api.duffel.com/air/offer_requests"),
    )
    mock_post.return_value = mock_response

    # Force a dummy key for testing
    app.dependency_overrides[get_duffel_service] = lambda: DuffelService(api_key="duffel_test_mockkey123")

    payload = {
        "origin": "JFK",
        "destination": "MAD",
        "departure_date": FUTURE_DEPARTURE,
        "passengers": 1,
        "cabin_class": "economy",
    }

    response = client.post("/api/v1/flights/cash", json=payload)
    app.dependency_overrides.clear()

    assert response.status_code == 200
    data = response.json()
    assert data["provider"] == "duffel"
    assert data["search_id"] == "orq_mock_001"
    assert data["total_offers"] == 1
    offer = data["offers"][0]
    assert offer["id"] == "off_mock_101"
    assert offer["total_price"] == 345.50
    assert offer["total_amount"] == "345.50"
    assert offer["currency"] == "USD"
    assert offer["airline_name"] == "Iberia"
    assert len(offer["slices"]) == 1
    slice_item = offer["slices"][0]
    assert slice_item["origin"]["iata_code"] == "JFK"
    assert slice_item["destination"]["iata_code"] == "MAD"
    assert len(slice_item["segments"]) == 1
    assert slice_item["segments"][0]["carrier_code"] == "IB"
    assert slice_item["segments"][0]["flight_number"] == "6250"


# --- Test 2: Round Trip Search payload construction ---

@patch.object(httpx.AsyncClient, "post")
def test_cash_search_round_trip_payload(mock_post):
    mock_response = httpx.Response(
        status_code=201,
        json=MOCK_DUFFEL_SUCCESS,
        request=httpx.Request("POST", "https://api.duffel.com/air/offer_requests"),
    )
    mock_post.return_value = mock_response

    app.dependency_overrides[get_duffel_service] = lambda: DuffelService(api_key="duffel_test_mockkey123")

    payload = {
        "origin": "jfk",  # lowercase should be auto-uppercased
        "destination": "mad",
        "departure_date": FUTURE_DEPARTURE,
        "return_date": FUTURE_RETURN,
        "passengers": 2,
        "cabin_class": "business",
    }

    response = client.post("/api/v1/flights/cash", json=payload)
    app.dependency_overrides.clear()

    assert response.status_code == 200
    # Inspect mock_post call arguments to verify slices and passengers
    call_args, call_kwargs = mock_post.call_args
    sent_json = call_kwargs.get("json", {}).get("data", {})
    assert len(sent_json.get("slices", [])) == 2
    assert sent_json["slices"][0]["origin"] == "JFK"
    assert sent_json["slices"][0]["destination"] == "MAD"
    assert sent_json["slices"][1]["origin"] == "MAD"
    assert sent_json["slices"][1]["destination"] == "JFK"
    assert len(sent_json.get("passengers", [])) == 2
    assert sent_json.get("cabin_class") == "business"


# --- Test 3: Input Validation Errors ---

def test_validation_invalid_origin_airport():
    response = client.post("/api/v1/flights/cash", json={
        "origin": "INVALID",
        "destination": "LHR",
        "departure_date": FUTURE_DEPARTURE,
    })
    assert response.status_code == 422


def test_validation_same_origin_and_destination():
    response = client.post("/api/v1/flights/cash", json={
        "origin": "JFK",
        "destination": "JFK",
        "departure_date": FUTURE_DEPARTURE,
    })
    assert response.status_code == 422


def test_validation_past_departure_date():
    response = client.post("/api/v1/flights/cash", json={
        "origin": "JFK",
        "destination": "LHR",
        "departure_date": PAST_DATE,
    })
    assert response.status_code == 422


def test_validation_return_date_before_departure():
    response = client.post("/api/v1/flights/cash", json={
        "origin": "JFK",
        "destination": "LHR",
        "departure_date": FUTURE_RETURN,
        "return_date": FUTURE_DEPARTURE,  # earlier than departure
    })
    assert response.status_code == 422


def test_validation_invalid_passenger_count():
    response = client.post("/api/v1/flights/cash", json={
        "origin": "JFK",
        "destination": "LHR",
        "departure_date": FUTURE_DEPARTURE,
        "passengers": 0,
    })
    assert response.status_code == 422


def test_validation_invalid_cabin_class():
    response = client.post("/api/v1/flights/cash", json={
        "origin": "JFK",
        "destination": "LHR",
        "departure_date": FUTURE_DEPARTURE,
        "cabin_class": "supersonic",
    })
    assert response.status_code == 422


# --- Test 4: Missing Duffel API Key returns 503 without leaking secrets ---

def test_missing_duffel_api_key():
    app.dependency_overrides[get_duffel_service] = lambda: DuffelService(api_key="")

    response = client.post("/api/v1/flights/cash", json={
        "origin": "JFK",
        "destination": "LHR",
        "departure_date": FUTURE_DEPARTURE,
    })
    app.dependency_overrides.clear()

    assert response.status_code == 503
    assert "Duffel API key is not configured" in response.json()["detail"]


# --- Test 5: Duffel Provider Error (400) Handled Cleanly ---

@patch.object(httpx.AsyncClient, "post")
def test_duffel_api_error_response(mock_post):
    mock_post.return_value = httpx.Response(
        status_code=400,
        json={
            "errors": [
                {
                    "message": "The airline did not return any flights for this route.",
                    "code": "airline_error"
                }
            ]
        },
        request=httpx.Request("POST", "https://api.duffel.com/air/offer_requests"),
    )

    app.dependency_overrides[get_duffel_service] = lambda: DuffelService(api_key="duffel_test_mockkey123")

    response = client.post("/api/v1/flights/cash", json={
        "origin": "JFK",
        "destination": "LHR",
        "departure_date": FUTURE_DEPARTURE,
    })
    app.dependency_overrides.clear()

    assert response.status_code == 400
    assert "The airline did not return any flights" in response.json()["detail"]


# --- Test 6: Timeout Error Handled Cleanly (504) ---

@patch.object(httpx.AsyncClient, "post")
def test_duffel_timeout_handled(mock_post):
    mock_post.side_effect = httpx.TimeoutException("Connection timed out")

    app.dependency_overrides[get_duffel_service] = lambda: DuffelService(api_key="duffel_test_mockkey123")

    response = client.post("/api/v1/flights/cash", json={
        "origin": "JFK",
        "destination": "LHR",
        "departure_date": FUTURE_DEPARTURE,
    })
    app.dependency_overrides.clear()

    assert response.status_code == 504
    assert "timed out" in response.json()["detail"]


# --- Test 7: Network Connection Failure (502) ---

@patch.object(httpx.AsyncClient, "post")
def test_duffel_network_failure_handled(mock_post):
    mock_post.side_effect = httpx.ConnectError("Connection refused")

    app.dependency_overrides[get_duffel_service] = lambda: DuffelService(api_key="duffel_test_mockkey123")

    response = client.post("/api/v1/flights/cash", json={
        "origin": "JFK",
        "destination": "LHR",
        "departure_date": FUTURE_DEPARTURE,
    })
    app.dependency_overrides.clear()

    assert response.status_code == 502
    assert "Unable to connect to flight search provider" in response.json()["detail"]


# --- Test 8: Malformed Provider Response (502) ---

@patch.object(httpx.AsyncClient, "post")
def test_duffel_malformed_response_handled(mock_post):
    mock_post.return_value = httpx.Response(
        status_code=200,
        json={"data": "not_a_dictionary"},
        request=httpx.Request("POST", "https://api.duffel.com/air/offer_requests"),
    )

    app.dependency_overrides[get_duffel_service] = lambda: DuffelService(api_key="duffel_test_mockkey123")

    response = client.post("/api/v1/flights/cash", json={
        "origin": "JFK",
        "destination": "LHR",
        "departure_date": FUTURE_DEPARTURE,
    })
    app.dependency_overrides.clear()

    assert response.status_code == 502
    assert "flight provider" in response.json()["detail"].lower()


# --- Test 9: Ensure Token is Never Leaked in Error Responses ---

@patch.object(httpx.AsyncClient, "post")
def test_token_never_leaked_in_response(mock_post):
    secret_token = "duffel_test_SUPER_SECRET_TOKEN_DO_NOT_LEAK"
    mock_post.return_value = httpx.Response(
        status_code=401,
        json={"errors": [{"message": "Unauthorized access token"}]},
        request=httpx.Request(
            "POST",
            "https://api.duffel.com/air/offer_requests",
            headers={"Authorization": f"Bearer {secret_token}"}
        ),
    )

    app.dependency_overrides[get_duffel_service] = lambda: DuffelService(api_key=secret_token)

    response = client.post("/api/v1/flights/cash", json={
        "origin": "JFK",
        "destination": "LHR",
        "departure_date": FUTURE_DEPARTURE,
    })
    app.dependency_overrides.clear()

    assert secret_token not in response.text
    assert "Authorization" not in response.text
