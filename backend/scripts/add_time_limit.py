import asyncio
import sys
import os

# Add parent directory to path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

async def add_time_limit_column():
    print("Attempting to add 'time_limit' column to 'flashcard_sets' table...")
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE flashcard_sets ADD COLUMN time_limit INTEGER;"))
            print("✅ Column 'time_limit' added successfully.")
        except Exception as e:
            print(f"⚠️  Could not add column (it might already exist): {e}")

if __name__ == "__main__":
    asyncio.run(add_time_limit_column())
