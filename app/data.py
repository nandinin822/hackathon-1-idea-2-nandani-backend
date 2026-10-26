"""Mock catalogs for BookMyflight v1.

No live Duffel, Amadeus, Seats.aero, or bank feeds. Numbers are a teaching
sample shaped like those sources, tuned so the three judge demos stay stable.
"""

from __future__ import annotations

from datetime import date, timedelta

CATEGORIES = [
    {"id": "groceries", "label": "Groceries", "hint": "Supermarkets and food shops"},
    {"id": "dining", "label": "Dining & delivery", "hint": "Restaurants and food delivery"},
    {"id": "shopping", "label": "Shopping", "hint": "Retail and online orders"},
    {"id": "bills", "label": "Bills & utilities", "hint": "Phone, power, insurance"},
    {"id": "rent", "label": "Rent", "hint": "Monthly rent"},
]

# Extra points on top of the card rate when the person uses a shopping or dining portal.
PORTAL_BONUS = {"dining": 4, "shopping": 2}

# Flat household bonus once bills + rent cross a spend threshold.
# Applied only when no owned card earns a monthly rent multiplier.
MILESTONES = {
    "EUR": {"threshold": 8000, "points": 8000},
    "INR": {"threshold": 80000, "points": 8000},
}

AIRPORTS = [
    {"code": "MAD", "city": "Madrid", "country": "Spain"},
    {"code": "BCN", "city": "Barcelona", "country": "Spain"},
    {"code": "GRO", "city": "Girona", "country": "Spain"},
    {"code": "LIS", "city": "Lisbon", "country": "Portugal"},
    {"code": "CDG", "city": "Paris", "country": "France"},
    {"code": "ORY", "city": "Paris Orly", "country": "France"},
    {"code": "LHR", "city": "London", "country": "United Kingdom"},
    {"code": "LGW", "city": "London Gatwick", "country": "United Kingdom"},
    {"code": "AMS", "city": "Amsterdam", "country": "Netherlands"},
    {"code": "JFK", "city": "New York", "country": "United States"},
    {"code": "EWR", "city": "Newark", "country": "United States"},
    {"code": "DEL", "city": "Delhi", "country": "India"},
    {"code": "DXB", "city": "Dubai", "country": "United Arab Emirates"},
    {"code": "DOH", "city": "Doha", "country": "Qatar"},
    {"code": "HND", "city": "Tokyo", "country": "Japan"},
    {"code": "NRT", "city": "Tokyo Narita", "country": "Japan"},
    {"code": "DPS", "city": "Bali", "country": "Indonesia"},
    {"code": "SIN", "city": "Singapore", "country": "Singapore"},
]

# Secondary airports within about an hour by train or bus.
NEARBY = {
    "JFK": [{"code": "EWR", "city": "Newark", "minutes": 50, "mode": "train"}],
    "EWR": [{"code": "JFK", "city": "New York (JFK)", "minutes": 50, "mode": "train"}],
    "LHR": [{"code": "LGW", "city": "Gatwick", "minutes": 70, "mode": "train"}],
    "LGW": [{"code": "LHR", "city": "Heathrow", "minutes": 70, "mode": "train"}],
    "BCN": [{"code": "GRO", "city": "Girona", "minutes": 75, "mode": "bus"}],
    "GRO": [{"code": "BCN", "city": "Barcelona", "minutes": 75, "mode": "bus"}],
    "CDG": [{"code": "ORY", "city": "Orly", "minutes": 55, "mode": "train"}],
    "ORY": [{"code": "CDG", "city": "Charles de Gaulle", "minutes": 55, "mode": "train"}],
    "HND": [{"code": "NRT", "city": "Narita", "minutes": 90, "mode": "bus"}],
    "NRT": [{"code": "HND", "city": "Haneda", "minutes": 70, "mode": "train"}],
}

CURRENCIES = {
    "amex_mr": {
        "label": "Membership Rewards",
        "issuer": "American Express",
        "portal_url": "https://global.americanexpress.com/rewards/transfer",
        "portal_label": "Open the Amex transfer portal",
    },
    "chase_ur": {
        "label": "Ultimate Rewards",
        "issuer": "Chase",
        "portal_url": "https://ultimaterewardspoints.chase.com/",
        "portal_label": "Open the Chase transfer portal",
    },
    "capital_one": {
        "label": "Capital One Miles",
        "issuer": "Capital One",
        "portal_url": "https://www.capitalone.com/credit-cards/benefits/travel/",
        "portal_label": "Open Capital One travel",
    },
    "citi_typ": {
        "label": "ThankYou Points",
        "issuer": "Citi",
        "portal_url": "https://www.thankyou.com/",
        "portal_label": "Open Citi ThankYou",
    },
    "axis_edge": {
        "label": "Edge Miles",
        "issuer": "Axis Bank",
        "portal_url": "https://www.axisbank.com/retail/cards/credit-card",
        "portal_label": "Open Axis rewards",
    },
    "hdfc_smartbuy": {
        "label": "SmartBuy points",
        "issuer": "HDFC Bank",
        "portal_url": "https://offers.smartbuy.hdfcbank.com/",
        "portal_label": "Open HDFC SmartBuy",
    },
    "bilt": {
        "label": "Bilt Points",
        "issuer": "Bilt",
        "portal_url": "https://www.biltrewards.com/",
        "portal_label": "Open Bilt",
    },
}

PROGRAMS = {
    "flying_blue": {
        "name": "Air France/KLM Flying Blue",
        "alliance": "SkyTeam",
        "search_url": "https://www.flyingblue.com/en/spend/flights",
    },
    "iberia_plus": {
        "name": "Iberia Plus",
        "alliance": "Oneworld",
        "search_url": "https://www.iberia.com/us/flight-search/",
    },
    "ba_avios": {
        "name": "British Airways Club",
        "alliance": "Oneworld",
        "search_url": "https://www.britishairways.com/travel/redeem/public/en_us",
    },
    "virgin_atlantic": {
        "name": "Virgin Atlantic Flying Club",
        # Virgin Atlantic is not a SkyTeam member. The product-spec sample table
        # lists it under SkyTeam; the demo keeps the real status.
        "alliance": "Non-alliance partner",
        "search_url": "https://www.virginatlantic.com/reward-flight-finder",
    },
    "lifemiles": {
        "name": "Avianca LifeMiles",
        "alliance": "Star Alliance",
        "search_url": "https://www.lifemiles.com/fly/find",
    },
    "krisflyer": {
        "name": "Singapore KrisFlyer",
        "alliance": "Star Alliance",
        "search_url": "https://www.singaporeair.com/en_UK/plan-and-book/redeem-miles/",
    },
    "qatar": {
        "name": "Qatar Privilege Club",
        "alliance": "Oneworld",
        "search_url": "https://www.qatarairways.com/en/book-a-flight.html",
    },
}

# ratio = airline miles received per 1 bank point. 0.5 means 2:1.
TRANSFERS = [
    {
        "from": "amex_mr",
        "to": "iberia_plus",
        "ratio": 1.0,
        "sweet_spot": "Madrid ↔ NYC (34k Avios)",
        "sample": True,
    },
    {
        "from": "amex_mr",
        "to": "ba_avios",
        "ratio": 1.0,
        "sweet_spot": "Madrid ↔ NYC (34k Avios)",
        "sample": True,
    },
    {
        "from": "amex_mr",
        "to": "flying_blue",
        "ratio": 1.0,
        "sweet_spot": "Europe ↔ US East Coast (often from 20k)",
        "sample": True,
    },
    {
        "from": "chase_ur",
        "to": "virgin_atlantic",
        "ratio": 1.0,
        "sweet_spot": "London ↔ US East Coast (10k pts)",
        "sample": True,
    },
    {
        "from": "chase_ur",
        "to": "flying_blue",
        "ratio": 1.0,
        "sweet_spot": "",
        "sample": False,
    },
    {
        "from": "chase_ur",
        "to": "ba_avios",
        "ratio": 1.0,
        "sweet_spot": "",
        "sample": False,
    },
    {
        "from": "capital_one",
        "to": "lifemiles",
        "ratio": 1.0,
        "sweet_spot": "US ↔ Europe (no fuel surcharges)",
        "sample": True,
    },
    {
        "from": "citi_typ",
        "to": "lifemiles",
        "ratio": 1.0,
        "sweet_spot": "US ↔ Europe (no fuel surcharges)",
        "sample": True,
    },
    {
        "from": "citi_typ",
        "to": "flying_blue",
        "ratio": 1.0,
        "sweet_spot": "",
        "sample": False,
    },
    {
        "from": "axis_edge",
        "to": "krisflyer",
        "ratio": 0.5,
        "sweet_spot": "India ↔ SE Asia / Europe",
        "sample": True,
    },
    {
        "from": "axis_edge",
        "to": "qatar",
        "ratio": 0.5,
        "sweet_spot": "India ↔ SE Asia / Europe",
        "sample": True,
    },
    {
        "from": "hdfc_smartbuy",
        "to": "krisflyer",
        "ratio": 1.0,
        "sweet_spot": "India ↔ SE Asia / Europe",
        "sample": True,
    },
    {
        "from": "hdfc_smartbuy",
        "to": "qatar",
        "ratio": 1.0,
        "sweet_spot": "India ↔ SE Asia / Europe",
        "sample": True,
    },
    {
        "from": "bilt",
        "to": "flying_blue",
        "ratio": 1.0,
        "sweet_spot": "",
        "sample": False,
    },
    {
        "from": "bilt",
        "to": "ba_avios",
        "ratio": 1.0,
        "sweet_spot": "",
        "sample": False,
    },
]

CARDS = [
    {
        "id": "amex-gold",
        "name": "Amex Gold",
        "issuer": "American Express",
        "currency": "amex_mr",
        "region": "International",
        "multipliers": {"groceries": 4, "dining": 4, "shopping": 1, "bills": 1, "rent": 0},
        "welcome": None,
        "top_category_only": False,
        "rent_card": False,
        "blurb": "4× on groceries and dining.",
    },
    {
        "id": "chase-sapphire-preferred",
        "name": "Chase Sapphire Preferred",
        "issuer": "Chase",
        "currency": "chase_ur",
        "region": "United States",
        "multipliers": {"groceries": 3, "dining": 3, "shopping": 1, "bills": 1, "rent": 0},
        "welcome": {"points": 30000, "spend": 2000, "days": 90, "currency": "EUR"},
        "top_category_only": False,
        "rent_card": False,
        "blurb": "30,000 points after €2,000 spend in 90 days.",
    },
    {
        "id": "citi-custom-cash",
        "name": "Citi Custom Cash",
        "issuer": "Citi",
        "currency": "citi_typ",
        "region": "United States",
        "multipliers": {"groceries": 1, "dining": 1, "shopping": 1, "bills": 1, "rent": 0},
        "welcome": {"points": 20000, "spend": 1500, "days": 90, "currency": "EUR"},
        "top_category_only": True,
        "top_multiplier": 5,
        "rent_card": False,
        "blurb": "5× on your highest spend category.",
    },
    {
        "id": "capital-one-venture-x",
        "name": "Capital One Venture X",
        "issuer": "Capital One",
        "currency": "capital_one",
        "region": "United States",
        "multipliers": {"groceries": 2, "dining": 2, "shopping": 2, "bills": 2, "rent": 1},
        "welcome": None,
        "top_category_only": False,
        "rent_card": False,
        "blurb": "2× on everyday spend. Transfers to LifeMiles.",
    },
    {
        "id": "axis-magnus",
        "name": "Axis Magnus",
        "issuer": "Axis Bank",
        "currency": "axis_edge",
        "region": "India",
        "multipliers": {"groceries": 2, "dining": 5, "shopping": 5, "bills": 2, "rent": 0},
        "welcome": None,
        "top_category_only": False,
        "rent_card": False,
        "blurb": "5× on dining and shopping. Transfers at 2:1.",
    },
    {
        "id": "hdfc-infinia",
        "name": "HDFC Infinia",
        "issuer": "HDFC Bank",
        "currency": "hdfc_smartbuy",
        "region": "India",
        "multipliers": {"groceries": 5, "dining": 5, "shopping": 5, "bills": 3, "rent": 0},
        "welcome": None,
        "top_category_only": False,
        "rent_card": False,
        "blurb": "5× on groceries, dining, and shopping. Transfers at 1:1.",
    },
    {
        "id": "bilt",
        "name": "Bilt Mastercard",
        "issuer": "Bilt",
        "currency": "bilt",
        "region": "United States",
        "multipliers": {"groceries": 1, "dining": 1, "shopping": 1, "bills": 1, "rent": 1},
        "welcome": None,
        "top_category_only": False,
        "rent_card": True,
        "blurb": "1× on rent, transferable to airlines.",
    },
]

# Judge-demo why copy, used verbatim when the booking is this award from Amex.
MADRID_NYC_WHY = (
    "Air France Flying Blue is running a 25% promo reward this month. "
    "By transferring 30,000 points from your Amex card at a 1:1 ratio, "
    "you unlock a seat that would otherwise cost €850 in cash."
)

AWARDS = [
    {
        "id": "fb-mad-jfk",
        "origin": "MAD",
        "destination": "JFK",
        "program": "flying_blue",
        "miles": 30000,
        "taxes": 60,
        "cash": 850,
        "currency": "EUR",
        "cabin": "economy",
        "promo": "25% promo reward",
        "why": MADRID_NYC_WHY,
    },
    {
        "id": "ib-mad-jfk",
        "origin": "MAD",
        "destination": "JFK",
        "program": "iberia_plus",
        "miles": 34000,
        "taxes": 95,
        "cash": 850,
        "currency": "EUR",
        "cabin": "economy",
        "promo": "",
        "why": "",
    },
    {
        "id": "fb-mad-ewr",
        "origin": "MAD",
        "destination": "EWR",
        "program": "flying_blue",
        "miles": 30000,
        "taxes": 55,
        "cash": 830,
        "currency": "EUR",
        "cabin": "economy",
        "promo": "",
        "why": "",
    },
    {
        "id": "kf-del-lhr",
        "origin": "DEL",
        "destination": "LHR",
        "program": "krisflyer",
        "miles": 42000,
        "taxes": 3500,
        "cash": 55000,
        "currency": "INR",
        "cabin": "economy",
        "promo": "",
        "why": "",
    },
    {
        "id": "qr-del-lhr",
        "origin": "DEL",
        "destination": "LHR",
        "program": "qatar",
        "miles": 40000,
        "taxes": 4200,
        "cash": 55000,
        "currency": "INR",
        "cabin": "economy",
        "promo": "",
        "why": "",
        "stopover": {
            "airport": "DOH",
            "city": "Doha",
            "note": "Qatar Airways allows a free stopover in Doha on this award.",
        },
    },
    {
        "id": "fb-cdg-hnd",
        "origin": "CDG",
        "destination": "HND",
        "program": "flying_blue",
        "miles": 70000,
        "taxes": 180,
        "cash": 1180,
        "currency": "EUR",
        "cabin": "economy",
        "promo": "",
        "why": "",
    },
    {
        "id": "fb-mad-dps",
        "origin": "MAD",
        "destination": "DPS",
        "program": "flying_blue",
        "miles": 60000,
        "taxes": 95,
        "cash": 1080,
        "currency": "EUR",
        "cabin": "economy",
        "promo": "",
        "why": "",
    },
    {
        "id": "lm-mad-dps",
        "origin": "MAD",
        "destination": "DPS",
        "program": "lifemiles",
        "miles": 70000,
        "taxes": 80,
        "cash": 1080,
        "currency": "EUR",
        "cabin": "economy",
        "promo": "",
        "why": "",
        "stopover": {
            "airport": "LIS",
            "city": "Lisbon",
            "note": "TAP Portugal awards booked with LifeMiles can include a free Lisbon stopover.",
        },
    },
    {
        "id": "kf-mad-dps",
        "origin": "MAD",
        "destination": "DPS",
        "program": "krisflyer",
        "miles": 55000,
        "taxes": 110,
        "cash": 1080,
        "currency": "EUR",
        "cabin": "economy",
        "promo": "",
        "why": "",
    },
    {
        "id": "fb-lhr-dxb",
        "origin": "LHR",
        "destination": "DXB",
        "program": "flying_blue",
        "miles": 35000,
        "taxes": 85,
        "cash": 640,
        "currency": "EUR",
        "cabin": "economy",
        "promo": "Monthly promo",
        "why": "",
    },
    {
        "id": "va-lhr-jfk",
        "origin": "LHR",
        "destination": "JFK",
        "program": "virgin_atlantic",
        "miles": 10000,
        "taxes": 120,
        "cash": 520,
        "currency": "EUR",
        "cabin": "economy",
        "promo": "",
        "why": "",
    },
    {
        "id": "lm-jfk-lhr",
        "origin": "JFK",
        "destination": "LHR",
        "program": "lifemiles",
        "miles": 30000,
        "taxes": 45,
        "cash": 690,
        "currency": "EUR",
        "cabin": "economy",
        "promo": "",
        "why": "",
        "note": "LifeMiles prices this corridor without the usual fuel surcharge.",
    },
    {
        "id": "fb-bcn-jfk",
        "origin": "BCN",
        "destination": "JFK",
        "program": "flying_blue",
        "miles": 36000,
        "taxes": 75,
        "cash": 790,
        "currency": "EUR",
        "cabin": "economy",
        "promo": "",
        "why": "",
    },
]

CITY_ALIASES = {
    "madrid": "MAD",
    "barcelona": "BCN",
    "girona": "GRO",
    "lisbon": "LIS",
    "lisboa": "LIS",
    "paris": "CDG",
    "orly": "ORY",
    "london": "LHR",
    "heathrow": "LHR",
    "gatwick": "LGW",
    "amsterdam": "AMS",
    "new york": "JFK",
    "nyc": "JFK",
    "jfk": "JFK",
    "newark": "EWR",
    "delhi": "DEL",
    "new delhi": "DEL",
    "dubai": "DXB",
    "doha": "DOH",
    "tokyo": "HND",
    "haneda": "HND",
    "narita": "NRT",
    "bali": "DPS",
    "denpasar": "DPS",
    "singapore": "SIN",
}

STOPOVER_NOTES = {
    "LIS": "TAP Portugal often allows a free Lisbon stopover when the award is on TAP metal.",
    "DOH": "Qatar Airways often allows a free Doha stopover on Privilege Club awards.",
}


def airport(code: str) -> dict | None:
    code = (code or "").upper()
    for item in AIRPORTS:
        if item["code"] == code:
            return item
    return None


def card_by_id(card_id: str) -> dict | None:
    for card in CARDS:
        if card["id"] == card_id:
            return card
    return None


def currency_meta(currency: str) -> dict:
    return CURRENCIES[currency]


def program_meta(program_id: str) -> dict:
    return PROGRAMS[program_id]


def best_transfer(currency: str, program_id: str) -> dict | None:
    rows = [row for row in TRANSFERS if row["from"] == currency and row["to"] == program_id]
    if not rows:
        return None
    return max(rows, key=lambda row: row["ratio"])


def demos() -> list[dict]:
    soon = (date.today() + timedelta(days=25)).isoformat()
    later = (date.today() + timedelta(days=80)).isoformat()
    dubai = (date.today() + timedelta(days=110)).isoformat()
    return [
        {
            "id": "euro-850",
            "pathway": "hack",
            "title": "€850 → €60 + 30k points",
            "detail": "Madrid to New York. You save 92%.",
            "hack": {
                "origin": "MAD",
                "destination": "JFK",
                "date": soon,
                "cabin": "economy",
                "passengers": 1,
                "flexible": True,
                "nearby": True,
                "via": None,
                "return_date": None,
                "cards": [{"id": "amex-gold", "points": 42000}],
            },
        },
        {
            "id": "inr-3500",
            "pathway": "hack",
            "title": "₹55,000 → ₹3,500 taxes",
            "detail": "Delhi to London on KrisFlyer.",
            "hack": {
                "origin": "DEL",
                "destination": "LHR",
                "date": later,
                "cabin": "economy",
                "passengers": 1,
                "flexible": False,
                "nearby": True,
                "via": None,
                "return_date": None,
                "cards": [{"id": "hdfc-infinia", "points": 60000}],
            },
        },
        {
            "id": "bali",
            "pathway": "plan",
            "title": "Bali in 8 months",
            "detail": "Funded by groceries, dining, and the household bills.",
            "strategy": {
                "origin": "MAD",
                "destination": "DPS",
                "months": 8,
                "use_portals": True,
                "cards": [{"id": "amex-gold", "points": 12000}],
                "monthly_expenses": {
                    "groceries": 500,
                    "dining": 250,
                    "shopping": 250,
                    "bills": 250,
                    "rent": 1200,
                },
            },
        },
        {
            "id": "dubai-combine",
            "pathway": "copilot",
            "title": "Combine points to Dubai",
            "detail": "25k Amex and 15k Chase into one Flying Blue award.",
            "copilot": {
                "message": "I have 25k Amex points and 15k Chase points, can I combine them to fly to Dubai?",
                "origin": "LHR",
                "destination": "DXB",
                "balances": [
                    {"id": "amex-gold", "points": 25000},
                    {"id": "chase-sapphire-preferred", "points": 15000},
                ],
            },
            "hack": {
                "origin": "LHR",
                "destination": "DXB",
                "date": dubai,
                "cabin": "economy",
                "passengers": 1,
                "flexible": False,
                "nearby": False,
                "via": None,
                "return_date": None,
                "cards": [
                    {"id": "amex-gold", "points": 25000},
                    {"id": "chase-sapphire-preferred", "points": 15000},
                ],
            },
        },
    ]


def demo_by_id(demo_id: str) -> dict | None:
    for demo in demos():
        if demo["id"] == demo_id:
            return demo
    return None
