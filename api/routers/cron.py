"""
Cron Job Endpoints for Scheduled Polling
Use with cloud schedulers like Vercel Cron, AWS EventBridge, Google Cloud Scheduler.
"""

from fastapi import APIRouter, HTTPException, Header
from typing import Optional
from datetime import datetime
import logging
import os

try:
    from ..services.polling_service import create_polling_service
    from ..services.draw_results_manager import create_draw_results_manager
except ImportError:
    from services.polling_service import create_polling_service
    from services.draw_results_manager import create_draw_results_manager

router = APIRouter(prefix="/api/cron", tags=["cron"])
logger = logging.getLogger(__name__)

# Security: Cron secret for authentication
CRON_SECRET = os.getenv("CRON_SECRET", "your-secret-key-here")


def verify_cron_auth(authorization: Optional[str] = Header(None)):
    """
    Verify cron job is authorized.
    
    For Vercel Cron, check the Authorization header.
    For other platforms, implement your own authentication.
    """
    if not authorization:
        raise HTTPException(
            status_code=401,
            detail="Unauthorized: Missing authorization header"
        )
    
    if authorization != f"Bearer {CRON_SECRET}":
        raise HTTPException(
            status_code=403,
            detail="Forbidden: Invalid cron secret"
        )


@router.get("/check-results")
@router.post("/check-results")
async def check_results_cron(authorization: Optional[str] = Header(None)):
    """
    Scheduled cron endpoint to check for new draw results and evaluate pending tickets.
    
    Schedule suggestions:
    - Vercel Cron: "45 18 * * WED,SAT" (6:45 PM on Wed & Sat)
    - AWS EventBridge: cron(45 18 ? * WED,SAT *)
    - Google Cloud Scheduler: 45 18 * * 3,6
    
    Security:
    - Requires Authorization header: "Bearer {CRON_SECRET}"
    - Set CRON_SECRET environment variable
    
    Headers:
        Authorization: Bearer <your-cron-secret>
    
    Returns:
        Summary of polling results
    """
    # Verify authentication
    verify_cron_auth(authorization)
    
    logger.info("Cron job triggered: checking draw results")
    
    try:
        # Step 1: Fetch and store latest results for both game types
        draw_manager = create_draw_results_manager()
        
        results_fetched = {
            "4D": None,
            "TOTO": None,
        }
        
        for game_type in ["4D", "TOTO"]:
            try:
                result = draw_manager.fetch_and_store_latest_results(game_type)
                results_fetched[game_type] = result
                logger.info(f"{game_type} results fetch: {result.get('status')}")
            except Exception as e:
                logger.error(f"Error fetching {game_type} results: {str(e)}")
                results_fetched[game_type] = {
                    "status": "error",
                    "message": str(e),
                }
        
        # Step 2: Poll and evaluate all pending tickets
        polling_service = create_polling_service()
        polling_result = polling_service.poll_all_pending_tickets()
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "results_fetched": results_fetched,
            "polling_summary": polling_result.get("summary", {}),
        }
    
    except Exception as e:
        logger.error(f"Cron job error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-4d")
@router.post("/check-4d")
async def check_4d_results_cron(authorization: Optional[str] = Header(None)):
    """
    Cron endpoint specifically for 4D draws.
    
    Schedule: Wed & Sat at 6:45 PM SGT
    - Vercel: "45 18 * * WED,SAT"
    
    Headers:
        Authorization: Bearer <your-cron-secret>
    """
    verify_cron_auth(authorization)
    
    logger.info("Cron job triggered: checking 4D results")
    
    try:
        draw_manager = create_draw_results_manager()
        polling_service = create_polling_service()
        
        # Fetch and store latest 4D results
        fetch_result = draw_manager.fetch_and_store_latest_results("4D")
        
        # If new results available, poll pending tickets
        polling_result = None
        if fetch_result.get("status") in ["success", "already_exists"]:
            draw_date = fetch_result.get("draw_date")
            if draw_date:
                polling_result = polling_service.process_pending_tickets_for_draw(
                    "4D",
                    draw_date,
                )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "game_type": "4D",
            "fetch_result": fetch_result,
            "polling_result": polling_result,
        }
    
    except Exception as e:
        logger.error(f"4D cron job error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/check-toto")
@router.post("/check-toto")
async def check_toto_results_cron(authorization: Optional[str] = Header(None)):
    """
    Cron endpoint specifically for TOTO draws.
    
    Schedule: Mon & Thu at 6:45 PM SGT (adjust based on actual draw days)
    - Vercel: "45 18 * * MON,THU"
    
    Headers:
        Authorization: Bearer <your-cron-secret>
    """
    verify_cron_auth(authorization)
    
    logger.info("Cron job triggered: checking TOTO results")
    
    try:
        draw_manager = create_draw_results_manager()
        polling_service = create_polling_service()
        
        # Fetch and store latest TOTO results
        fetch_result = draw_manager.fetch_and_store_latest_results("TOTO")
        
        # If new results available, poll pending tickets
        polling_result = None
        if fetch_result.get("status") in ["success", "already_exists"]:
            draw_date = fetch_result.get("draw_date")
            if draw_date:
                polling_result = polling_service.process_pending_tickets_for_draw(
                    "TOTO",
                    draw_date,
                )
        
        return {
            "status": "completed",
            "timestamp": datetime.utcnow().isoformat(),
            "game_type": "TOTO",
            "fetch_result": fetch_result,
            "polling_result": polling_result,
        }
    
    except Exception as e:
        logger.error(f"TOTO cron job error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def cron_health_check():
    """
    Health check endpoint for cron monitoring.
    No authentication required.
    """
    return {
        "status": "healthy",
        "service": "lottery-cron",
        "timestamp": datetime.utcnow().isoformat(),
    }

