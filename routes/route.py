from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from models.chicago_crimes import Chicago_Crime
from config.database import collection_name
from schema.schemas import list_serial
from bson import ObjectId, json_util
import json
import redis
from typing import Optional
import pickle
from datetime import timedelta
import asyncio
from redis.connection import BlockingConnectionPool
from fastapi.concurrency import run_in_threadpool

router = APIRouter()

# Configure Redis connection pool
redis_pool = BlockingConnectionPool(
    host='redis-16912.c292.ap-southeast-1-1.ec2.redns.redis-cloud.com',
    port=16912,
    password='zCOaF5iQ1GSnd2z3GbeIAA9iZFPegqIh',
    max_connections=2000,
    timeout=20,
    decode_responses=False,
    retry_on_timeout=True,
    socket_keepalive=True,
    socket_connect_timeout=10,
    health_check_interval=30
)

redis_client = redis.Redis(
    connection_pool=redis_pool,
    socket_timeout=10,
    retry_on_timeout=True
)

# Cache configuration
CACHE_EXPIRATION = timedelta(minutes=30)

# Semaphore to limit concurrent database operations
DB_SEMAPHORE = asyncio.Semaphore(100)

def get_cache_key(skip: int, limit: int) -> str:
    """Generate cache key"""
    return f"chicago_crimes:skip={skip}:limit={limit}"

async def get_crimes_from_cache(cache_key: str) -> Optional[list]:
    """Get data from cache"""
    try:
        cached_data = await run_in_threadpool(redis_client.get, cache_key)
        if cached_data:
            return pickle.loads(cached_data)
    except (redis.RedisError, pickle.PickleError, ConnectionError) as e:
        print(f"Cache retrieval error: {str(e)}")
    return None

async def set_crimes_in_cache(cache_key: str, crimes_data: list) -> None:
    """Set cache data"""
    try:
        # Ensure crimes_data is serializable
        serialized_data = await run_in_threadpool(lambda: pickle.dumps(crimes_data))
        await run_in_threadpool(
            redis_client.setex,
            cache_key,
            int(CACHE_EXPIRATION.total_seconds()),
            serialized_data
        )
    except (redis.RedisError, pickle.PickleError, ConnectionError) as e:
        print(f"Cache storage error: {str(e)}")

async def get_crimes_from_db(skip: int, limit: int) -> list:
    """Get crimes from database"""
    async with DB_SEMAPHORE:
        try:
            # Run database query in thread pool to avoid blocking
            def db_query():
                cursor = collection_name.find({}).skip(skip).limit(limit)
                return list_serial(cursor)
            
            return await run_in_threadpool(db_query)
        except Exception as e:
            print(f"Database query error: {str(e)}")
            raise

@router.get("/chicago-crimes")
async def get_crimes(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, gt=0)
):
    """Get paginated chicago crimes data with caching"""
    try:
        cache_key = get_cache_key(skip, limit)
        
        # Try cache first
        cached_data = await get_crimes_from_cache(cache_key)
        if cached_data:
            return JSONResponse(
                content=cached_data,
                headers={
                    "X-Cache": "HIT",
                    "X-Cache-Source": "Redis-Cloud"
                }
            )

        # Get from database if not in cache
        crimes_data = await get_crimes_from_db(skip, limit)
        
        # Store in cache asynchronously
        asyncio.create_task(set_crimes_in_cache(cache_key, crimes_data))
        
        return JSONResponse(
            content=crimes_data,
            headers={
                "X-Cache": "MISS",
                "X-Cache-Source": "MongoDB"
            }
        )

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        raise HTTPException(
            status_code=503,
            detail="Service temporarily unavailable"
        )

@router.get("/health")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "redis": {"status": "unhealthy"},
        "mongodb": {"status": "unhealthy"},
        "api": {"status": "healthy"}
    }
    
    try:
        # Check Redis connection
        await run_in_threadpool(redis_client.ping)
        redis_info = await run_in_threadpool(redis_client.info)
        health_status["redis"] = {
            "status": "healthy",
            "connected_clients": redis_info.get('connected_clients', 'N/A'),
            "used_memory": redis_info.get('used_memory_human', 'N/A'),
            "operations_per_second": redis_info.get('instantaneous_ops_per_sec', 'N/A')
        }
    except Exception as e:
        health_status["redis"]["error"] = str(e)

    try:
        # Check MongoDB connection
        await get_crimes_from_db(0, 1)
        health_status["mongodb"]["status"] = "healthy"
    except Exception as e:
        health_status["mongodb"]["error"] = str(e)

    return health_status

# Optional: Add cache stats endpoint
@router.get("/cache/stats")
async def get_cache_stats():
    """Get cache statistics"""
    try:
        info = await run_in_threadpool(redis_client.info)
        return {
            "keyspace_hits": info.get('keyspace_hits', 'N/A'),
            "keyspace_misses": info.get('keyspace_misses', 'N/A'),
            "connected_clients": info.get('connected_clients', 'N/A'),
            "used_memory_human": info.get('used_memory_human', 'N/A'),
            "total_connections_received": info.get('total_connections_received', 'N/A'),
            "expired_keys": info.get('expired_keys', 'N/A')
        }
    except redis.RedisError as e:
        raise HTTPException(
            status_code=500,
            detail=f"Failed to get cache stats: {str(e)}"
        )