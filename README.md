# BookMyflight API

This repository is the API. It prices a cash fare against an award, builds an eight-month points plan, reads a booking link, and answers whether two card balances can share one ticket.

The product plan, the screens, and how a full trip is checked are in the frontend repository: [hackathon-1-idea-2-nandani-frontend](https://github.com/nandinin822/hackathon-1-idea-2-nandani-frontend).

The question the API answers is: how much could this user save on this trip?

## What this service does

A quick flight takes an origin, a destination, a date, a cabin, travellers, and the cards in the wallet. The response is the normal price, the hacked price (taxes plus miles), the saving, the transfer, and three booking steps.

A full trip adds flexible dates, nearby airports, a stopover, and a return date. A return is priced as two one-way awards. Travellers scale the miles, the taxes, and the cash fare.

A plan takes monthly groceries, dining, shopping, bills, and rent. Each category is placed on the card that earns the most miles in a program those cards can transfer into. A new card is recommended only when its welcome bonus books the trip sooner.

Points move from a bank currency into one airline program. They do not move from one bank to another. Two cards combine only when both transfer into the same program.

## The five systems

| Job | Planned source | In this repository now |
| --- | --- | --- |
| Advisor | Gemini 1.5 Flash or GPT-4o-mini | `answer_copilot` and `write_strategy_narrative` write the sentences from the chart. No model call. |
| Link and screenshot | Gemini vision, plus a text parser | `POST /api/parse` reads a link or a line of text. `POST /api/parse-screenshot` checks the file type and returns a sample booking. The image is not sent to a model. |
| Cash price | Amadeus, Duffel, or SerpApi | The cash fare is the number stored on the sample award chart. |
| Awards and transfers | Rules engine, plus Seats.aero or Roame | The chart, the ratios, nearby airports, and the spend planner are implemented in `app/engine.py`. Live seat search is not called. |
| Booking | Deep link to the airline award page | Step 2 of the checklist is that link, with origin, destination, date, and cabin. |

The model must not invent a fare, a mileage number, or a transfer ratio. It explains the result the engine returned.

## Database

MongoDB is the database. It stores what the user created. The award chart and the transfer ratios stay in the rules engine. A live fare is fetched when a trip is checked, then that quote is saved.

| Collection | What it holds |
| --- | --- |
| `users` | The account. No bank login. Balances are what the user typed. |
| `wallets` | Cards and point balances for that user. |
| `trips` | A quick flight or a full trip: stops, dates, travellers, cabin. |
| `quotes` | Cash price, hacked price, saving, and the program for one check. |
| `plans` | The eight-month roadmap, the recommended card, and the month the award unlocks. |
| `savedTrips` | Trips the user kept, so the home screen can total the savings. |

This demo does not connect to MongoDB yet. The sample catalog is `app/data.py`.

## Run

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Docs: http://127.0.0.1:8000/docs

The browser origins allowed by CORS are `http://127.0.0.1:5173` and `http://localhost:5173`.

Tests:

```bash
.venv/bin/pytest
```

## API

| Method | Path | Role |
| --- | --- | --- |
| GET | `/api/health` | Service is up |
| GET | `/api/catalog` | Airports, cards, spend categories, programs |
| GET | `/api/transfers` | Bank currency to airline program, ratio, and sweet spot |
| GET | `/api/routes` | City pairs the chart can price |
| GET | `/api/demos` | The four judge demos |
| GET | `/api/demos/{demo_id}` | One demo |
| POST | `/api/hack` | Cash fare versus the award the supplied cards can reach |
| POST | `/api/strategy` | Spend plan and new-card recommendation |
| POST | `/api/parse` | Body `{ "text": "..." }`. A booking link or a line of text |
| POST | `/api/parse-screenshot` | Multipart image, under 5 MB. PNG, JPEG, GIF, or WebP |
| POST | `/api/copilot` | `message`, and optional `balances`, `origin`, `destination` |

`POST /api/hack` accepts `origin`, `destination`, optional `date`, `cabin` (`economy` or `business`), `passengers` (1 to 9), `cards` as `{ "id", "points" }`, `flexible`, `nearby`, `via`, and `return_date`.

`POST /api/strategy` accepts `origin`, `destination`, `months` (1 to 24), `monthly_expenses`, `cards`, `use_portals`, and an optional `target_points` that overrides the chart.

Errors return a JSON `detail.message`.

## Rules the engine already applies

- Portal extras, when enabled, add 4x on dining and 2x on shopping.
- Citi Custom Cash applies 5x to one top category: groceries, dining, or shopping.
- A household milestone adds 8,000 points after 8,000 euros or 80,000 rupees of bills plus rent, and only when rent itself earns nothing.
- If rent earns nothing, a Bilt tip is returned and is not added to the timeline.
- Business class is accepted and priced as economy, with a note. A stopover is a note unless that city is already on the chart.
- A ratio of 0.5 is shown as 2:1. Axis Edge Miles to KrisFlyer is 2:1.

## Judge demos

| Demo | Result |
| --- | --- |
| `euro-850` | Madrid to New York. Cash 850 euros. Hacked fare 60 euros plus 30,000 Flying Blue miles. 92 percent off. |
| `inr-3500` | Delhi to London. Cash 55,000 rupees. Tax 3,500 rupees plus 42,000 KrisFlyer miles. |
| `bali` | Madrid to Bali in 8 months from grocery, dining, and household spend. Chase Sapphire Preferred cuts the wait from 8 months to 4. |
| `dubai-combine` | 25,000 Amex and 15,000 Chase combine in Flying Blue: 40,000 miles for a 35,000-mile award. |

Confirm the seat on the airline site before moving points. Transfers usually cannot be reversed.
