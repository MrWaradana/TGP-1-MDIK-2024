from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import StreamingResponse, JSONResponse
from models.chicago_crimes import Chicago_Crime
from config.database import collection_name
from schema.schemas import list_serial
from bson import ObjectId, json_util
from typing import AsyncGenerator
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
    host="redis-19266.c252.ap-southeast-1-1.ec2.redns.redis-cloud.com",
    port=19266,
    password="YJ76HbEgRPtNjZjHrsbNrIJTygUIQMW0",
    max_connections=10000,
    timeout=20,
    decode_responses=False,
    retry_on_timeout=True,
    socket_keepalive=True,
    socket_connect_timeout=10,
    health_check_interval=30,
)

redis_client = redis.Redis(
    connection_pool=redis_pool, socket_timeout=10, retry_on_timeout=True
)

# Cache configuration
CACHE_EXPIRATION = timedelta(minutes=30)

# Semaphore to limit concurrent database operations
DB_SEMAPHORE = asyncio.Semaphore(100)


async def stream_crimes_generator(
    skip: int = 0, limit: int = 1000
) -> AsyncGenerator[str, None]:
    """
    Asynchronous generator for streaming crime records
    """
    try:
        # Get cursor for the query
        cursor = collection_name.find({}).skip(skip).limit(limit)

        # Stream opening bracket
        yield "["

        first = True
        count = 0

        async for crime in async_cursor_iterator(cursor):
            if not first:
                yield ","
            else:
                first = False

            # Convert the document to JSON and yield
            yield json.dumps(crime, default=json_util.default)

            count += 1
            if limit and count >= limit:
                break

        # Stream closing bracket
        yield "]"

    except Exception as e:
        print(f"Streaming error: {str(e)}")
        yield json.dumps({"error": "Streaming error occurred"})


async def async_cursor_iterator(cursor):
    """
    Convert MongoDB cursor to async iterator
    """
    while True:
        try:
            # Get next document in thread pool
            doc = await run_in_threadpool(next, cursor, None)
            if doc is None:
                break
            yield doc
        except StopIteration:
            break
        except Exception as e:
            print(f"Cursor iteration error: {str(e)}")
            break


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
            serialized_data,
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
async def get_crimes(skip: int = Query(0, ge=0), limit: int = Query(1000, gt=0)):
    """Get paginated chicago crimes data with caching"""
    try:
        cache_key = get_cache_key(skip, limit)

        # Try cache first
        cached_data = await get_crimes_from_cache(cache_key)
        if cached_data:
            return JSONResponse(
                content=cached_data,
                headers={"X-Cache": "HIT", "X-Cache-Source": "Redis-Cloud"},
            )

        # Get from database if not in cache
        crimes_data = await get_crimes_from_db(skip, limit)

        # Store in cache asynchronously
        asyncio.create_task(set_crimes_in_cache(cache_key, crimes_data))

        return JSONResponse(
            content=crimes_data,
            headers={"X-Cache": "MISS", "X-Cache-Source": "MongoDB"},
        )

    except Exception as e:
        print(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")


@router.get("/chicago-crimes/stream")
async def stream_crimes(skip: int = Query(0, ge=0), limit: int = Query(1000, gt=0)):
    """
    Stream chicago crimes data with pagination
    """
    try:
        return StreamingResponse(
            stream_crimes_generator(skip, limit),
            media_type="application/json",
            headers={
                "X-Stream": "True",
                "X-Pagination-Skip": str(skip),
                "X-Pagination-Limit": str(limit),
            },
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Streaming error: {str(e)}")


# Optional: Add batch size parameter for more control
@router.get("/chicago-crimes/stream/batch")
async def stream_crimes_batch(
    skip: int = Query(0, ge=0),
    limit: int = Query(1000, gt=0),
    batch_size: int = Query(100, ge=1, le=1000),
):
    """
    Stream chicago crimes data with custom batch size
    """

    async def batch_generator() -> AsyncGenerator[str, None]:
        try:
            cursor = collection_name.find({}).skip(skip).limit(limit)

            yield "["
            first_batch = True

            while True:
                batch = []
                batch_count = 0

                while batch_count < batch_size:
                    try:
                        doc = await run_in_threadpool(next, cursor, None)
                        if doc is None:
                            break
                        batch.append(doc)
                        batch_count += 1
                    except StopIteration:
                        break

                if not batch:
                    break

                if not first_batch:
                    yield ","
                else:
                    first_batch = False

                yield json.dumps(batch, default=json_util.default)[
                    1:-1
                ]  # Remove batch brackets

            yield "]"

        except Exception as e:
            print(f"Batch streaming error: {str(e)}")
            yield json.dumps({"error": "Batch streaming error occurred"})

    return StreamingResponse(
        batch_generator(),
        media_type="application/json",
        headers={"X-Stream": "True", "X-Batch-Size": str(batch_size)},
    )


# Health check endpoint for streaming
@router.get("/stream/health")
async def check_stream_health():
    """
    Check streaming functionality health
    """
    try:
        # Test with small sample
        cursor = collection_name.find({}).limit(1)
        doc = await run_in_threadpool(next, cursor, None)

        return {
            "status": "healthy",
            "streaming": "available",
            "sample_available": bool(doc),
        }
    except Exception as e:
        return {"status": "unhealthy", "error": str(e)}


# @router.get("/chicago-crimes/stream")
# async def stream_crimes(skip: int = Query(0, ge=0), limit: int = Query(1000, gt=0)):
#     return StreamingResponse(
#         stream_crimes_generator(skip, limit), media_type="application/json"
#     )


@router.get("/health")
async def health_check():
    """Health check endpoint"""
    health_status = {
        "redis": {"status": "unhealthy"},
        "mongodb": {"status": "unhealthy"},
        "api": {"status": "healthy"},
    }

    try:
        # Check Redis connection
        await run_in_threadpool(redis_client.ping)
        redis_info = await run_in_threadpool(redis_client.info)
        health_status["redis"] = {
            "status": "healthy",
            "connected_clients": redis_info.get("connected_clients", "N/A"),
            "used_memory": redis_info.get("used_memory_human", "N/A"),
            "operations_per_second": redis_info.get("instantaneous_ops_per_sec", "N/A"),
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
            "keyspace_hits": info.get("keyspace_hits", "N/A"),
            "keyspace_misses": info.get("keyspace_misses", "N/A"),
            "connected_clients": info.get("connected_clients", "N/A"),
            "used_memory_human": info.get("used_memory_human", "N/A"),
            "total_connections_received": info.get("total_connections_received", "N/A"),
            "expired_keys": info.get("expired_keys", "N/A"),
        }
    except redis.RedisError as e:
        raise HTTPException(
            status_code=500, detail=f"Failed to get cache stats: {str(e)}"
        )


# Add cache cleanup endpoint
@router.post("/cache/cleanup")
async def cleanup_cache():
    """Remove old cache entries"""
    try:
        redis_client.flushdb()
        return {"message": "Cache cleared successfully"}
    except redis.RedisError as e:
        raise HTTPException(status_code=500, detail=str(e))
