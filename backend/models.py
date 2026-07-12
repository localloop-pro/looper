"""LOOPER Database Models — SQLAlchemy ORM + SQLite"""
import os
import unicodedata
from datetime import datetime, timezone
from sqlalchemy import create_engine, event, Column, Integer, String, Float, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

DATABASE_URL = os.getenv("LOOPER_DB_URL", "sqlite:///data/looper.db")
engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def fold_accents(value: str | None) -> str | None:
    """Lowercase + strip diacritics so 'cafe' matches 'café' (voice
    transcripts and widget users type ASCII; the seed data is accented)."""
    if value is None:
        return None
    return "".join(
        c for c in unicodedata.normalize("NFD", value) if not unicodedata.combining(c)
    ).lower()


if "sqlite" in DATABASE_URL:
    @event.listens_for(engine, "connect")
    def _register_sqlite_functions(dbapi_conn, _record):
        dbapi_conn.create_function("fold_accents", 1, fold_accents, deterministic=True)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, autoincrement=True)
    first_name = Column(String(100), nullable=False)
    mobile_number = Column(String(20), nullable=False, unique=True)
    join_code = Column(String(6), unique=True, index=True)
    user_type = Column(String(20), default="local")  # local, tourist, business
    interest_category = Column(String(100))  # what brought them here
    preferred_language = Column(String(10), default="en")
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    reviews = relationship("Review", back_populates="user")
    pins = relationship("MapPin", back_populates="user")


class Business(Base):
    __tablename__ = "businesses"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(200), nullable=False)
    category = Column(String(100), nullable=False, index=True)  # café, doctor, vet, plumber, etc.
    subcategory = Column(String(100))
    address = Column(String(500))
    suburb = Column(String(100), index=True)
    lat = Column(Float)
    lng = Column(Float)
    phone = Column(String(20))
    website = Column(String(500))
    hybrid_card_id = Column(String(100))  # link to Hybrid Card profile
    description = Column(Text)
    is_verified = Column(Boolean, default=False)
    is_active = Column(Boolean, default=True)  # card.removed => False; never delete
    bridge_updated_at = Column(DateTime)  # sender's updated_at high-water mark (stale-event gate)
    source = Column(String(50), default="manual")  # manual, facebook, hybrid_card
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    reviews = relationship("Review", back_populates="business")


class Review(Base):
    __tablename__ = "reviews"

    id = Column(Integer, primary_key=True, autoincrement=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    rating = Column(Integer, nullable=False)  # 1-5
    review_text = Column(Text)
    verified_visit = Column(Boolean, default=False)  # confirmed they actually visited
    source = Column(String(50), default="direct")  # direct, facebook_import
    facebook_post_id = Column(String(100))  # if imported from FB
    is_public = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    business = relationship("Business", back_populates="reviews")
    user = relationship("User", back_populates="reviews")


class MapPin(Base):
    __tablename__ = "map_pins"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    pin_type = Column(String(30), nullable=False)  # offering, looking_for, event, alert, tourist_attraction
    title = Column(String(200), nullable=False)
    description = Column(Text)
    lat = Column(Float, nullable=False)
    lng = Column(Float, nullable=False)
    category = Column(String(100))
    expires_at = Column(DateTime)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    user = relationship("User", back_populates="pins")


class TrainingLog(Base):
    __tablename__ = "training_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    query_text = Column(Text, nullable=False)
    response_text = Column(Text)
    user_id = Column(Integer, ForeignKey("users.id"))
    session_id = Column(String(100))
    feedback = Column(String(20))  # helpful, not_helpful, neutral
    intent = Column(String(100))  # classified intent
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class BridgeEvent(Base):
    """One row per received BRIDGE-CONTRACT-v1 event — the idempotency ledger.
    The sender retries ALL non-2xx, so the same eventId arrives repeatedly."""
    __tablename__ = "bridge_events"

    id = Column(Integer, primary_key=True, autoincrement=True)
    event_id = Column(String(64), nullable=False, unique=True, index=True)
    event_type = Column(String(40))  # deal.upserted, deal.removed, card.upserted, card.removed
    payload = Column(Text)  # raw JSON as received (public-safe per contract §8)
    status = Column(String(20), default="processed")
    received_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))


class Deal(Base):
    """HybridCard deal mirrored via the bridge. deal.removed deactivates,
    NEVER deletes (BRIDGE-CONTRACT-v1 §2)."""
    __tablename__ = "deals"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deal_id = Column(String(64), nullable=False, unique=True, index=True)
    business_id = Column(Integer, ForeignKey("businesses.id"), nullable=False, index=True)
    title = Column(String(200))
    short_description = Column(String(500))
    category = Column(String(100))
    pin_type = Column(String(30))  # offering, event
    sub_type = Column(String(100))
    discount_size = Column(Float)  # contract type is number — STORAGE ONLY, never a ranking input (§7)
    lat = Column(Float)
    lng = Column(Float)
    hours = Column(String(200))
    public_card_url = Column(String(500))
    active = Column(Boolean, default=True)
    source_updated_at = Column(DateTime)  # sender's updated_at (stale-event gate)
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))


def init_db():
    """Create all tables. Safe to call multiple times."""
    import os
    os.makedirs("data", exist_ok=True)
    Base.metadata.create_all(bind=engine)
    # create_all never ALTERs existing tables — add columns introduced after
    # a DB was first created (additive, idempotent).
    if "sqlite" in DATABASE_URL:
        added_columns = {
            "businesses": {"is_active": "BOOLEAN DEFAULT 1", "bridge_updated_at": "DATETIME"},
            "deals": {"source_updated_at": "DATETIME"},
        }
        with engine.connect() as conn:
            for table, columns in added_columns.items():
                cols = [row[1] for row in conn.exec_driver_sql(f"PRAGMA table_info({table})")]
                if not cols:
                    continue  # table doesn't exist yet; create_all handles it
                for name, ddl in columns.items():
                    if name not in cols:
                        conn.exec_driver_sql(f"ALTER TABLE {table} ADD COLUMN {name} {ddl}")
            conn.commit()


def get_db():
    """Dependency: get DB session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()