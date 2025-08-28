"""Main FastAPI application for the trading system."""

import time
from fastapi import FastAPI, Request, HTTPException, status, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import redis.asyncio as redis
from src.config import settings
from src.utils.logger import setup_logging, logger
from src.api import routers
from src.api.websocket import ConnectionManager, WebSocketHandler
from src.auth import get_auth_service, AuthenticationError
from src.data.database import db_service
from src.services.data_service import DataService
from src.services.strategy_service import StrategyService
from src.services.trading_service import TradingService
from src.api.portfolio_integration import get_portfolio_integration

# Setup logging
setup_logging()

# Service instances
data_service = DataService()
strategy_service = StrategyService()
trading_service = TradingService()
portfolio_integration = get_portfolio_integration()

# Redis client for WebSocket
redis_client = redis.Redis(
    host=settings.redis.host,
    port=settings.redis.port,
    db=settings.redis.db,
    password=settings.redis.password if settings.redis.password else None,
    decode_responses=True
)

# WebSocket manager
ws_manager = ConnectionManager()
websocket_handler = WebSocketHandler(ws_manager, redis_client)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator:
    """Application lifespan manager."""
    # Startup
    logger.info("Starting trading system API...")
    
    try:
        # Initialize database
        db_service.initialize()
        logger.info("Database initialized")
        
        # Initialize auth service
        auth_service = get_auth_service()
        await auth_service.initialize()
        logger.info("Auth service initialized")
        
        # Initialize other services
        await data_service.initialize()
        await strategy_service.initialize()
        await trading_service.initialize()
        
        # Initialize portfolio integration
        await portfolio_integration.initialize()
        await portfolio_integration.start_realtime_updates()
        logger.info("All services initialized")
        
        # WebSocket manager doesn't need initialization
        logger.info("WebSocket manager ready")
        
    except Exception as e:
        logger.error(f"Failed to initialize services: {e}")
        raise
    
    yield
    
    # Shutdown
    logger.info("Shutting down trading system API...")
    
    try:
        # Stop portfolio integration
        await portfolio_integration.stop_realtime_updates()
        
        # Cleanup services
        if auth_service.is_initialized():
            await auth_service.shutdown()
        
        # WebSocket manager cleanup (if needed)
        # ws_manager doesn't have a shutdown method
        
        # Close database connections
        db_service.close()
        
        logger.info("Cleanup completed")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")


# Create FastAPI app
app = FastAPI(
    title="Personal Trading System",
    description="Automated stock trading system with Schwab API integration",
    version="0.1.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://localhost:3000",
        "http://127.0.0.1:3000",
        "https://127.0.0.1:3000"
    ],  # Frontend URLs (both HTTP and HTTPS)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Request logging middleware
@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Log all requests with timing."""
    start_time = time.time()
    
    # Log request
    logger.info(f"Request: {request.method} {request.url.path}")
    
    # Process request
    response = await call_next(request)
    
    # Calculate processing time
    process_time = time.time() - start_time
    
    # Add custom headers
    response.headers["X-Process-Time"] = str(process_time)
    response.headers["X-API-Version"] = "0.1.0"
    
    # Log response
    logger.info(f"Response: {response.status_code} - {process_time:.3f}s")
    
    return response


# Exception handlers
@app.exception_handler(AuthenticationError)
async def authentication_exception_handler(request: Request, exc: AuthenticationError):
    """Handle authentication errors."""
    logger.error(f"Authentication error: {exc}")
    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "detail": str(exc),
            "type": "authentication_error"
        },
        headers={"WWW-Authenticate": "Bearer"}
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """Handle HTTP exceptions."""
    logger.error(f"HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "type": "http_error"
        }
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Handle validation errors."""
    logger.error(f"Validation error: {exc.errors()}")
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": exc.errors(),
            "type": "validation_error",
            "body": exc.body
        }
    )


@app.exception_handler(StarletteHTTPException)
async def starlette_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle Starlette HTTP exceptions."""
    logger.error(f"Starlette HTTP error {exc.status_code}: {exc.detail}")
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "detail": exc.detail,
            "type": "http_error"
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """Handle all unhandled exceptions."""
    logger.exception("Unhandled exception occurred")
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "detail": "Internal server error",
            "type": "internal_error"
        }
    )


# Health check endpoints
@app.get("/health")
@app.get("/api/health")
async def health_check():
    """Basic health check endpoint."""
    return {
        "status": "healthy",
        "version": "0.1.0",
        "service": "trading-system-api"
    }


@app.get("/health/detailed")
async def detailed_health_check():
    """Detailed health check with service status."""
    health_status = {
        "status": "healthy",
        "version": "0.1.0",
        "services": {
            "database": "unknown",
            "auth": "unknown",
            "data_service": "unknown",
            "strategy_service": "unknown",
            "trading_service": "unknown",
            "websocket": "unknown",
            "streaming": "unknown"
        },
        "timestamp": time.time()
    }
    
    # Check database
    try:
        with db_service.get_session() as session:
            session.execute("SELECT 1")
        health_status["services"]["database"] = "healthy"
    except Exception as e:
        health_status["services"]["database"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check auth service
    try:
        auth_service = get_auth_service()
        if auth_service.is_initialized():
            health_status["services"]["auth"] = "healthy"
        else:
            health_status["services"]["auth"] = "not_initialized"
    except Exception as e:
        health_status["services"]["auth"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check other services
    health_status["services"]["data_service"] = "healthy" if data_service._initialized else "not_initialized"
    health_status["services"]["strategy_service"] = "healthy" if strategy_service._initialized else "not_initialized"
    health_status["services"]["trading_service"] = "healthy" if trading_service._initialized else "not_initialized"
    
    # Check WebSocket status
    try:
        if ws_manager.redis_client:
            await ws_manager.redis_client.ping()
            health_status["services"]["websocket"] = "healthy"
        else:
            health_status["services"]["websocket"] = "not_initialized"
    except Exception as e:
        health_status["services"]["websocket"] = f"unhealthy: {str(e)}"
        health_status["status"] = "degraded"
    
    # Check streaming service status
    try:
        from src.services.streaming_service import get_streaming_service
        service = await get_streaming_service()
        status = await service.get_status()
        health_status["services"]["streaming"] = "active" if status["active"] else "inactive"
    except Exception as e:
        health_status["services"]["streaming"] = "not_available"
    
    return health_status


# Include API routers
app.include_router(routers.auth_router, prefix="/api/auth", tags=["auth"])
app.include_router(routers.account_router, prefix="/api/account", tags=["account"])
app.include_router(routers.data_router, prefix="/api/data", tags=["data"])
app.include_router(routers.strategies_router, prefix="/api/strategies", tags=["strategies"])
app.include_router(routers.backtest_router, prefix="/api/backtest", tags=["backtest"])
app.include_router(routers.trading_router, prefix="/api/trading", tags=["trading"])
app.include_router(routers.portfolio_router, prefix="/api/portfolio", tags=["portfolio"])

# WebSocket endpoint
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """WebSocket endpoint for real-time data streaming."""
    await websocket.accept()
    try:
        # Add to manager after accepting
        ws_manager.active_connections.append(websocket)
        logger.info(f"WebSocket client connected. Total: {len(ws_manager.active_connections)}")
        
        while True:
            # Keep connection alive and handle messages
            data = await websocket.receive_text()
            # Handle incoming messages if needed
            await websocket_handler.handle_message(websocket, data)
            logger.debug(f"Received message: {data}")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
    finally:
        ws_manager.disconnect(websocket)