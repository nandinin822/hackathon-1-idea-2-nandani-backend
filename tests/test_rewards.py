import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_rewards_plan_csp():
    payload = {
        "destination": "MAD",
        "planning_horizon_months": 6,
        "travel_goal": "cheapest_flight",
        "card_id": "us_chase_csp",
        "current_points": 15000,
        "monthly_rent": 1200.0,
        "monthly_utilities": 150.0,
        "monthly_groceries_dining": 600.0,
        "monthly_travel": 200.0,
        "monthly_other": 300.0,
        "currency": "USD",
    }
    response = client.post("/api/v1/rewards/plan", json=payload)
    assert response.status_code == 200
    data = response.json()

    assert data["destination"] == "MAD"
    assert data["planning_horizon_months"] == 6
    assert data["current_points"] == 15000

    # Rent is excluded on CSP
    assert data["monthly_breakdown"]["eligible_monthly_spend"] == 1250.0
    assert data["monthly_breakdown"]["ineligible_monthly_spend"] == 1200.0
    assert len(data["monthly_breakdown"]["ineligible_reasons"]) >= 1

    # Monthly points = (600*3) + (200*2) + (150*1) + (300*1) = 1800 + 400 + 150 + 300 = 2650
    # 6 months = 2650 * 6 = 15900 points earned
    assert data["estimated_points_earned"] == 15900
    assert data["projected_total_points"] == 30900
    assert data["recommended_card"] == "Chase Sapphire Preferred®"
    assert data["verified_card_annual_fee"] == 95.0


def test_rewards_plan_bilt_includes_rent():
    payload = {
        "destination": "Tokyo",
        "planning_horizon_months": 12,
        "travel_goal": "business_class",
        "card_id": "us_bilt_rewards",
        "current_points": 5000,
        "monthly_rent": 2000.0,
        "monthly_groceries_dining": 500.0,
        "monthly_utilities": 100.0,
        "monthly_travel": 100.0,
        "monthly_other": 200.0,
    }
    response = client.post("/api/v1/rewards/plan", json=payload)
    assert response.status_code == 200
    data = response.json()

    # Bilt includes rent at 1x
    assert data["monthly_breakdown"]["eligible_monthly_spend"] == 2900.0
    assert data["monthly_breakdown"]["ineligible_monthly_spend"] == 0.0

    # Monthly points = 2000*1 + 500*3 + 100*2 + 100*1 + 200*1 = 2000 + 1500 + 200 + 100 + 200 = 4000
    # 12 months = 4000 * 12 = 48000
    assert data["estimated_points_earned"] == 48000
    assert data["projected_total_points"] == 53000
    assert data["verified_card_annual_fee"] == 0.0


def test_rewards_plan_invalid_horizon():
    payload = {
        "destination": "Paris",
        "planning_horizon_months": 5, # invalid
        "travel_goal": "earn_faster",
    }
    response = client.post("/api/v1/rewards/plan", json=payload)
    assert response.status_code == 422


def test_rewards_plan_zero_spending_warnings():
    payload = {
        "destination": "London",
        "planning_horizon_months": 3,
        "travel_goal": "business_class",
        "card_id": "us_chase_csp",
        "current_points": 0,
        "monthly_rent": 0.0,
        "monthly_utilities": 0.0,
        "monthly_groceries_dining": 0.0,
        "monthly_travel": 0.0,
        "monthly_other": 0.0,
    }
    response = client.post("/api/v1/rewards/plan", json=payload)
    assert response.status_code == 200
    data = response.json()
    assert data["estimated_points_earned"] == 0
    assert any("zero" in w.lower() for w in data["warnings"])
    assert any("business class" in w.lower() for w in data["warnings"])
