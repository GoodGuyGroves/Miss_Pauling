"""Tortoise ORM SQLite database"""
from tortoise import Tortoise, run_async


async def init():
    """Creates the database and schema"""
    print("making db pauling.db")
    await Tortoise.init(
        db_url="sqlite://../pauling.db", modules={"models": ["pauling.db.models"]}
    )
    await Tortoise.generate_schemas()
    print("made db pauling.db")


if __name__ == "__main__":
    run_async(init())
