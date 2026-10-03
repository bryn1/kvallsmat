"""app.models.shopping — per-user RELATIONAL shopping data (MC 10037 P1-b/P2-a/P2-b).

Three tables on the SHARED ``database.Base`` (boot() creates them atomically;
registered by ``app.routers.shopping`` importing this module at module scope —
the FIX-2 rule is "registered BEFORE create_all", and app.main imports its
routers before the lifespan boot runs):

  * ``shopping_item``   — week-scoped list rows, UNIQUE(user_id, week_key, item)
    (matapp weekly_shopping's contract, per-user instead of the legacy global).
  * ``shopping_memory`` — purchase-frequency memory per user (matapp
    shopping_memory + record_purchase; the item key is the normalized name).
  * ``staple``          — restock-interval staples per user (matapp staples).

The matapp AES-GCM *blob* scheme is deliberately NOT ported (PORT-PLAN
correction: algorithms yes, blobs/legacy global tables never).
"""
from __future__ import annotations

import json
from datetime import date, timedelta

from sqlalchemy import (Column, Float, ForeignKey, Integer, String, Text,
                        UniqueConstraint)
from sqlalchemy.orm import Session

from database import Base  # shared Base (FIX-2)

SOURCE_PLAN = "plan"
SOURCE_MEMORY = "memory"
SOURCE_STAPLE = "staple"
SOURCE_MANUAL = "manual"
SOURCES = (SOURCE_PLAN, SOURCE_MEMORY, SOURCE_STAPLE, SOURCE_MANUAL)


class ShoppingItem(Base):
    __tablename__ = "shopping_item"
    __table_args__ = (
        UniqueConstraint("user_id", "week_key", "item",
                         name="uq_shopping_user_week_item"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"),
                     nullable=False)
    week_key = Column(String, nullable=False)          # ISO "YYYY-Www"
    item = Column(String, nullable=False)              # normalized key
    quantity = Column(String, default="")
    category = Column(String, default="övrigt")
    checked = Column(Integer, default=0, nullable=False)        # 0/1
    added_manually = Column(Integer, default=0, nullable=False)  # 0/1
    source = Column(String, default=SOURCE_MANUAL, nullable=False)

    def __repr__(self):
        return f"<ShoppingItem {self.user_id}/{self.week_key}/{self.item}>"


class ShoppingMemory(Base):
    __tablename__ = "shopping_memory"
    __table_args__ = (
        UniqueConstraint("user_id", "item", name="uq_memory_user_item"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"),
                     nullable=False)
    item = Column(String, nullable=False)              # normalized key
    last_bought = Column(String)                       # ISO date
    times_bought = Column(Integer, default=0, nullable=False)
    avg_interval_days = Column(Float)                  # None until 2+ gaps
    bought_dates = Column(Text, default="[]")          # JSON list, last 20

    def __repr__(self):
        return f"<ShoppingMemory {self.user_id}/{self.item} x{self.times_bought}>"


class Staple(Base):
    __tablename__ = "staple"
    __table_args__ = (
        UniqueConstraint("user_id", "item", name="uq_staple_user_item"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("users.user_id", ondelete="CASCADE"),
                     nullable=False)
    item = Column(String, nullable=False)              # normalized key
    interval_days = Column(Integer, nullable=False)
    last_bought = Column(String)                       # ISO date or None

    def __repr__(self):
        return f"<Staple {self.user_id}/{self.item} {self.interval_days}d>"


# ─── purchase memory (matapp db.record_purchase, ported 1:1) ─────────────────


def record_purchase(session: Session, user_id: int, item: str,
                    today: str | None = None) -> ShoppingMemory:
    """Record one purchase; keep last 20 dates, recompute the avg gap (>0)."""
    today = today or date.today().isoformat()
    row = (session.query(ShoppingMemory)
           .filter_by(user_id=user_id, item=item).first())
    dates = json.loads(row.bought_dates) if row and row.bought_dates else []
    dates.append(today)
    dates = sorted(set(dates))[-20:]

    gaps = [(date.fromisoformat(dates[i]) - date.fromisoformat(dates[i - 1])).days
            for i in range(1, len(dates))]
    gaps = [g for g in gaps if g > 0]
    avg = (sum(gaps) / len(gaps)) if gaps else None

    if row is None:
        row = ShoppingMemory(user_id=user_id, item=item)
        session.add(row)
    row.last_bought = today
    row.times_bought = (row.times_bought or 0) + 1
    row.avg_interval_days = avg
    row.bought_dates = json.dumps(dates)
    session.commit()
    return row


# ─── due logic (matapp GT-6q4 get_due_habitual_items, ported) ────────────────


def due_memory_items(session: Session, user_id: int,
                     today: date | None = None) -> list[ShoppingMemory]:
    """Habitual items: times_bought>=3 and now-last_bought >= avg_interval."""
    today = today or date.today()
    out = []
    rows = (session.query(ShoppingMemory)
            .filter(ShoppingMemory.user_id == user_id)
            .filter(ShoppingMemory.times_bought >= 3)
            .filter(ShoppingMemory.avg_interval_days.isnot(None))
            .filter(ShoppingMemory.last_bought.isnot(None))
            .all())
    for row in rows:
        try:
            last = date.fromisoformat(row.last_bought)
        except (TypeError, ValueError):
            continue
        if (today - last).days >= row.avg_interval_days:
            out.append(row)
    return out


def due_staples(session: Session, user_id: int,
                today: date | None = None) -> list[Staple]:
    """Staples never bought, or last_bought older than the interval."""
    today = today or date.today()
    out = []
    for row in session.query(Staple).filter(Staple.user_id == user_id).all():
        if not row.last_bought:
            out.append(row)
            continue
        try:
            last = date.fromisoformat(row.last_bought)
        except (TypeError, ValueError):
            out.append(row)   # corrupt date: treat as due (matapp parity)
            continue
        if (today - last).days >= row.interval_days:
            out.append(row)
    return out


def staple_buy_reset(session: Session, user_id: int, item: str,
                     today: str | None = None) -> bool:
    """matapp /api/staples/bought: checking a staple row resets its clock."""
    staple = (session.query(Staple)
              .filter_by(user_id=user_id, item=item).first())
    if staple is None:
        return False
    staple.last_bought = today or date.today().isoformat()
    session.commit()
    return True
