"""BookMyflight API. Mock award chart, no paid data or model keys."""

from __future__ import annotations

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from app.data import demo_by_id, demos
from app.engine import (
    EngineError,
    answer_copilot,
    calculate_hacked_price,
    catalog_payload,
    generate_spend_strategy,
    parse_booking_text,
    parse_screenshot,
    routes_payload,
    transfers_payload,
)

app = FastAPI(title="BookMyflight", version="1.0.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5173",
        "http://localhost:5173",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


class CardIn(BaseModel):
    id: str
    points: int = Field(default=0, ge=0)


class HackIn(BaseModel):
    origin: str
    destination: str
    date: str | None = None
    cabin: str = "economy"
    passengers: int = Field(default=1, ge=1, le=9)
    cards: list[CardIn] = []
    flexible: bool = False
    nearby: bool = True
    via: str | None = None
    return_date: str | None = None


class StrategyIn(BaseModel):
    origin: str
    destination: str
    months: int = Field(default=8, ge=1, le=24)
    monthly_expenses: dict[str, float]
    cards: list[CardIn]
    use_portals: bool = True
    target_points: int | None = Field(default=None, ge=0)


class ParseIn(BaseModel):
    text: str


class CopilotIn(BaseModel):
    message: str = ""
    balances: list[CardIn] | None = None
    destination: str | None = None
    origin: str | None = None


def _fail(exc: EngineError) -> None:
    raise HTTPException(status_code=exc.status, detail={"message": exc.message, **exc.extra})


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "service": "bookmyflight"}


@app.get("/api/catalog")
def catalog() -> dict:
    return catalog_payload()


@app.get("/api/transfers")
def transfers() -> dict:
    return {"transfers": transfers_payload()}


@app.get("/api/routes")
def routes() -> dict:
    return {"routes": routes_payload()}


@app.get("/api/demos")
def list_demos() -> dict:
    return {"demos": demos()}


@app.post("/api/hack")
def hack(body: HackIn) -> dict:
    try:
        return calculate_hacked_price(
            origin=body.origin,
            destination=body.destination,
            cards=[card.model_dump() for card in body.cards],
            date_value=body.date,
            cabin=body.cabin,
            passengers=body.passengers,
            flexible=body.flexible,
            nearby=body.nearby,
            via=body.via,
            return_date=body.return_date,
        )
    except EngineError as exc:
        _fail(exc)


@app.post("/api/strategy")
def strategy(body: StrategyIn) -> dict:
    try:
        return generate_spend_strategy(
            target_points=body.target_points,
            months=body.months,
            monthly_expenses=body.monthly_expenses,
            cards=[card.model_dump() for card in body.cards],
            origin=body.origin,
            destination=body.destination,
            use_portals=body.use_portals,
        )
    except EngineError as exc:
        _fail(exc)


@app.post("/api/parse")
def parse_link(body: ParseIn) -> dict:
    try:
        return parse_booking_text(body.text)
    except EngineError as exc:
        _fail(exc)


@app.post("/api/parse-screenshot")
async def parse_shot(file: UploadFile = File(...)) -> dict:
    content = await file.read()
    if len(content) > 5_000_000:
        raise HTTPException(status_code=400, detail={"message": "Screenshot must be under 5 MB."})
    try:
        return parse_screenshot(content, file.filename or "")
    except EngineError as exc:
        _fail(exc)


@app.post("/api/copilot")
def copilot(body: CopilotIn) -> dict:
    try:
        balances = [card.model_dump() for card in body.balances] if body.balances else None
        return answer_copilot(
            message=body.message,
            balances=balances,
            destination=body.destination,
            origin=body.origin,
        )
    except EngineError as exc:
        _fail(exc)


@app.get("/api/demos/{demo_id}")
def one_demo(demo_id: str) -> dict:
    demo = demo_by_id(demo_id)
    if not demo:
        raise HTTPException(status_code=404, detail={"message": "Unknown demo."})
    return demo
