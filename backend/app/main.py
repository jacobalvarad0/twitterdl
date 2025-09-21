# Add this to your backend/app/main.py or create it

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.requests import Request
from fastapi.responses import HTMLResponse
from contextlib import asynccontextmanager

from .models import BulkScreenshotRequest, ScreenshotResult
from .screenshot_service import ScreenshotService

# Global screenshot service instance
screenshot_service = ScreenshotService()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    await screenshot_service.initialize()
    yield
    # Shutdown
    await screenshot_service.cleanup()

# Create FastAPI app
app = FastAPI(
    title="Twitter Screenshot API",
    description="Capture beautiful screenshots of tweets",
    version="1.0.0",
    lifespan=lifespan
)

# Mount static files and templates
app.mount("/static", StaticFiles(directory="frontend/static"), name="static")
templates = Jinja2Templates(directory="frontend/templates")

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/health")
async def health_check():
    """Health check endpoint"""
    is_healthy = await screenshot_service.health_check()
    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "service": "twitter-screenshot-api"
    }

@app.post("/api/screenshot/bulk")
async def capture_screenshots_bulk(request: BulkScreenshotRequest):
    """Capture screenshots for multiple URLs"""
    try:
        if not request.urls:
            raise HTTPException(status_code=400, detail="No URLs provided")

        # Use default options if none provided
        options = request.options or ScreenshotOptions()

        # Capture screenshots
        results = await screenshot_service.capture_tweets(request.urls, options)

        return {"results": results}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)