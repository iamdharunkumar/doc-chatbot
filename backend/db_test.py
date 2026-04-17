import asyncio
import logging
from app.core.config import settings
from app.core.database import engine
from app.core.storage import _get_client
from app.core.cache import get_redis
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("HealthCheck")

async def test_all():
    logger.info("Starting System Health Check...")
    
    # Debug: Where is the app looking for .env?
    from pydantic_settings import SettingsConfigDict
    from app.core.config import Settings
    temp_settings = Settings()
    logger.info("🔍 Looking for .env at: %s", temp_settings.model_config.get("env_file"))
    logger.info("🔍 Loaded DATABASE_URL: %s***", settings.DATABASE_URL[:25])
    
    # 1. Test Database (Neon)
    try:
        async with engine.connect() as conn:
            result = await conn.execute(text("SELECT version();"))
            row = result.fetchone()
            logger.info("✅ Database Connected: %s", row[0])
            
            # Check pgvector
            vec_res = await conn.execute(text("SELECT extname FROM pg_extension WHERE extname = 'vector';"))
            if vec_res.fetchone():
                logger.info("✅ PGVector Extension: Active")
            else:
                logger.warn("⚠️ PGVector Extension: Missing (Running 'alembic upgrade head' should fix this)")
    except Exception as e:
        logger.error("❌ Database Failed: %s", e)

    # 2. Test Redis
    try:
        redis = await get_redis()
        await redis.ping()
        logger.info("✅ Redis Connected")
    except Exception as e:
        logger.error("❌ Redis Failed: %s", e)

    # 3. Test MinIO
    try:
        client = _get_client()
        buckets = client.list_buckets()
        logger.info("✅ MinIO Connected (%d buckets found)", len(buckets))
    except Exception as e:
        logger.error("❌ MinIO Failed: %s", e)

    logger.info("Health Check Complete.")

if __name__ == "__main__":
    asyncio.run(test_all())
