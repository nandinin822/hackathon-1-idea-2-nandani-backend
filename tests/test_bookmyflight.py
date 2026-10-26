"""Contract tests for the three judge demos and the transfer rules."""

from fastapi.testclient import TestClient

from app.data import MADRID_NYC_WHY, demo_by_id
from app.engine import (
    answer_copilot,
    calculate_hacked_price,
    generate_spend_strategy,
    parse_booking_text,
    transfers_payload,
)
from app.main import app

client = TestClient(app)


def test_madrid_new_york_judge_demo():
    demo = demo_by_id("euro-850")
    hack = demo["hack"]
    result = calculate_hacked_price(
        origin=hack["origin"],
        destination=hack["destination"],
        cards=hack["cards"],
        date_value=hack["date"],
        passengers=1,
    )
    best = result["best"]
    assert result["cash"]["amount"] == 850
    assert best["currency"] == "EUR"
    assert best["taxes"] == 60
    assert best["miles"] == 30000
    assert best["saved"] == 790
    assert best["savings_percent"] == 92
    assert best["cpp"] == 2.6
    assert best["cpp_baseline"] == 0.5
    assert best["can_book"] is True
    assert best["why"] == MADRID_NYC_WHY
    assert best["transfers"][0]["bank_points"] == 30000
    assert best["transfers"][0]["ratio"] == "1:1"
    assert len(result["booking"]["steps"]) == 3
    assert any(item["code"] == "EWR" and item["kind"] == "priced" for item in result["nearby"])


def test_delhi_london_rupee_demo():
    demo = demo_by_id("inr-3500")["hack"]
    result = calculate_hacked_price(
        origin=demo["origin"],
        destination=demo["destination"],
        cards=demo["cards"],
        date_value=demo["date"],
    )
    best = result["best"]
    assert best["cash"] == 55000
    assert best["taxes"] == 3500
    assert best["currency"] == "INR"
    assert best["miles"] == 42000
    assert best["saved"] == 51500
    assert best["savings_percent"] == 93
    assert best["can_book"] is True
    assert best["program_id"] == "krisflyer"


def test_shortfall_still_shows_the_promo_fare():
    result = calculate_hacked_price(
        origin="MAD",
        destination="JFK",
        cards=[{"id": "amex-gold", "points": 10000}],
    )
    best = result["best"]
    assert best["miles"] == 30000
    assert best["taxes"] == 60
    assert best["can_book"] is False
    assert best["miles_short"] == 20000


def test_passengers_scale_the_fare():
    result = calculate_hacked_price(
        origin="MAD",
        destination="JFK",
        cards=[{"id": "amex-gold", "points": 80000}],
        passengers=2,
    )
    best = result["best"]
    assert best["cash"] == 1700
    assert best["taxes"] == 120
    assert best["miles"] == 60000


def test_axis_transfer_is_two_to_one():
    result = calculate_hacked_price(
        origin="DEL",
        destination="LHR",
        cards=[{"id": "axis-magnus", "points": 90000}],
    )
    best = result["best"]
    assert best["can_book"] is True
    assert best["transfers"][0]["ratio"] == "2:1"
    assert best["transfers"][0]["bank_points"] == 84000


def test_bali_plan_cuts_the_wait_in_half():
    demo = demo_by_id("bali")["strategy"]
    plan = generate_spend_strategy(
        target_points=None,
        months=demo["months"],
        monthly_expenses=demo["monthly_expenses"],
        cards=demo["cards"],
        origin=demo["origin"],
        destination=demo["destination"],
        use_portals=True,
    )
    assert plan["award"]["miles"] == 60000
    assert plan["award"]["program_id"] == "flying_blue"
    assert plan["monthly_points"] == 5000
    assert plan["starting_points"] == 12000
    assert plan["months_without_bonus"] == 8
    assert plan["months_with_bonus"] == 4
    assert plan["halves_wait"] is True
    assert plan["recommendation"]["card_id"] == "chase-sapphire-preferred"
    assert plan["recommendation"]["welcome_points"] == 30000
    assert plan["recommendation"]["days"] == 90
    assert plan["milestone"]["month"] == 6
    assert plan["milestone"]["points"] == 8000
    month_two = next(row for row in plan["timeline"] if row["month"] == 2)
    month_four = next(row for row in plan["timeline"] if row["month"] == 4)
    assert month_two["cumulative"] == 22000
    assert month_four["cumulative"] == 62000
    assert month_four["reached"] is True
    assert "half the time" in plan["narrative"]
    groceries = next(row for row in plan["assignments"] if row["category"] == "groceries")
    dining = next(row for row in plan["assignments"] if row["category"] == "dining")
    assert groceries["multiplier"] == 4
    assert dining["multiplier"] == 8
    assert plan["rent_tip"]["extra_monthly_points"] == 1200
    assert plan["alternates"][0]["card_id"] == "citi-custom-cash"
    assert plan["alternates"][0]["months"] == 6


def test_transfer_matrix_covers_the_spec_sample():
    rows = transfers_payload()
    pairs = {(row["currency"], row["program_id"], row["ratio"]) for row in rows if row["sample"]}
    assert ("amex_mr", "iberia_plus", "1:1") in pairs
    assert ("amex_mr", "ba_avios", "1:1") in pairs
    assert ("amex_mr", "flying_blue", "1:1") in pairs
    assert ("chase_ur", "virgin_atlantic", "1:1") in pairs
    assert ("capital_one", "lifemiles", "1:1") in pairs
    assert ("citi_typ", "lifemiles", "1:1") in pairs
    assert ("axis_edge", "krisflyer", "2:1") in pairs
    assert ("hdfc_smartbuy", "qatar", "1:1") in pairs
    virgin = next(row for row in rows if row["program_id"] == "virgin_atlantic")
    assert virgin["alliance"] == "Non-alliance partner"


def test_copilot_combines_amex_and_chase_for_dubai():
    answer = answer_copilot(
        "I have 25k Amex points and 15k Chase points, can I combine them to fly to Dubai?"
    )
    assert answer["can_combine"] is True
    assert answer["combined_miles"] == 40000
    assert answer["miles_needed"] == 35000
    assert answer["miles_left"] == 5000
    assert "Flying Blue" in answer["answer"]


def test_parse_skyscanner_and_plain_text():
    parsed = parse_booking_text("https://www.skyscanner.net/transport/flights/mad/jfk/261120/")
    assert parsed["origin"] == "MAD"
    assert parsed["destination"] == "JFK"
    assert parsed["date"] == "2026-11-20"
    plain = parse_booking_text("Madrid to New York €850 Air France AF1021")
    assert plain["origin"] == "MAD"
    assert plain["destination"] == "JFK"
    assert plain["cash_price"] == 850
    assert plain["flight_number"] == "AF1021"


def test_api_demos_round_trip():
    health = client.get("/api/health")
    assert health.status_code == 200
    euro = client.get("/api/demos/euro-850").json()
    response = client.post("/api/hack", json=euro["hack"])
    assert response.status_code == 200
    body = response.json()
    assert body["best"]["taxes"] == 60
    assert body["best"]["miles"] == 30000
    bali = client.get("/api/demos/bali").json()
    plan = client.post("/api/strategy", json=bali["strategy"])
    assert plan.status_code == 200
    assert plan.json()["months_with_bonus"] == 4
    rupee = client.get("/api/demos/inr-3500").json()
    india = client.post("/api/hack", json=rupee["hack"])
    assert india.status_code == 200
    assert india.json()["best"]["taxes"] == 3500
