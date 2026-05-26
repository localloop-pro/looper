"""LOOPER API — Map Pin Routes"""
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from models import MapPin, get_db
from schemas import MapPinRequest, MapPinResponse

router = APIRouter(prefix="/api", tags=["map"])


@router.post("/pins", response_model=MapPinResponse)
def add_pin(req: MapPinRequest, db: Session = Depends(get_db)):
    """Add a pin to the community map."""
    expires_at = None
    if req.expires_in_days:
        expires_at = datetime.now(timezone.utc) + timedelta(days=req.expires_in_days)

    pin = MapPin(
        user_id=req.user_id,
        pin_type=req.pin_type,
        title=req.title,
        description=req.description,
        lat=req.lat,
        lng=req.lng,
        category=req.category,
        expires_at=expires_at,
    )
    db.add(pin)
    db.commit()
    db.refresh(pin)

    return MapPinResponse(
        pin_id=pin.id,
        title=pin.title,
        pin_type=pin.pin_type,
        lat=pin.lat,
        lng=pin.lng,
        created_at=pin.created_at,
    )


@router.get("/pins")
def get_pins(
    lat: float | None = Query(None),
    lng: float | None = Query(None),
    radius_km: float = Query(10.0),
    pin_type: str | None = Query(None),
    db: Session = Depends(get_db),
):
    """Get map pins in an area. Filters by type if specified."""
    query = db.query(MapPin).filter(MapPin.is_active == True)

    # Filter expired pins
    query = query.filter(
        (MapPin.expires_at == None) | (MapPin.expires_at > datetime.now(timezone.utc))
    )

    if pin_type:
        query = query.filter(MapPin.pin_type == pin_type)

    pins = query.all()

    # Filter by distance if coordinates provided
    from routes.search import haversine_km

    results = []
    for pin in pins:
        distance = None
        if lat is not None and lng is not None:
            distance = haversine_km(lat, lng, pin.lat, pin.lng)
            if distance > radius_km:
                continue

        results.append({
            "id": pin.id,
            "pin_type": pin.pin_type,
            "title": pin.title,
            "description": pin.description,
            "lat": pin.lat,
            "lng": pin.lng,
            "category": pin.category,
            "distance_km": round(distance, 1) if distance else None,
            "created_at": pin.created_at.isoformat(),
        })

    # Sort: nearest first
    results.sort(key=lambda p: p["distance_km"] or 999)

    return {"count": len(results), "pins": results}


@router.get("/tourist-info")
def tourist_info(
    lat: float = Query(...),
    lng: float = Query(...),
    db: Session = Depends(get_db),
):
    """Get tourist-specific information: attractions, transport, emergency info."""
    # Get nearby tourist attractions (pins + businesses)
    from routes.search import haversine_km

    attractions = []
    for pin in db.query(MapPin).filter(
        MapPin.pin_type == "tourist_attraction",
        MapPin.is_active == True
    ).all():
        distance = haversine_km(lat, lng, pin.lat, pin.lng)
        if distance < 20:
            attractions.append({
                "name": pin.title,
                "description": pin.description,
                "lat": pin.lat,
                "lng": pin.lng,
                "distance_km": round(distance, 1),
            })

    return {
        "attractions": sorted(attractions, key=lambda a: a["distance_km"]),
        "transport": {
            "nearest_train": "Bondi Junction (approx. 2km from beach)",
            "buses": "333, 380, 381 from Circular Quay to Bondi Beach",
            "opal_card": "Available at convenience stores and stations",
            "rideshare": "Uber, DiDi, Ola available",
        },
        "emergency": {
            "police_ambulance_fire": "000",
            "police_non_urgent": "131 444",
            "nearest_hospital": "Prince of Wales Hospital, Randwick",
            "beach_safety": "Swim between the flags. Lifeguards 7am-5pm (summer)",
        },
        "tips": [
            "Bondi to Coogee coastal walk — 6km, stunning views",
            "Bondi Markets — Sundays 10am-4pm at Bondi Beach Public School",
            "Icebergs Pool — ocean pool at the south end, entry fee applies",
        ],
    }