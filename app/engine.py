"""Pricing, spend strategy, link parsing, and copilot answers.

`calculate_hacked_price` and `generate_spend_strategy` are the rules engine.
`write_strategy_narrative` and `parse_screenshot` are the module boundary a
later model can replace. v1 does not call a paid LLM.
"""

from __future__ import annotations

import calendar
import math
import re
from datetime import date, timedelta
from urllib.parse import urlencode

from app.data import (
    AIRPORTS,
    AWARDS,
    CARDS,
    CATEGORIES,
    CITY_ALIASES,
    CURRENCIES,
    MILESTONES,
    NEARBY,
    PORTAL_BONUS,
    PROGRAMS,
    STOPOVER_NOTES,
    TRANSFERS,
    airport,
    best_transfer,
    card_by_id,
)

CATEGORY_IDS = [item["id"] for item in CATEGORIES]
CATEGORY_LABELS = {item["id"]: item["label"] for item in CATEGORIES}
# A 5× "top category" applies to everyday shopping, not rent or household bills.
TOP_BONUS_CATEGORIES = {"groceries", "dining", "shopping"}


class EngineError(Exception):
    def __init__(self, message: str, status: int = 400, extra: dict | None = None):
        super().__init__(message)
        self.message = message
        self.status = status
        self.extra = extra or {}


def money(amount: int | float, currency: str) -> str:
    rounded = int(round(amount))
    if currency == "EUR":
        return f"€{rounded:,}"
    if currency == "INR":
        return "₹" + _indian_group(rounded)
    return f"{rounded:,} {currency}"


def _indian_group(value: int) -> str:
    sign = "-" if value < 0 else ""
    digits = str(abs(value))
    if len(digits) <= 3:
        return sign + digits
    head, tail = digits[:-3], digits[-3:]
    parts: list[str] = []
    while len(head) > 2:
        parts.append(head[-2:])
        head = head[:-2]
    if head:
        parts.append(head)
    return sign + ",".join(reversed(parts)) + "," + tail


def ratio_label(ratio: float) -> str:
    if abs(ratio - 1.0) < 1e-9:
        return "1:1"
    if abs(ratio - 0.5) < 1e-9:
        return "2:1"
    return f"1:{ratio:g}"


def bank_points_for(miles: int, ratio: float) -> int:
    if ratio <= 0:
        raise EngineError("Transfer ratio must be positive.")
    return math.ceil(miles / ratio - 1e-9)


def percent_off(cash: int, taxes: int) -> int:
    if cash <= 0:
        return 0
    saved = max(0, cash - taxes)
    return saved * 100 // cash


def cents_per_point(saved: int, miles: int, currency: str) -> tuple[float, float, str]:
    """Return (value, weak-cashback baseline, unit)."""
    if miles <= 0:
        return 0.0, 0.0, "¢" if currency == "EUR" else currency
    if currency == "EUR":
        return round(saved / miles * 100, 1), 0.5, "¢"
    if currency == "INR":
        return round(saved / miles, 2), 0.25, "₹"
    return round(saved / miles, 2), 0.0, currency


def _parse_date(value: str | None, fallback: date | None = None) -> date:
    if not value:
        return fallback or (date.today() + timedelta(days=21))
    try:
        return date.fromisoformat(value[:10])
    except ValueError as exc:
        raise EngineError("Use a date like 2026-11-20.") from exc


def _require_airport(code: str) -> dict:
    found = airport(code)
    if not found:
        known = ", ".join(item["code"] for item in AIRPORTS)
        raise EngineError(f"Unknown airport '{code}'. Known codes: {known}.")
    return found


def _award_pair(award: dict) -> frozenset[str]:
    return frozenset((award["origin"], award["destination"]))


def exact_awards(origin: str, destination: str) -> list[dict]:
    pair = frozenset((origin.upper(), destination.upper()))
    return [award for award in AWARDS if _award_pair(award) == pair and award["cabin"] == "economy"]


def _nearby_codes(code: str) -> list[str]:
    return [item["code"] for item in NEARBY.get(code, [])]


def _resolve_cards(cards: list[dict]) -> list[dict]:
    resolved = []
    for raw in cards:
        master = card_by_id(raw["id"])
        if not master:
            raise EngineError(f"Unknown card '{raw['id']}'.")
        points = int(raw.get("points") or 0)
        if points < 0:
            raise EngineError("Point balances cannot be negative.")
        resolved.append({**master, "points": points})
    return resolved


def _leg(card: dict, transfer: dict, bank_points: int, miles: int) -> dict:
    meta = CURRENCIES[card["currency"]]
    return {
        "card_id": card["id"],
        "card_name": card["name"],
        "currency": card["currency"],
        "currency_label": meta["label"],
        "bank_points": bank_points,
        "miles": miles,
        "ratio": ratio_label(transfer["ratio"]),
        "ratio_value": transfer["ratio"],
        "portal_url": meta["portal_url"],
        "portal_label": meta["portal_label"],
    }


def plan_transfers(program_id: str, miles_needed: int, cards: list[dict]) -> tuple[list[dict], int]:
    """Prefer one card when it covers the award. Otherwise pool balances that share a program."""
    eligible = []
    for card in cards:
        transfer = best_transfer(card["currency"], program_id)
        if not transfer or card["points"] <= 0:
            continue
        eligible.append(
            {
                **card,
                "transfer": transfer,
                "deliverable": int(card["points"] * transfer["ratio"]),
            }
        )
    singles = [item for item in eligible if item["deliverable"] >= miles_needed]
    if singles:
        chosen = min(
            singles,
            key=lambda item: (
                bank_points_for(miles_needed, item["transfer"]["ratio"]),
                0 if item["currency"] == "amex_mr" else 1,
                -item["points"],
            ),
        )
        bank_points = min(chosen["points"], bank_points_for(miles_needed, chosen["transfer"]["ratio"]))
        delivered = int(bank_points * chosen["transfer"]["ratio"])
        return [_leg(chosen, chosen["transfer"], bank_points, delivered)], 0

    remaining = miles_needed
    legs = []
    for item in sorted(eligible, key=lambda row: row["deliverable"], reverse=True):
        if remaining <= 0:
            break
        use_miles = min(remaining, item["deliverable"])
        bank_points = min(item["points"], bank_points_for(use_miles, item["transfer"]["ratio"]))
        delivered = int(bank_points * item["transfer"]["ratio"])
        if delivered <= 0:
            continue
        legs.append(_leg(item, item["transfer"], bank_points, delivered))
        remaining -= delivered
    return legs, max(0, remaining)


def _search_url(program_id: str, origin: str, destination: str, when: date, cabin: str) -> str:
    base = PROGRAMS[program_id]["search_url"]
    query = urlencode(
        {
            "origin": origin,
            "destination": destination,
            "date": when.isoformat(),
            "cabin": cabin,
            "award": "1",
        }
    )
    join = "&" if "?" in base else "?"
    return f"{base}{join}{query}"


def _why(award: dict, legs: list[dict], passengers: int, round_trip: bool) -> str:
    verbatim = (
        not round_trip
        and passengers == 1
        and award.get("why")
        and len(legs) == 1
        and legs[0]["currency"] == "amex_mr"
        and legs[0]["miles"] >= award["miles"]
    )
    if verbatim:
        return award["why"]
    program = PROGRAMS[award["program"]]["name"]
    promo = f" {award['promo']}." if award.get("promo") else ""
    if legs:
        moved = ", ".join(
            f"{leg['bank_points']:,} {leg['currency_label']} from {leg['card_name']} at {leg['ratio']}"
            for leg in legs
        )
        return (
            f"{program} prices this seat at {award['miles']:,} miles plus taxes.{promo} "
            f"Move {moved}."
        ).replace("..", ".")
    holders = _currencies_that_reach(award["program"])
    return (
        f"{program} prices this seat at {award['miles']:,} miles plus taxes.{promo} "
        f"You would need a card that transfers in: {holders}."
    ).replace("..", ".")


def _currencies_that_reach(program_id: str) -> str:
    labels = []
    seen = set()
    for row in TRANSFERS:
        if row["to"] != program_id or row["from"] in seen:
            continue
        seen.add(row["from"])
        labels.append(CURRENCIES[row["from"]]["label"])
    return ", ".join(labels) if labels else "no sample currency"


def _build_option(
    award: dict,
    cards: list[dict],
    user_origin: str,
    user_destination: str,
    when: date,
    cabin: str,
    factor: int,
    round_trip: bool,
) -> dict:
    miles = award["miles"] * factor
    taxes = award["taxes"] * factor
    cash = award["cash"] * factor
    saved = max(0, cash - taxes)
    legs, short = plan_transfers(award["program"], miles, cards)
    cpp, baseline, unit = cents_per_point(saved, miles, award["currency"])
    pair = _award_pair(award)
    if pair == frozenset((user_origin, user_destination)):
        origin, destination = user_origin, user_destination
    else:
        origin, destination = award["origin"], award["destination"]
    scaled = {**award, "miles": miles, "taxes": taxes, "cash": cash}
    program = PROGRAMS[award["program"]]
    return {
        "id": award["id"],
        "program_id": award["program"],
        "program": program["name"],
        "alliance": program["alliance"],
        "origin": origin,
        "destination": destination,
        "origin_city": airport(origin)["city"] if airport(origin) else origin,
        "destination_city": airport(destination)["city"] if airport(destination) else destination,
        "miles": miles,
        "taxes": taxes,
        "cash": cash,
        "currency": award["currency"],
        "saved": saved,
        "savings_percent": percent_off(cash, taxes),
        "cpp": cpp,
        "cpp_baseline": baseline,
        "cpp_unit": unit,
        "can_book": short == 0 and bool(legs),
        "miles_short": short,
        "transfers": legs,
        "why": _why(scaled, legs, factor if not round_trip else factor, round_trip),
        "promo": award.get("promo") or "",
        "stopover": award.get("stopover"),
        "note": award.get("note") or "",
        "deep_link": _search_url(award["program"], origin, destination, when, cabin),
        "date": when.isoformat(),
        "cabin": cabin,
        "round_trip": round_trip,
        "passengers": factor if not round_trip else max(1, factor // (2 if round_trip else 1)),
    }


def _rank_key(option: dict) -> tuple:
    return (option["taxes"], option["miles"], -option["saved"])


def booking_steps(option: dict) -> list[dict]:
    if not option:
        return []
    transfer_lines = []
    links = []
    for leg in option["transfers"]:
        transfer_lines.append(
            f"Transfer {leg['bank_points']:,} {leg['currency_label']} from {leg['card_name']} "
            f"to {option['program']} at {leg['ratio']}."
        )
        links.append(
            {
                "label": leg["portal_label"],
                "url": leg["portal_url"],
                "detail": f"{leg['bank_points']:,} {leg['currency_label']}",
            }
        )
    if not transfer_lines:
        holders = _currencies_that_reach(option["program_id"])
        transfer_lines.append(
            f"You still need {option['miles']:,} {option['program']} miles. "
            f"Cards that transfer in: {holders}."
        )
    elif option["miles_short"]:
        transfer_lines.append(
            f"That covers part of the award. You are still {option['miles_short']:,} miles short of {option['miles']:,}."
        )
    tax = money(option["taxes"], option["currency"])
    cash = money(option["cash"], option["currency"])
    return [
        {
            "n": 1,
            "title": "Move the points",
            "body": " ".join(transfer_lines),
            "warning": "Transfer only after you can see the seat. Transfers usually cannot be reversed.",
            "links": links,
        },
        {
            "n": 2,
            "title": "Open the award search",
            "body": (
                f"{option['program']} · {option['origin']} → {option['destination']} · "
                f"{option['date']} · {option['cabin'].title()} · {option['miles']:,} miles + {tax} tax."
            ),
            "note": "The link carries origin, destination, date, and cabin. The airline site may ask you to enter them again.",
            "links": [{"label": f"Open {option['program']}", "url": option["deep_link"], "detail": "Pre-filled award search"}],
        },
        {
            "n": 3,
            "title": "Confirm and ticket",
            "body": f"The cash fare on this mock chart is {cash}. You pay the tax, not that fare.",
            "checks": [
                f"The seat is still there at {option['miles']:,} miles + {tax}",
                "The points have landed in the frequent-flyer account",
                "The passenger name matches the passport",
            ],
        },
    ]


def _flexible_dates(when: date, option: dict) -> list[dict]:
    rows = []
    for delta in range(-3, 4):
        if delta == 0:
            continue
        wobble = ((abs(delta) * 17) % 5) - 2
        rows.append(
            {
                "date": (when + timedelta(days=delta)).isoformat(),
                "delta_days": delta,
                "cash": max(option["taxes"] + 40, option["cash"] + wobble * 12),
                "miles": option["miles"],
                "taxes": option["taxes"],
                "currency": option["currency"],
            }
        )
    return rows


def _nearby_payload(origin: str, destination: str, cards: list[dict], when: date, cabin: str, factor: int, round_trip: bool) -> list[dict]:
    priced: list[dict] = []
    seen: set[str] = set()
    swaps: list[tuple[str, str, str]] = []
    for alt in _nearby_codes(origin):
        swaps.append((alt, destination, origin))
    for alt in _nearby_codes(destination):
        swaps.append((origin, alt, destination))
    for alt_origin, alt_dest, instead in swaps:
        for award in AWARDS:
            if award["cabin"] != "economy" or award["id"] in seen:
                continue
            if _award_pair(award) != frozenset((alt_origin, alt_dest)):
                continue
            seen.add(award["id"])
            option = _build_option(award, cards, alt_origin, alt_dest, when, cabin, factor, round_trip)
            place_code = alt_origin if alt_origin != origin else alt_dest
            place = next((item for item in NEARBY.get(instead, []) if item["code"] == place_code), None)
            priced.append(
                {
                    "kind": "priced",
                    "code": place_code,
                    "city": (place or {}).get("city") or option["origin_city"],
                    "minutes": (place or {}).get("minutes"),
                    "mode": (place or {}).get("mode"),
                    "instead_of": instead,
                    "option": option,
                }
            )
    unpriced = []
    priced_codes = {item["code"] for item in priced}
    for side in (origin, destination):
        for place in NEARBY.get(side, []):
            if place["code"] in priced_codes:
                continue
            unpriced.append(
                {
                    "kind": "unpriced",
                    "code": place["code"],
                    "city": place["city"],
                    "minutes": place["minutes"],
                    "mode": place["mode"],
                    "instead_of": side,
                    "option": None,
                    "note": f"No award row for {place['code']} in the v1 chart. The priced award still leaves from {side}.",
                }
            )
    return priced[:3] + unpriced[:2]


def calculate_hacked_price(
    origin: str,
    destination: str,
    cards: list[dict] | None = None,
    date_value: str | None = None,
    cabin: str = "economy",
    passengers: int = 1,
    flexible: bool = False,
    nearby: bool = True,
    via: str | None = None,
    return_date: str | None = None,
) -> dict:
    """Cash fare versus the best award the supplied cards can reach.

    `cards` is a list of `{id, points}`. Spec name: calculate_hacked_price(route, cards, points).
    """
    origin_airport = _require_airport(origin)
    destination_airport = _require_airport(destination)
    origin = origin_airport["code"]
    destination = destination_airport["code"]
    if origin == destination:
        raise EngineError("Origin and destination are the same.")
    if passengers < 1 or passengers > 9:
        raise EngineError("Passengers must be between 1 and 9.")
    cabin = (cabin or "economy").lower()
    when = _parse_date(date_value)
    resolved = _resolve_cards(cards or [])
    awards = exact_awards(origin, destination)
    if not awards:
        suggestions = _route_suggestions()
        raise EngineError(
            f"No award chart for {origin_airport['city']} → {destination_airport['city']} yet.",
            status=404,
            extra={"suggestions": suggestions},
        )
    round_trip = bool(return_date)
    factor = passengers * (2 if round_trip else 1)
    options = [
        _build_option(award, resolved, origin, destination, when, "economy", factor, round_trip)
        for award in awards
    ]
    bookable = [option for option in options if option["can_book"]]
    pool = bookable or options
    best = min(pool, key=_rank_key)
    alternatives = [option for option in sorted(options, key=_rank_key) if option["id"] != best["id"]]
    cabin_note = ""
    if cabin == "business":
        cabin_note = "v1 only has an economy chart for this route. The prices below are economy."
    stopover_note = ""
    if via:
        via_airport = _require_airport(via)
        stopover_note = STOPOVER_NOTES.get(
            via_airport["code"],
            f"v1 prices {origin} → {destination} nonstop. A stop in {via_airport['city']} is noted, not repriced, unless an award lists it.",
        )
    flexible_rows = _flexible_dates(when, best) if flexible else []
    nearby_rows = _nearby_payload(origin, destination, resolved, when, "economy", factor, round_trip) if nearby else []
    return {
        "found": True,
        "query": {
            "origin": origin,
            "destination": destination,
            "origin_city": origin_airport["city"],
            "destination_city": destination_airport["city"],
            "date": when.isoformat(),
            "return_date": return_date,
            "cabin": cabin,
            "passengers": passengers,
            "flexible": flexible,
            "nearby": nearby,
            "via": via.upper() if via else None,
            "round_trip": round_trip,
        },
        "cash": {"amount": best["cash"], "currency": best["currency"]},
        "best": best,
        "alternatives": alternatives,
        "nearby": nearby_rows,
        "flexible_dates": flexible_rows,
        "stopover_note": stopover_note,
        "cabin_note": cabin_note,
        "pricing_note": "Round trip is priced as two one-way awards." if round_trip else "",
        "booking": {"steps": booking_steps(best)},
    }


def _route_suggestions() -> list[dict]:
    seen = set()
    rows = []
    for award in AWARDS:
        key = tuple(sorted(_award_pair(award)))
        if key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "origin": award["origin"],
                "destination": award["destination"],
                "label": f"{airport(award['origin'])['city']} → {airport(award['destination'])['city']}",
            }
        )
    return rows


def _next_month(day: date) -> date:
    if day.month == 12:
        return date(day.year + 1, 1, 1)
    return date(day.year, day.month + 1, 1)


def _add_months(day: date, count: int) -> date:
    month_index = day.month - 1 + count
    year = day.year + month_index // 12
    month = month_index % 12 + 1
    last = calendar.monthrange(year, month)[1]
    return date(year, month, min(day.day, last))


def _expenses(raw: dict) -> dict[str, int]:
    cleaned = {}
    for category in CATEGORY_IDS:
        value = raw.get(category, 0) if raw else 0
        try:
            number = int(round(float(value)))
        except (TypeError, ValueError) as exc:
            raise EngineError(f"Spend for {category} must be a number.") from exc
        cleaned[category] = max(0, number)
    return cleaned


def _effective_multiplier(card: dict, category: str, use_portals: bool, as_top: bool) -> int:
    if card.get("top_category_only"):
        if as_top:
            return int(card.get("top_multiplier") or 5)
        return int(card["multipliers"].get(category, 1))
    base = int(card["multipliers"].get(category, 0))
    if base <= 0:
        return 0
    extra = PORTAL_BONUS.get(category, 0) if use_portals else 0
    return base + extra


def _transfer_ratio(card: dict, program_id: str) -> float:
    transfer = best_transfer(card["currency"], program_id)
    return transfer["ratio"] if transfer else 0.0


def assign_spend(cards: list[dict], program_id: str, expenses: dict[str, int], use_portals: bool) -> tuple[list[dict], int]:
    eligible = [card for card in cards if _transfer_ratio(card, program_id) > 0]
    pool = eligible or cards
    regular = [card for card in pool if not card.get("top_category_only")]
    specials = [card for card in pool if card.get("top_category_only")]

    def points_for(card: dict | None, category: str, as_top: bool = False) -> int:
        if card is None:
            return 0
        amount = expenses.get(category, 0)
        multiplier = _effective_multiplier(card, category, use_portals, as_top)
        return int(round(amount * multiplier * _transfer_ratio(card, program_id)))

    choice: dict[str, tuple[dict, bool] | None] = {}
    for category in CATEGORY_IDS:
        best_card = None
        best_points = -1
        for card in regular:
            earned = points_for(card, category, False)
            if earned > best_points or best_card is None:
                best_points = earned
                best_card = card
        choice[category] = (best_card, False) if best_card else None

    used: set[str] = set()
    for card in specials:
        best_category = None
        best_gain = 0
        for category in CATEGORY_IDS:
            if category not in TOP_BONUS_CATEGORIES or category in used:
                continue
            current = choice.get(category)
            current_points = points_for(current[0], category, current[1]) if current else 0
            gain = points_for(card, category, True) - current_points
            if gain > best_gain:
                best_gain = gain
                best_category = category
        if best_category is not None:
            choice[best_category] = (card, True)
            used.add(best_category)

    program_name = PROGRAMS[program_id]["name"]
    rows = []
    total = 0
    for category in CATEGORY_IDS:
        amount = expenses.get(category, 0)
        picked = choice.get(category)
        if not picked:
            rows.append(
                {
                    "category": category,
                    "label": CATEGORY_LABELS[category],
                    "monthly_spend": amount,
                    "card_id": None,
                    "card_name": "No earning card",
                    "multiplier": 0,
                    "portal": False,
                    "monthly_points": 0,
                    "blurb": f"Nothing in the wallet transfers {CATEGORY_LABELS[category].lower()} spend to {program_name}.",
                }
            )
            continue
        card, as_top = picked
        multiplier = _effective_multiplier(card, category, use_portals, as_top)
        earned = points_for(card, category, as_top)
        portal = bool(
            use_portals
            and category in PORTAL_BONUS
            and not as_top
            and int(card["multipliers"].get(category, 0)) > 0
            and multiplier > int(card["multipliers"].get(category, 0))
        )
        if multiplier <= 0:
            blurb = (
                f"No monthly multiplier on {card['name']}. "
                f"This spend still counts toward the household milestone."
            )
        elif portal:
            blurb = f"{multiplier}× through the {CATEGORY_LABELS[category].lower()} portal, on a card that transfers to {program_name}."
        elif as_top:
            blurb = f"{multiplier}× because this is the bonus category on {card['name']}."
        else:
            blurb = f"{multiplier}× on {card['name']}. Highest rate that transfers to {program_name}."
        total += earned
        rows.append(
            {
                "category": category,
                "label": CATEGORY_LABELS[category],
                "monthly_spend": amount,
                "card_id": card["id"],
                "card_name": card["name"],
                "multiplier": multiplier,
                "portal": portal,
                "monthly_points": earned,
                "blurb": blurb,
            }
        )
    return rows, total


def _starting_miles(cards: list[dict], program_id: str) -> int:
    total = 0
    for card in cards:
        ratio = _transfer_ratio(card, program_id)
        total += int(card["points"] * ratio)
    return total


def _spend_threshold(welcome: dict, plan_currency: str) -> int:
    spend = int(welcome["spend"])
    welcome_currency = welcome.get("currency", "EUR")
    if welcome_currency == plan_currency:
        return spend
    if plan_currency == "INR" and welcome_currency == "EUR":
        return spend * 90
    if plan_currency == "EUR" and welcome_currency == "INR":
        return max(1, spend // 90)
    return spend


def _milestone_month(expenses: dict[str, int], currency: str, assignments: list[dict]) -> dict | None:
    rent_row = next((row for row in assignments if row["category"] == "rent"), None)
    if rent_row and rent_row["multiplier"] > 0:
        return None
    spec = MILESTONES.get(currency)
    if not spec:
        return None
    household = expenses.get("bills", 0) + expenses.get("rent", 0)
    if household <= 0:
        return None
    month = math.ceil(spec["threshold"] / household)
    return {
        "threshold": spec["threshold"],
        "points": spec["points"],
        "month": month,
        "household_monthly": household,
        "currency": currency,
    }


def months_until(
    starting: int,
    monthly: int,
    target: int,
    bonus: int = 0,
    bonus_month: int | None = None,
    milestone_points: int = 0,
    milestone_month: int | None = None,
    cap: int = 48,
) -> int | None:
    if starting >= target:
        return 0
    if monthly <= 0 and bonus <= 0 and milestone_points <= 0:
        return None
    cumulative = starting
    for month in range(1, cap + 1):
        cumulative += monthly
        if bonus and bonus_month and month == bonus_month:
            cumulative += bonus
        if milestone_points and milestone_month and month == milestone_month:
            cumulative += milestone_points
        if cumulative >= target:
            return month
    return None


def _timeline(
    starting: int,
    monthly: int,
    target: int,
    bonus: int,
    bonus_month: int | None,
    milestone_points: int,
    milestone_month: int | None,
    month_count: int,
    first_month: date,
) -> list[dict]:
    rows = [
        {
            "month": 0,
            "label": "Today",
            "earned": 0,
            "bonus": 0,
            "milestone": 0,
            "cumulative": starting,
            "reached": starting >= target,
            "events": [f"{starting:,} miles already in the account" if starting else "Starting from zero"],
        }
    ]
    cumulative = starting
    reached_marked = starting >= target
    for month in range(1, month_count + 1):
        bonus_this = bonus if bonus_month == month else 0
        milestone_this = milestone_points if milestone_month == month else 0
        cumulative += monthly + bonus_this + milestone_this
        events = []
        if month == 1:
            events.append(f"Earn about {monthly:,} miles from the card plan")
        if bonus_this:
            events.append(f"Welcome bonus posts: {bonus_this:,} points")
        if milestone_this:
            events.append(f"Household milestone posts: {milestone_this:,} points")
        just_reached = not reached_marked and cumulative >= target
        if just_reached:
            events.append("You can book the ticket")
            reached_marked = True
        if not events:
            events.append("Keep the same cards in the same shops")
        label_date = _add_months(first_month, month - 1)
        rows.append(
            {
                "month": month,
                "label": label_date.strftime("%B %Y"),
                "earned": monthly,
                "bonus": bonus_this,
                "milestone": milestone_this,
                "cumulative": cumulative,
                "reached": cumulative >= target,
                "book_month": just_reached,
                "events": events,
            }
        )
    return rows


def _candidate_plans(origin: str, destination: str, owned: list[dict], expenses: dict[str, int], months: int, use_portals: bool, target_points: int | None) -> list[dict]:
    awards = exact_awards(origin, destination)
    considered = []
    owned_ids = {card["id"] for card in owned}
    for award in awards:
        program_id = award["program"]
        goal = int(target_points) if target_points else award["miles"]
        owned_assignments, owned_monthly = assign_spend(owned, program_id, expenses, use_portals)
        starting = _starting_miles(owned, program_id)
        milestone = _milestone_month(expenses, award["currency"], owned_assignments)
        milestone_points = milestone["points"] if milestone else 0
        milestone_at = milestone["month"] if milestone else None
        without = months_until(starting, owned_monthly, goal, 0, None, milestone_points, milestone_at)
        welcome_options = []
        for card in CARDS:
            if not card.get("welcome") or card["id"] in owned_ids:
                continue
            if _transfer_ratio(card, program_id) <= 0:
                continue
            together = owned + [{**card, "points": 0}]
            _rows, monthly = assign_spend(together, program_id, expenses, use_portals)
            total_spend = sum(expenses.values())
            threshold = _spend_threshold(card["welcome"], award["currency"])
            if total_spend <= 0:
                continue
            bonus_month = max(3, math.ceil(threshold / total_spend))
            with_bonus = months_until(
                starting,
                monthly,
                goal,
                int(card["welcome"]["points"]),
                bonus_month,
                milestone_points,
                milestone_at,
            )
            welcome_options.append(
                {
                    "card": card,
                    "monthly": monthly,
                    "months": with_bonus,
                    "bonus_month": bonus_month,
                    "threshold": threshold,
                    "multiplier_gain": monthly - owned_monthly,
                }
            )
        welcome_options = [item for item in welcome_options if item["months"] is not None]
        welcome_options.sort(key=lambda item: (item["months"], -item["card"]["welcome"]["points"]))
        best_welcome = welcome_options[0] if welcome_options else None
        reachable = _transfer_ratio_any(owned, program_id) or best_welcome is not None
        if not reachable:
            continue
        with_months = best_welcome["months"] if best_welcome else without
        considered.append(
            {
                "award": award,
                "goal": goal,
                "owned_assignments": owned_assignments,
                "owned_monthly": owned_monthly,
                "starting": starting,
                "milestone": milestone,
                "without": without,
                "welcome_options": welcome_options,
                "best_welcome": best_welcome,
                "with_months": with_months if with_months is not None else 99,
            }
        )
    considered.sort(key=lambda item: (item["with_months"], item["award"]["taxes"], item["goal"]))
    return considered


def _transfer_ratio_any(cards: list[dict], program_id: str) -> bool:
    return any(_transfer_ratio(card, program_id) > 0 for card in cards)


def write_strategy_narrative(plan: dict) -> str:
    """Deterministic copilot copy. Replace this function with an LLM call later."""
    origin = plan["origin"]["city"]
    destination = plan["destination"]["city"]
    award = plan["award"]
    tax = money(award["taxes"], award["currency"])
    cash = money(award["cash"], award["currency"])
    sentences = [
        (
            f"You are {plan['points_needed']:,} {award['program']} miles short of {origin} to {destination} "
            f"({award['miles']:,} miles + {tax} tax, against about {cash} cash)."
        )
    ]
    grocery = next((row for row in plan["assignments"] if row["category"] == "groceries"), None)
    dining = next((row for row in plan["assignments"] if row["category"] == "dining"), None)
    if grocery and dining and grocery["card_name"] == dining["card_name"] and grocery["monthly_points"]:
        portal = " through the dining portal" if dining["portal"] else ""
        sentences.append(
            f"Put groceries on {grocery['card_name']} at {grocery['multiplier']}× "
            f"and dining on the same card at {dining['multiplier']}×{portal}."
        )
    recommendation = plan.get("recommendation")
    if recommendation and plan.get("halves_wait"):
        sentences.append(
            f"Open {recommendation['card_name']}, spend {money(recommendation['spend'], recommendation['spend_currency'])} "
            f"in {recommendation['days']} days, and the {recommendation['welcome_points']:,}-point bonus "
            f"cuts the wait from {plan['months_without_bonus']} months to {plan['months_with_bonus']} — half the time."
        )
    elif recommendation and plan.get("months_with_bonus"):
        sentences.append(
            f"Open {recommendation['card_name']} for {recommendation['welcome_points']:,} bonus points. "
            f"That moves the booking from {plan['months_without_bonus']} months to {plan['months_with_bonus']}."
        )
    elif plan.get("months_without_bonus"):
        sentences.append(f"On the cards you already have, you can book in month {plan['months_without_bonus']}.")
    milestone = plan.get("milestone")
    if milestone:
        sentences.append(
            f"Bills and rent count toward a {milestone['points']:,}-point household milestone "
            f"at {money(milestone['threshold'], milestone['currency'])} spent, around month {milestone['month']}."
        )
    return " ".join(sentences)


def generate_spend_strategy(
    target_points: int | None,
    months: int,
    monthly_expenses: dict,
    cards: list[dict] | None = None,
    origin: str | None = None,
    destination: str | None = None,
    use_portals: bool = True,
    today: date | None = None,
) -> dict:
    """Map monthly spend onto the cards that reach an award fastest.

    Spec name: generate_spend_strategy(target_points, months, monthly_expenses).
    Pass origin and destination to pick the award chart. `target_points` overrides the chart.
    """
    if not origin or not destination:
        raise EngineError("Choose an origin and a destination.")
    if months < 1 or months > 24:
        raise EngineError("Plan length must be between 1 and 24 months.")
    origin_airport = _require_airport(origin)
    destination_airport = _require_airport(destination)
    owned = _resolve_cards(cards or [])
    if not owned:
        raise EngineError("Add at least one card you already have. A new-card bonus is recommended on top.")
    expenses = _expenses(monthly_expenses)
    considered = _candidate_plans(
        origin_airport["code"],
        destination_airport["code"],
        owned,
        expenses,
        months,
        use_portals,
        target_points,
    )
    if not considered:
        raise EngineError(
            f"No award chart for {origin_airport['city']} → {destination_airport['city']} that your cards can reach.",
            status=404,
            extra={"suggestions": _route_suggestions()},
        )
    chosen = considered[0]
    award = chosen["award"]
    welcome = chosen["best_welcome"]
    use_welcome = welcome is not None and (chosen["without"] is None or welcome["months"] < (chosen["without"] or 99))
    if use_welcome:
        plan_cards = owned + [{**welcome["card"], "points": 0}]
        assignments, monthly = assign_spend(plan_cards, award["program"], expenses, use_portals)
        bonus = int(welcome["card"]["welcome"]["points"])
        bonus_month = welcome["bonus_month"]
        months_with = welcome["months"]
    else:
        assignments, monthly = chosen["owned_assignments"], chosen["owned_monthly"]
        bonus = 0
        bonus_month = None
        months_with = chosen["without"]
    milestone = chosen["milestone"]
    milestone_points = milestone["points"] if milestone else 0
    milestone_at = milestone["month"] if milestone else None
    # Recompute milestone from the displayed assignments so a rent-earning card suppresses it.
    milestone = _milestone_month(expenses, award["currency"], assignments)
    milestone_points = milestone["points"] if milestone else 0
    milestone_at = milestone["month"] if milestone else None
    months_with = months_until(
        chosen["starting"],
        monthly,
        chosen["goal"],
        bonus,
        bonus_month,
        milestone_points,
        milestone_at,
    )
    months_without = months_until(
        chosen["starting"],
        chosen["owned_monthly"],
        chosen["goal"],
        0,
        None,
        chosen["milestone"]["points"] if chosen["milestone"] else 0,
        chosen["milestone"]["month"] if chosen["milestone"] else None,
    )
    halves = bool(
        months_with
        and months_without
        and months_without >= 2
        and months_with * 2 <= months_without
    )
    today = today or date.today()
    first = _next_month(today)
    departure = _add_months(first, months - 1)
    timeline = _timeline(
        chosen["starting"],
        monthly,
        chosen["goal"],
        bonus if use_welcome else 0,
        bonus_month if use_welcome else None,
        milestone_points,
        milestone_at,
        months,
        first,
    )
    recommendation = None
    if use_welcome:
        card = welcome["card"]
        recommendation = {
            "card_id": card["id"],
            "card_name": card["name"],
            "welcome_points": int(card["welcome"]["points"]),
            "spend": welcome["threshold"],
            "spend_currency": award["currency"],
            "days": int(card["welcome"]["days"]),
            "bonus_month": bonus_month,
            "multiplier_gain": welcome["multiplier_gain"],
            "blurb": card["blurb"],
        }
    alternates = []
    for option in (chosen["welcome_options"] or [])[1:3]:
        alternates.append(
            {
                "card_id": option["card"]["id"],
                "card_name": option["card"]["name"],
                "months": option["months"],
                "welcome_points": int(option["card"]["welcome"]["points"]),
            }
        )
    rent_tip = None
    rent_amount = expenses.get("rent", 0)
    owns_rent = any(card.get("rent_card") or int(card["multipliers"].get("rent", 0)) > 0 for card in owned)
    rent_row = next((row for row in assignments if row["category"] == "rent"), None)
    if rent_amount > 0 and not owns_rent and (not rent_row or rent_row["multiplier"] <= 0):
        rent_tip = {
            "card_id": "bilt",
            "card_name": "Bilt Mastercard",
            "extra_monthly_points": rent_amount,
            "note": (
                f"Rent is {money(rent_amount, award['currency'])} a month and earns nothing on the cards in this plan. "
                f"A rent card such as Bilt would add about {rent_amount:,} transferable points a month. "
                "It is not included in the timeline above."
            ),
        }
    points_needed = max(0, chosen["goal"] - chosen["starting"])
    result = {
        "origin": {"code": origin_airport["code"], "city": origin_airport["city"]},
        "destination": {"code": destination_airport["code"], "city": destination_airport["city"]},
        "months": months,
        "departure": departure.isoformat(),
        "departure_label": departure.strftime("%B %Y"),
        "use_portals": use_portals,
        "award": {
            "id": award["id"],
            "program_id": award["program"],
            "program": PROGRAMS[award["program"]]["name"],
            "alliance": PROGRAMS[award["program"]]["alliance"],
            "miles": chosen["goal"],
            "chart_miles": award["miles"],
            "taxes": award["taxes"],
            "cash": award["cash"],
            "currency": award["currency"],
        },
        "starting_points": chosen["starting"],
        "points_needed": points_needed,
        "monthly_points": monthly,
        "assignments": assignments,
        "months_without_bonus": months_without,
        "months_with_bonus": months_with,
        "halves_wait": halves,
        "recommendation": recommendation,
        "alternates": alternates,
        "milestone": milestone,
        "rent_tip": rent_tip,
        "timeline": timeline,
        "currency": award["currency"],
        "reachable": True,
    }
    result["narrative"] = write_strategy_narrative(result)
    result["booking_preview"] = {
        "origin": origin_airport["code"],
        "destination": destination_airport["code"],
        "date": departure.isoformat(),
        "program": result["award"]["program"],
        "miles": result["award"]["miles"],
        "taxes": result["award"]["taxes"],
        "currency": result["award"]["currency"],
    }
    return result


_AMOUNT = re.compile(
    r"(\d[\d,]*)(\s*k)?\s+(amex|membership rewards|chase|ultimate rewards|capital one|citi|thankyou|axis|hdfc|bilt)\b",
    re.IGNORECASE,
)
_CURRENCY_WORDS = [
    ("membership rewards", "amex_mr"),
    ("amex", "amex_mr"),
    ("ultimate rewards", "chase_ur"),
    ("chase", "chase_ur"),
    ("capital one", "capital_one"),
    ("thankyou", "citi_typ"),
    ("citi", "citi_typ"),
    ("axis", "axis_edge"),
    ("hdfc", "hdfc_smartbuy"),
    ("bilt", "bilt"),
]
_CARD_FOR_CURRENCY = {
    "amex_mr": "amex-gold",
    "chase_ur": "chase-sapphire-preferred",
    "capital_one": "capital-one-venture-x",
    "citi_typ": "citi-custom-cash",
    "axis_edge": "axis-magnus",
    "hdfc_smartbuy": "hdfc-infinia",
    "bilt": "bilt",
}


def _parse_amount(number: str, k_flag: str | None) -> int:
    value = int(number.replace(",", ""))
    if k_flag and "k" in k_flag.lower():
        value *= 1000
    return value


def parse_balances_from_text(message: str) -> list[dict]:
    found: dict[str, int] = {}
    for match in _AMOUNT.finditer(message or ""):
        amount = _parse_amount(match.group(1), match.group(2))
        word = match.group(3).lower()
        currency = next(code for label, code in _CURRENCY_WORDS if label == word or word.startswith(label))
        found[currency] = found.get(currency, 0) + amount
    balances = []
    for currency, points in found.items():
        balances.append({"id": _CARD_FOR_CURRENCY[currency], "points": points, "currency": currency})
    return balances


def _city_in_text(text: str) -> str | None:
    lowered = text.lower()
    for name, code in sorted(CITY_ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
        if re.search(rf"\b{re.escape(name)}\b", lowered):
            return code
    for item in AIRPORTS:
        if re.search(rf"\b{item['code']}\b", text, re.IGNORECASE):
            return item["code"]
    return None


def answer_copilot(
    message: str = "",
    balances: list[dict] | None = None,
    destination: str | None = None,
    origin: str | None = None,
) -> dict:
    """Answer a combine-points question from the transfer matrix. No model call."""
    parsed = parse_balances_from_text(message)
    if balances:
        resolved = _resolve_cards(balances)
    elif parsed:
        resolved = _resolve_cards([{"id": item["id"], "points": item["points"]} for item in parsed])
    else:
        raise EngineError("Tell me the balances, for example 25k Amex and 15k Chase.")
    dest_code = (destination or "").upper() or _destination_from_message(message) or ""
    if not dest_code:
        raise EngineError("Which city do you want to fly to?")
    dest = _require_airport(dest_code)
    origin_code = (origin or "").upper() or _origin_from_message(message) or ""
    by_program: dict[str, list[dict]] = {}
    for card in resolved:
        seen = set()
        for row in TRANSFERS:
            if row["from"] != card["currency"] or row["to"] in seen:
                continue
            seen.add(row["to"])
            miles = int(card["points"] * row["ratio"])
            by_program.setdefault(row["to"], []).append(
                {
                    "card_id": card["id"],
                    "card_name": card["name"],
                    "currency_label": CURRENCIES[card["currency"]]["label"],
                    "bank_points": card["points"],
                    "miles": miles,
                    "ratio": ratio_label(row["ratio"]),
                }
            )
    shared = {program: parts for program, parts in by_program.items() if len(parts) >= 2 and sum(p["miles"] for p in parts) > 0}
    pool = shared or by_program
    if not pool:
        raise EngineError("None of those currencies are on the sample transfer chart.")

    def _program_score(program: str) -> tuple:
        combined_miles = sum(part["miles"] for part in pool[program])
        award = _award_for_destination(program, dest["code"], origin_code)
        return (
            1 if award else 0,
            1 if award and combined_miles >= award["miles"] else 0,
            combined_miles,
            -(award["taxes"] if award else 0),
        )

    best_program = max(pool, key=_program_score)
    parts = pool[best_program]
    combined = sum(part["miles"] for part in parts)
    award = _award_for_destination(best_program, dest["code"], origin_code)
    program = PROGRAMS[best_program]
    if not award:
        answer = (
            f"{program['name']} is where these balances meet ({combined:,} miles together), "
            f"but the v1 chart has no {dest['city']} award on that program."
        )
        return {
            "can_combine": len(parts) >= 2,
            "answer": answer,
            "destination": {"code": dest["code"], "city": dest["city"]},
            "origin": None,
            "program": program["name"],
            "program_id": best_program,
            "combined_miles": combined,
            "miles_needed": None,
            "taxes": None,
            "cash": None,
            "currency": None,
            "parts": parts,
            "miles_left": None,
        }
    origin_airport = airport(award["origin"])
    can_book = combined >= award["miles"]
    left = combined - award["miles"]
    tax = money(award["taxes"], award["currency"])
    cash = money(award["cash"], award["currency"])
    part_text = " and ".join(f"{part['bank_points']:,} {part['currency_label']}" for part in parts)
    if len(parts) >= 2 and can_book:
        answer = (
            f"Yes. {part_text} both transfer into {program['name']}, so they can share one award. "
            f"Together that is {combined:,} miles. {origin_airport['city']} to {dest['city']} is "
            f"{award['miles']:,} miles plus about {tax} in taxes, against roughly {cash} cash. "
            f"You would have {left:,} miles left over. Transfer each balance from its own bank portal "
            f"into the same frequent-flyer account, then book."
        )
    elif len(parts) >= 2:
        answer = (
            f"They can share {program['name']} ({combined:,} miles together), "
            f"but {origin_airport['city']} to {dest['city']} needs {award['miles']:,} miles. "
            f"You are {award['miles'] - combined:,} miles short."
        )
    else:
        answer = (
            f"Those balances do not land in the same program on this chart. "
            f"The strongest single pile is {combined:,} {program['name']} miles."
        )
    return {
        "can_combine": len(parts) >= 2 and can_book,
        "answer": answer,
        "destination": {"code": dest["code"], "city": dest["city"]},
        "origin": {"code": origin_airport["code"], "city": origin_airport["city"]},
        "program": program["name"],
        "program_id": best_program,
        "combined_miles": combined,
        "miles_needed": award["miles"],
        "taxes": award["taxes"],
        "cash": award["cash"],
        "currency": award["currency"],
        "parts": parts,
        "miles_left": left if can_book else None,
        "deep_link": _search_url(best_program, award["origin"], award["destination"], date.today() + timedelta(days=110), "economy"),
    }


def _destination_from_message(message: str) -> str | None:
    match = re.search(r"\bto\s+([a-z][a-z\s]{1,40})", message or "", re.IGNORECASE)
    if match:
        code = _city_in_text(match.group(1))
        if code:
            return code
    return _city_in_text(message or "")


def _origin_from_message(message: str) -> str | None:
    match = re.search(r"\bfrom\s+([a-z][a-z\s]{1,40})", message or "", re.IGNORECASE)
    if not match:
        return None
    return _city_in_text(match.group(1))


def _award_for_destination(program_id: str, destination: str, origin: str) -> dict | None:
    awards = [award for award in AWARDS if award["program"] == program_id and destination in _award_pair(award)]
    if origin:
        directed = [award for award in awards if origin in _award_pair(award)]
        if directed:
            return directed[0]
    return awards[0] if awards else None


_AIRLINE_NAMES = {
    "air france": "Air France",
    "klm": "KLM",
    "iberia": "Iberia",
    "british airways": "British Airways",
    "qatar": "Qatar Airways",
    "singapore": "Singapore Airlines",
    "virgin atlantic": "Virgin Atlantic",
    "virgin": "Virgin Atlantic",
}


def parse_booking_text(text: str) -> dict:
    """Parse a pasted flights link or a line of text. Does not fetch the URL."""
    raw = (text or "").strip()
    if not raw:
        raise EngineError("Paste a flight link or a line like MAD to JFK on 2026-11-20.")
    origin, destination = _route_from_text(raw)
    if not origin or not destination:
        raise EngineError(
            "Could not find an origin and destination. Try a Skyscanner path like /flights/mad/jfk/261120 or 'Madrid to New York'.",
            extra={"example": "https://www.skyscanner.net/transport/flights/mad/jfk/261120"},
        )
    parsed_date = _date_from_text(raw)
    cash, currency = _price_from_text(raw)
    airline = ""
    lowered = raw.lower()
    for needle, name in _AIRLINE_NAMES.items():
        if needle in lowered:
            airline = name
            break
    flight = ""
    flight_match = re.search(r"\b([A-Z]{2})\s?(\d{2,4})\b", raw)
    if flight_match and flight_match.group(1) not in {"TO"}:
        flight = f"{flight_match.group(1)}{flight_match.group(2)}"
    return {
        "ok": True,
        "simulated": False,
        "origin": origin,
        "destination": destination,
        "date": parsed_date,
        "airline": airline,
        "flight_number": flight,
        "cash_price": cash,
        "currency": currency,
        "cabin": "business" if "business" in lowered else "economy",
        "note": "Parsed from the text you pasted. The link itself was not opened.",
    }


def _route_from_text(raw: str) -> tuple[str | None, str | None]:
    skyscanner = re.search(r"/flights/([a-z]{3})/([a-z]{3})/", raw, re.IGNORECASE)
    if skyscanner:
        return skyscanner.group(1).upper(), skyscanner.group(2).upper()
    mmt = re.search(r"\b([A-Za-z]{3})-([A-Za-z]{3})-(\d{2})/(\d{2})/(\d{4})\b", raw)
    if mmt and airport(mmt.group(1)) and airport(mmt.group(2)):
        return mmt.group(1).upper(), mmt.group(2).upper()
    pair = re.search(r"\b([A-Z]{3})\s*(?:to|→|-)\s*([A-Z]{3})\b", raw)
    if pair and airport(pair.group(1)) and airport(pair.group(2)):
        return pair.group(1), pair.group(2)
    lowered = raw.lower().replace("+", " ")
    to_match = re.search(r"\b([a-z][a-z\s]*?)\s+to\s+([a-z][a-z\s]*)", lowered)
    if to_match:
        origin = _city_in_text(to_match.group(1))
        destination = _city_in_text(to_match.group(2))
        if origin and destination:
            return origin, destination
    return None, None


def _date_from_text(raw: str) -> str | None:
    iso = re.search(r"(20\d{2})-(\d{2})-(\d{2})", raw)
    if iso:
        return f"{iso.group(1)}-{iso.group(2)}-{iso.group(3)}"
    sky = re.search(r"/(\d{2})(\d{2})(\d{2})(?:/|$)", raw)
    if sky:
        year = 2000 + int(sky.group(1))
        return f"{year:04d}-{sky.group(2)}-{sky.group(3)}"
    mmt = re.search(r"\b(\d{2})/(\d{2})/(20\d{2})\b", raw)
    if mmt:
        return f"{mmt.group(3)}-{mmt.group(2)}-{mmt.group(1)}"
    return None


def _price_from_text(raw: str) -> tuple[int | None, str | None]:
    euro = re.search(r"€\s?([\d,]+)", raw)
    if euro:
        return int(euro.group(1).replace(",", "")), "EUR"
    inr = re.search(r"(?:₹|Rs\.?)\s?([\d,]+)", raw, re.IGNORECASE)
    if inr:
        return int(inr.group(1).replace(",", "")), "INR"
    labeled = re.search(r"(?:price|fare)\s*[:=]\s*([\d,]+)", raw, re.IGNORECASE)
    if labeled:
        return int(labeled.group(1).replace(",", "")), None
    return None, None


def parse_screenshot(content: bytes, filename: str = "") -> dict:
    """Simulated vision parse. Replace with a multimodal model later."""
    if not content or len(content) < 16:
        raise EngineError("That file is empty.")
    if not (
        content.startswith(b"\x89PNG")
        or content.startswith(b"\xff\xd8")
        or content.startswith(b"GIF")
        or content[:4] == b"RIFF"
    ):
        raise EngineError("Upload a PNG, JPEG, GIF, or WebP screenshot.")
    origin, destination = "MAD", "JFK"
    codes = re.findall(r"\b([A-Za-z]{3})\b", filename or "")
    airports = [code.upper() for code in codes if airport(code)]
    if len(airports) >= 2:
        origin, destination = airports[0], airports[1]
    sample = {
        "MAD": ("JFK", 850, "EUR", "Air France", "AF1021"),
        "DEL": ("LHR", 55000, "INR", "Air India", "AI111"),
        "CDG": ("HND", 1180, "EUR", "Air France", "AF272"),
    }
    dest, price, currency, airline, flight = sample.get(origin, ("JFK", 850, "EUR", "Air France", "AF1021"))
    if len(airports) >= 2:
        destination = airports[1]
    else:
        destination = dest
    return {
        "ok": True,
        "simulated": True,
        "origin": origin,
        "destination": destination,
        "date": (date.today() + timedelta(days=25)).isoformat(),
        "airline": airline,
        "flight_number": flight,
        "cash_price": price,
        "currency": currency,
        "cabin": "economy",
        "note": "Simulated screenshot read for v1. A vision model can replace parse_screenshot later. The image was not sent to a model.",
    }


def catalog_payload() -> dict:
    return {
        "airports": AIRPORTS,
        "cards": [
            {
                "id": card["id"],
                "name": card["name"],
                "issuer": card["issuer"],
                "currency": card["currency"],
                "currency_label": CURRENCIES[card["currency"]]["label"],
                "region": card["region"],
                "multipliers": card["multipliers"],
                "welcome": card["welcome"],
                "blurb": card["blurb"],
                "rent_card": card.get("rent_card", False),
                "top_category_only": card.get("top_category_only", False),
            }
            for card in CARDS
        ],
        "categories": CATEGORIES,
        "programs": [
            {"id": key, "name": value["name"], "alliance": value["alliance"]}
            for key, value in PROGRAMS.items()
        ],
    }


def transfers_payload() -> list[dict]:
    rows = []
    for row in TRANSFERS:
        program = PROGRAMS[row["to"]]
        rows.append(
            {
                "currency": row["from"],
                "currency_label": CURRENCIES[row["from"]]["label"],
                "issuer": CURRENCIES[row["from"]]["issuer"],
                "program_id": row["to"],
                "program": program["name"],
                "alliance": program["alliance"],
                "ratio": ratio_label(row["ratio"]),
                "sweet_spot": row.get("sweet_spot") or "",
                "sample": bool(row.get("sample")),
            }
        )
    return rows


def routes_payload() -> list[dict]:
    seen = set()
    rows = []
    for award in AWARDS:
        key = tuple(sorted(_award_pair(award)))
        if key in seen:
            continue
        seen.add(key)
        origin = airport(award["origin"])
        destination = airport(award["destination"])
        rows.append(
            {
                "origin": award["origin"],
                "destination": award["destination"],
                "origin_city": origin["city"],
                "destination_city": destination["city"],
                "cash": award["cash"],
                "currency": award["currency"],
                "label": f"{origin['city']} → {destination['city']}",
            }
        )
    return rows
