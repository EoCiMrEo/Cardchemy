import asyncio
import sys
import os

# Add parent directory to path so we can import app
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlalchemy import text
from app.database import engine

async def add_column():
    print("Attempting to add 'options' column to 'flashcards' table...")
    async with engine.begin() as conn:
        try:
            await conn.execute(text("ALTER TABLE flashcards ADD COLUMN options JSON;"))
            print("✅ Column 'options' added successfully.")
        except Exception as e:
            print(f"⚠️  Could not add column (it might already exist): {e}")

if __name__ == "__main__":
    asyncio.run(add_column())
