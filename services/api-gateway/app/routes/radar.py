import re
from datetime import datetime, timezone
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from fastapi import APIRouter, Depends

from ..clients.catalog import search_catalog
from ..config import Settings, get_settings

router = APIRouter()

COE_EVENTS_URL = "https://www.coe.edu/why-coe/events/calendar"
OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast?latitude=41.9779&longitude=-91.6656&daily=temperature_2m_max,temperature_2m_min,precipitation_probability_max&temperature_unit=fahrenheit&timezone=America%2FChicago&forecast_days=7"


def _get_text(url: str, timeout: int = 5) -> str:
    req = Request(url, headers={"User-Agent": "CampusDemandRadar/0.1"})
    with urlopen(req, timeout=timeout) as r:
        return r.read().decode("utf-8", errors="ignore")


def _get_json(url: str, timeout: int = 5) -> dict:
    req = Request(url, headers={"User-Agent": "CampusDemandRadar/0.1"})
    with urlopen(req, timeout=timeout) as r:
        import json
        return json.loads(r.read().decode("utf-8"))


def _compact(html: str) -> str:
    text = re.sub(r"<script[\s\S]*?</script>", " ", html, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def campus_events_signal() -> dict:
    try:
        text = _compact(_get_text(COE_EVENTS_URL))
        keywords = ["graduation", "alumni", "homecoming", "athletics", "family", "orientation", "student", "admission"]
        hits = [m.group(1).strip() for kw in keywords if (m := re.search(r"([A-Z][a-z]{2}\d{2}[^.]{0,140}" + kw + r"[^.]{0,160})", text, re.I))]
        return {"status": "live", "source": COE_EVENTS_URL, "signals": hits[:4] or ["Upcoming campus events detected."], "keywords": [kw for kw in keywords if kw in text.lower()]}
    except Exception as exc:
        return {"status": "fallback", "source": COE_EVENTS_URL, "signals": ["Could not read live calendar; using campus retail season defaults."], "keywords": ["alumni", "student", "athletics"], "error": str(exc)}


def weather_signal() -> dict:
    try:
        data = _get_json(OPEN_METEO_URL)
        daily = data.get("daily", {})
        max_temps = daily.get("temperature_2m_max", [])
        min_temps = daily.get("temperature_2m_min", [])
        precip = daily.get("precipitation_probability_max", [])
        avg_high = round(sum(max_temps) / len(max_temps), 1) if max_temps else None
        cold_days = sum(1 for v in max_temps if v is not None and v < 55)
        rain_days = sum(1 for v in precip if v is not None and v >= 40)
        signals = []
        if cold_days:
            signals.append(f"{cold_days} cool days forecast; feature hoodies and fleece.")
        if rain_days:
            signals.append(f"{rain_days} higher-rain-probability days; feature outerwear.")
        if not signals and avg_high:
            signals.append(f"Average high near {avg_high}F; feature lighter tees, hats, and drinkware.")
        return {"status": "live", "source": "https://open-meteo.com/", "avgHighF": avg_high, "minLowF": min(min_temps) if min_temps else None, "rainDays": rain_days, "signals": signals}
    except Exception as exc:
        return {"status": "fallback", "source": "https://open-meteo.com/", "signals": ["Weather unavailable; defaulting to hoodie, hat, and drinkware opportunities."], "error": str(exc)}


def intent_signal(recent_intents: list) -> dict:
    text = " ".join(e.get("message", "") for e in recent_intents).lower()
    buckets = {"alumni": ["alum", "alumni"], "hoodie": ["hoodie", "fleece", "cold"], "gift": ["gift", "parent", "family"], "drinkware": ["mug", "bottle", "drink"], "pickup": ["pickup", "today", "tomorrow"]}
    counts = {name: sum(text.count(t) for t in terms) for name, terms in buckets.items()}
    ranked = [name for name, count in sorted(counts.items(), key=lambda x: -x[1]) if count]
    return {"status": "live" if recent_intents else "seeded", "source": "in-app shopper intent log", "topIntents": ranked[:5] or ["alumni", "hoodie", "gift"], "sampleCount": len(recent_intents), "signals": [f"{len(recent_intents)} recent chat turns analyzed.", "Top inferred demand: " + ", ".join(ranked[:3] or ["alumni", "hoodie", "gift"])]}


async def run_radar(recent_intents_list: list, focus: str, settings: Settings) -> dict:
    import json
    from urllib.parse import urlencode

    events = campus_events_signal()
    weather = weather_signal()
    intents = intent_signal(recent_intents_list)

    joined = " ".join(events.get("keywords", []) + intents.get("topIntents", []) + weather.get("signals", [])).lower()
    queries = []
    if "hoodie" in joined or "cool" in joined or "cold" in joined:
        queries.append("hoodie")
    if "alumni" in joined or "alum" in joined:
        queries.append("alumni")
    if "gift" in joined or "family" in joined:
        queries.append("gift")
    if "rain" in joined:
        queries.append("hat")
    if "drinkware" in joined or "mug" in joined:
        queries.append("mug")
    queries.extend(["hoodie", "alumni gift", "campus mug"])
    deduped = list(dict.fromkeys(queries))[:3]

    all_products = []
    gaps = []
    for q in deduped:
        try:
            matches = await search_catalog(settings.catalog_service_url, q, None, [])
            if matches:
                all_products.append(matches[0])
            else:
                gaps.append(f"No match for '{q}'.")
        except Exception as exc:
            gaps.append(f"Could not search for '{q}': {exc}")

    actions = []
    if any("hoodie" in q for q in deduped):
        actions.append("Feature hoodies/fleece in the concierge this week and check sizes before event traffic.")
    if "alumni" in " ".join(deduped):
        actions.append("Create an alumni gift bundle: hoodie or tee plus license plate/drinkware.")
    if gaps:
        actions.append("Review missed product gaps and add substitutes or merchandising copy.")
    actions.append("Send daily event-week demand report to store staff with top searches and recommended products.")

    report_id = f"RADAR-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}"

    from ..clients.order import automate_order
    try:
        kestra_result = automate_order.__module__  # side-effect free import check
    except Exception:
        pass

    from urllib.parse import urlencode
    from urllib.request import Request, urlopen
    kestra_url = settings.__dict__.get("kestra_url", "http://localhost:8080") if hasattr(settings, "__dict__") else "http://localhost:8080"
    kestra_namespace = getattr(settings, "kestra_namespace", "demo.commerce") if hasattr(settings, "kestra_namespace") else "demo.commerce"
    kestra_flow_id = "campus-demand-radar"
    data = urlencode({"orderId": report_id, "total": str(len(all_products)), "workflowEvent": "campus.demand_radar"}).encode()
    req = Request(f"{kestra_url}/api/v1/main/executions/{kestra_namespace}/{kestra_flow_id}", data=data, headers={"Content-Type": "application/x-www-form-urlencoded"}, method="POST")
    try:
        with urlopen(req, timeout=8) as r:
            payload = json.loads(r.read().decode())
            kestra = {"status": "triggered", "executionId": payload.get("id"), "url": f"{kestra_url}/ui/executions/{payload.get('id')}" if payload.get("id") else kestra_url}
    except Exception as exc:
        kestra = {"status": "unavailable", "reason": str(exc), "url": kestra_url}

    return {
        "reportId": report_id,
        "focus": focus,
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "signals": {"events": events, "weather": weather, "intent": intents},
        "actions": actions,
        "featuredProducts": all_products[:5],
        "sourceSummary": [
            {"name": "Coe events", "status": events.get("status"), "url": events.get("source")},
            {"name": "Cedar Rapids weather", "status": weather.get("status"), "url": weather.get("source")},
            {"name": "Shopper intent", "status": intents.get("status"), "url": "local session intent log"},
            {"name": "catalog-service", "status": "live" if all_products else "partial", "url": settings.catalog_service_url},
        ],
        "kestraWorkflow": kestra_flow_id,
        "kestra": kestra,
    }


@router.post("/api/radar")
async def radar_endpoint(settings: Settings = Depends(get_settings)) -> dict:
    from ..intent_log import recent_intents
    intents = recent_intents(limit=15)
    return await run_radar(intents, "this week's campus retail opportunity scan", settings)
