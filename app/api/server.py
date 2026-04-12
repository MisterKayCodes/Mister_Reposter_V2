"""
API: SERVER
FastAPI application factory.
"""
from fastapi import FastAPI
from app.api.routes import router

def create_app() -> FastAPI:
    app = FastAPI(
        title="Mister Reposter REST API",
        version="2.0.0",
        docs_url="/docs"
    )
    
    app.include_router(router)
    
    return app
