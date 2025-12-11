"""Main module for the FastAPI application."""
# Render deployment fix - trigger redeploy

import os
from pathlib import Path
from typing import Dict

from dotenv import load_dotenv
from fastapi import FastAPI, Request, HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from slowapi.errors import RateLimitExceeded
from starlette.middleware.trustedhost import TrustedHostMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from server.routers import index, dynamic
from server.server_config import templates
from server.server_utils import lifespan, limiter, rate_limit_exception_handler

# Load environment variables from .env file
load_dotenv()

# Initialize the FastAPI application with lifespan
app = FastAPI(lifespan=lifespan)
app.state.limiter = limiter

# Register the custom exception handler for rate limits
app.add_exception_handler(RateLimitExceeded, rate_limit_exception_handler)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """
    Handle validation errors (422) with detailed logging for debugging.
    
    This helps diagnose environmental issues like missing form data or incorrect Content-Type headers.
    """
    # Log the error details for debugging
    host = request.headers.get("host", "unknown")
    content_type = request.headers.get("content-type", "unknown")
    method = request.method
    path = request.url.path
    
    error_details = {
        "host": host,
        "content_type": content_type,
        "method": method,
        "path": path,
        "errors": exc.errors(),
    }
    
    print(f"ERROR: 422 Validation Error - Host: {host}, Content-Type: {content_type}, Path: {path}")
    print(f"ERROR: Validation details: {error_details}")
    
    # If it's a form submission, return a helpful error message
    if method == "POST" and "form" in str(exc.errors()).lower():
        return JSONResponse(
            status_code=422,
            content={
                "detail": "Form validation failed. Make sure the request has Content-Type: application/x-www-form-urlencoded or multipart/form-data",
                "host": host,
                "content_type": content_type,
                "errors": exc.errors(),
            }
        )
    
    # Otherwise return standard validation error
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors(), "body": exc.body}
    )


# Mount static files dynamically to serve CSS, JS, and other static assets
static_dir = Path(__file__).parent.parent / "static"
app.mount("/static", StaticFiles(directory=static_dir), name="static")


# Fetch allowed hosts from the environment or use the default values
allowed_hosts = os.getenv("ALLOWED_HOSTS")
if allowed_hosts:
    allowed_hosts = allowed_hosts.split(",")
    # Strip whitespace from each host
    allowed_hosts = [host.strip() for host in allowed_hosts]
else:
    # Define the default allowed hosts for the application
    default_allowed_hosts = [
        "gitdocs.com", "*.gitdocs.com", "localhost", "127.0.0.1",
        "gittodoc.com", "*.gittodoc.com", "www.gittodoc.com",
        "gittodoc.onrender.com", "*.onrender.com"
    ]
    allowed_hosts = default_allowed_hosts

# Log allowed hosts for debugging (only in development)
if os.getenv("DEBUG", "").lower() in ("true", "1"):
    print(f"DEBUG: Allowed hosts: {allowed_hosts}")


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Middleware to log request details for debugging 422 errors."""
    
    async def dispatch(self, request: Request, call_next):
        # Log POST requests that might fail validation
        if request.method == "POST":
            host = request.headers.get("host", "unknown")
            content_type = request.headers.get("content-type", "missing")
            path = request.url.path
            
            # Only log if DEBUG is enabled or if content-type is suspicious
            if os.getenv("DEBUG", "").lower() in ("true", "1") or not content_type.startswith(("application/x-www-form-urlencoded", "multipart/form-data")):
                print(f"DEBUG POST: Host={host}, Content-Type={content_type}, Path={path}")
        
        response = await call_next(request)
        return response


# Add request logging middleware first (runs last in the chain)
app.add_middleware(RequestLoggingMiddleware)

# Add middleware to enforce allowed hosts
# Note: TrustedHostMiddleware can cause 400 errors if Host header doesn't match
# Make sure ALLOWED_HOSTS environment variable includes your actual domain
# If you're behind a proxy, you may need to configure X-Forwarded-Host handling
app.add_middleware(TrustedHostMiddleware, allowed_hosts=allowed_hosts)


@app.get("/health")
async def health_check() -> Dict[str, str]:
    """
    Health check endpoint to verify that the server is running.

    Returns
    -------
    Dict[str, str]
        A JSON object with a "status" key indicating the server's health status.
    """
    return {"status": "healthy"}


@app.head("/")
async def head_root() -> HTMLResponse:
    """
    Respond to HTTP HEAD requests for the root URL.

    Mirrors the headers and status code of the index page.

    Returns
    -------
    HTMLResponse
        An empty HTML response with appropriate headers.
    """
    return HTMLResponse(content=None, headers={"content-type": "text/html; charset=utf-8"})


@app.get("/api/", response_class=HTMLResponse)
@app.get("/api", response_class=HTMLResponse)
async def api_docs(request: Request) -> HTMLResponse:
    """
    Render the API documentation page.

    Parameters
    ----------
    request : Request
        The incoming HTTP request.

    Returns
    -------
    HTMLResponse
        A rendered HTML page displaying API documentation.
    """
    return templates.TemplateResponse("api.jinja", {"request": request})


@app.get("/robots.txt")
async def robots() -> FileResponse:
    """
    Serve the `robots.txt` file to guide search engine crawlers.

    Returns
    -------
    FileResponse
        The `robots.txt` file located in the static directory.
    """
    return FileResponse("static/robots.txt")


# Include routers for modular endpoints - use the imported router objects directly
app.include_router(index)
app.include_router(dynamic)
