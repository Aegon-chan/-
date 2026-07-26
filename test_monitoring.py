import asyncio, sys
sys.stdout.reconfigure(encoding='utf-8')
from backend.db.monitoring_session import AsyncSessionLocal
from backend.analysis.monitoring_service import get_latest, get_summary

async def test():
    async with AsyncSessionLocal() as db:
        for dtype in ['rainfall', 'groundwater', 'gnss']:
            latest = await get_latest(db, dtype)
            recs = latest.get('records', [])
            print(f"{dtype} latest: {len(recs)} records")
            if recs:
                print(f"  first: {recs[0]}")
        s = await get_summary(db, 'rainfall')
        print(f"rainfall summary: {s.get('total_records')} records, {s.get('station_count')} stations")

asyncio.run(test())