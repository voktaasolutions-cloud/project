import uuid
import logging
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, delete, desc
from sqlalchemy.ext.asyncio import AsyncSession

from database.models import ReviewModel
from database.connection import AsyncSessionLocal
from repositories import parse_datetime, format_iso

logger = logging.getLogger("voktaa.repositories.reviews")


class ReviewRepository:
    @staticmethod
    async def create(session: Optional[AsyncSession], data: Dict[str, Any], legacy_mongo_id: Optional[str] = None) -> Dict[str, Any]:
        doc_id = str(uuid.uuid4())
        ts_dt = parse_datetime(data.get("timestamp"))

        review_row = ReviewModel(
            id=doc_id,
            name=data.get("name", ""),
            email=data.get("email", ""),
            phone=data.get("phone", ""),
            role=data.get("role", ""),
            organisation=data.get("organisation", ""),
            program=data.get("program", ""),
            rating=max(1, min(5, int(data.get("rating") or 5))),
            review=data.get("review", ""),
            status=data.get("status", "approved"),
            timestamp=ts_dt,
            ip=data.get("ip", ""),
            legacy_mongo_id=legacy_mongo_id or None,
        )

        async def _run(s: AsyncSession):
            s.add(review_row)
            await s.flush()
            return {
                "id": doc_id,
                "name": review_row.name,
                "email": review_row.email,
                "phone": review_row.phone,
                "role": review_row.role,
                "organisation": review_row.organisation,
                "program": review_row.program,
                "rating": review_row.rating,
                "review": review_row.review,
                "status": review_row.status,
                "timestamp": format_iso(ts_dt),
                "ip": review_row.ip,
            }

        if session:
            return await _run(session)
        async with AsyncSessionLocal() as s:
            res = await _run(s)
            await s.commit()
            return res

    @staticmethod
    async def list_public(session: Optional[AsyncSession], limit: int = 100) -> List[Dict[str, Any]]:
        async def _run(s: AsyncSession):
            stmt = (
                select(ReviewModel)
                .where(ReviewModel.status == "approved")
                .order_by(desc(ReviewModel.timestamp))
                .limit(limit)
            )
            res = await s.execute(stmt)
            rows = res.scalars().all()
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "role": r.role,
                    "organisation": r.organisation,
                    "program": r.program,
                    "rating": r.rating,
                    "review": r.review,
                    "status": r.status,
                    "timestamp": format_iso(r.timestamp) if hasattr(r.timestamp, "isoformat") else str(r.timestamp),
                }
                for r in rows
            ]

        if session:
            return await _run(session)
        async with AsyncSessionLocal() as s:
            return await _run(s)

    @staticmethod
    async def list_all(session: Optional[AsyncSession], limit: int = 500) -> List[Dict[str, Any]]:
        async def _run(s: AsyncSession):
            stmt = select(ReviewModel).order_by(desc(ReviewModel.timestamp)).limit(limit)
            res = await s.execute(stmt)
            rows = res.scalars().all()
            return [
                {
                    "id": r.id,
                    "name": r.name,
                    "email": r.email,
                    "phone": r.phone,
                    "role": r.role,
                    "organisation": r.organisation,
                    "program": r.program,
                    "rating": r.rating,
                    "review": r.review,
                    "status": r.status,
                    "timestamp": format_iso(r.timestamp) if hasattr(r.timestamp, "isoformat") else str(r.timestamp),
                    "ip": r.ip,
                }
                for r in rows
            ]

        if session:
            return await _run(session)
        async with AsyncSessionLocal() as s:
            return await _run(s)

    @staticmethod
    async def update_status(session: Optional[AsyncSession], review_id: str, status: str) -> bool:
        async def _run(s: AsyncSession):
            stmt = update(ReviewModel).where(ReviewModel.id == review_id).values(status=status)
            res = await s.execute(stmt)
            return res.rowcount > 0

        if session:
            return await _run(session)
        async with AsyncSessionLocal() as s:
            ok = await _run(s)
            await s.commit()
            return ok

    @staticmethod
    async def delete(session: Optional[AsyncSession], review_id: str) -> bool:
        async def _run(s: AsyncSession):
            stmt = delete(ReviewModel).where(ReviewModel.id == review_id)
            res = await s.execute(stmt)
            if res.rowcount > 0:
                return True

            idx_map = {
                "r1": "Tejasri Penubothu",
                "r2": "Sahithi Srinivas S",
                "r3": "N Venkata Bhargavi",
                "r4": "Anumula Abhinaya",
                "r5": "VOKTAA Student",
                "r6": "Kavya Gowripatnam",
            }
            target_name = idx_map.get(review_id)
            if target_name:
                stmt2 = delete(ReviewModel).where(ReviewModel.name == target_name)
                res2 = await s.execute(stmt2)
                return res2.rowcount > 0

            return False

        if session:
            return await _run(session)
        async with AsyncSessionLocal() as s:
            ok = await _run(s)
            await s.commit()
            return ok

    @staticmethod
    async def deduplicate(session: Optional[AsyncSession]) -> int:
        async def _run(s: AsyncSession):
            stmt = select(ReviewModel).order_by(ReviewModel.timestamp.asc())
            res = await s.execute(stmt)
            rows = res.scalars().all()
            seen = set()
            deleted_count = 0
            for r in rows:
                key = ((r.name or "").strip().lower(), (r.review or "").strip().lower())
                if key in seen:
                    await s.delete(r)
                    deleted_count += 1
                else:
                    seen.add(key)
            return deleted_count

        if session:
            return await _run(session)
        async with AsyncSessionLocal() as s:
            count = await _run(s)
            await s.commit()
            return count
