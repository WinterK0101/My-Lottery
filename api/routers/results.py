"""
Results API Router
Handles fetching official lottery results and evaluating tickets.
Integrates scraper, prize matching, and Supabase database.
"""

from fastapi import APIRouter, HTTPException, Query, BackgroundTasks
from datetime import datetime, date, timedelta
from typing import Optional
import logging

try:
    from ..services.scraper import create_scraper
    from ..services.prize_matching import (
        evaluate_ticket,
        should_evaluate_ticket,
    )
    from ..services.supabase import get_supabase_client
    from ..services.draw_results_manager import create_draw_results_manager
    from ..services.polling_service import create_polling_service
except ImportError:
    from services.scraper import create_scraper
    from services.prize_matching import (
        evaluate_ticket,
        should_evaluate_ticket,
    )
    from services.supabase import get_supabase_client
    from services.draw_results_manager import create_draw_results_manager
    from services.polling_service import create_polling_service

router = APIRouter(prefix="/api/results", tags=["results"])
logger = logging.getLogger(__name__)


@router.get("/latest/{game_type}")
async def get_latest_results(game_type: str):
    """
    Fetch latest lottery results for a specific game type.
    
    Args:
        game_type: "4D" or "TOTO"
    
    Returns:
        Dict with latest results or error message
    
    Raises:
        HTTPException: Invalid game type or scraper error
    """
    if game_type not in ["4D", "TOTO"]:
        raise HTTPException(status_code=400, detail="game_type must be '4D' or 'TOTO'")

    try:
        scraper = create_scraper()
        results = scraper.get_latest_results(game_type)

        if results.get("status") == "error":
            raise HTTPException(
                status_code=404, detail=results.get("message", "Results not available")
            )

        return results

    except Exception as e:
        logger.error(f"Error fetching latest results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/past/{game_type}")
async def get_past_results(
    game_type: str,
    draw_date: str = Query(..., description="Date in format YYYY-MM-DD"),
):
    """
    Fetch past lottery results for a specific game and date.
    First checks database, then falls back to web scraping if not found.
    
    Args:
        game_type: "4D" or "TOTO"
        draw_date: Date in format YYYY-MM-DD
    
    Returns:
        Dict with past results or error message
    """
    if game_type not in ["4D", "TOTO"]:
        raise HTTPException(status_code=400, detail="game_type must be '4D' or 'TOTO'")

    try:
        # Validate date format
        datetime.strptime(draw_date, "%Y-%m-%d")
    except ValueError:
        raise HTTPException(
            status_code=400, detail="draw_date must be in format YYYY-MM-DD"
        )

    try:
        # Use draw results manager (checks DB first, then scrapes if needed)
        draw_manager = create_draw_results_manager()
        results = draw_manager.get_draw_results(
            game_type=game_type,
            draw_date=draw_date,
            fetch_if_missing=True,
        )

        if results.get("status") == "error":
            raise HTTPException(
                status_code=404, detail=results.get("message", "Results not available")
            )

        return results

    except Exception as e:
        logger.error(f"Error fetching past results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate")
async def evaluate_user_ticket(
    ticket_data: dict,
    background_tasks: BackgroundTasks,
):
    """
    DEPRECATED: Use /process-ticket endpoint instead.
    Legacy endpoint for backward compatibility.
    
    Evaluate a user's ticket against official results.
    
    Request body:
    {
        "ticket_id": "uuid",
        "game_type": "4D" or "TOTO",
        "numbers": [...],
        "expanded_combinations": [...],  # optional, for system bets
        "draw_date": "YYYY-MM-DD"
    }
    
    Returns:
        Dict with evaluation result and updated ticket status
    """
    try:
        ticket_id = ticket_data.get("ticket_id")
        game_type = ticket_data.get("game_type")
        draw_date = ticket_data.get("draw_date")

        if not all([ticket_id, game_type, draw_date]):
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: ticket_id, game_type, draw_date",
            )

        if game_type not in ["4D", "TOTO"]:
            raise HTTPException(status_code=400, detail="Invalid game_type")

        # Check if results should be evaluated
        if not should_evaluate_ticket(draw_date):
            return {
                "status": "pending",
                "message": "Draw date is in the future; evaluation will occur after draw",
                "ticket_id": ticket_id,
            }

        # Fetch official results
        scraper = create_scraper()
        official_results = scraper.get_latest_results(game_type)

        if official_results.get("status") == "error":
            return {
                "status": "pending",
                "message": "Official results not yet available",
                "ticket_id": ticket_id,
            }

        # Evaluate ticket
        evaluation = evaluate_ticket(ticket_data, official_results)

        # Update Supabase with results
        background_tasks.add_task(
            _update_ticket_status,
            ticket_id,
            evaluation,
        )

        return {
            "status": "evaluated",
            "ticket_id": ticket_id,
            "evaluation": evaluation,
            "note": "Ticket status updated in background",
        }

    except Exception as e:
        logger.error(f"Error evaluating ticket: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/process-ticket")
async def process_ticket(
    request: dict,
):
    """
    Process a ticket and send results via push notification.
    The API returns a simple acknowledgment; detailed results are delivered via notification.
    
    Request body:
    {
        "ticket_id": "uuid"
    }
    
    Returns:
        Dict with processing status (notification will be sent separately)
    """
    try:
        ticket_id = request.get("ticket_id")
        
        if not ticket_id:
            raise HTTPException(
                status_code=400,
                detail="Missing required field: ticket_id",
            )

        # Use polling service to handle the workflow
        polling_service = create_polling_service()
        result = polling_service.process_ticket(ticket_id)

        # Map status to HTTP response
        if result.get("status") == "error":
            if "not found" in result.get("message", "").lower():
                raise HTTPException(status_code=404, detail=result.get("message"))
            raise HTTPException(status_code=500, detail=result.get("message"))

        # Return minimal response - full results sent via notification
        status = result.get("status")
        ticket_id = result.get("ticket_id")
        notification_sent = bool(result.get("notification_sent", False))
        
        # Build minimal response based on status
        response = {
            "status": status,
            "ticket_id": ticket_id,
        }
        
        if status == "success":
            response["message"] = (
                "Ticket evaluated successfully. Results sent via notification."
                if notification_sent
                else "Ticket evaluated successfully. Notification is not enabled or delivery failed."
            )
            response["notification_sent"] = notification_sent
        elif status == "already_evaluated":
            response["message"] = "Ticket was already evaluated."
            response["notification_sent"] = False
        elif status == "pending":
            response["message"] = result.get("message", "Draw has not occurred yet. You'll be notified when results are available.")
            response["draw_date"] = result.get("draw_date")
            response["notification_sent"] = False
        elif status == "no_results":
            response["message"] = result.get("message", "Draw results not yet available. You'll be notified when results are released.")
            response["draw_date"] = result.get("draw_date")
            response["notification_sent"] = False
        else:
            response["message"] = result.get("message", "Ticket processed.")
            response["notification_sent"] = False
        
        return response

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error processing ticket: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/poll-draw")
async def poll_draw_results(
    request: dict,
):
    """
    Poll and evaluate all pending tickets for a specific draw.
    Useful for manually triggering evaluation after results are released.
    
    Request body:
    {
        "game_type": "4D" or "TOTO",
        "draw_date": "YYYY-MM-DD"
    }
    
    Returns:
        Dict with batch processing results
    """
    try:
        game_type = request.get("game_type")
        draw_date = request.get("draw_date")

        if not all([game_type, draw_date]):
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: game_type, draw_date",
            )

        if game_type not in ["4D", "TOTO"]:
            raise HTTPException(status_code=400, detail="Invalid game_type")

        # Validate date format
        try:
            datetime.strptime(draw_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="draw_date must be in format YYYY-MM-DD"
            )

        # Use polling service
        polling_service = create_polling_service()
        result = polling_service.process_pending_tickets_for_draw(game_type, draw_date)

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error polling draw results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/poll-all-pending")
async def poll_all_pending_tickets():
    """
    Poll and evaluate all pending tickets across all draws.
    Checks which draws have results available and evaluates corresponding tickets.
    
    This endpoint is useful for:
    - Manual trigger to check all pending tickets
    - Cron job endpoint for scheduled polling
    - Catching up on missed evaluations
    
    Returns:
        Dict with summary of all tickets processed
    """
    try:
        polling_service = create_polling_service()
        result = polling_service.poll_all_pending_tickets()

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error polling all pending tickets: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/store-results")
async def store_draw_results(
    request: dict,
):
    """
    Manually store draw results in the database.
    Useful for populating historical data or correcting errors.
    
    Request body:
    {
        "game_type": "4D" or "TOTO",
        "draw_date": "YYYY-MM-DD",
        "draw_id": "draw_number",
        "results": {
            // For 4D:
            "first_prize": "1234",
            "second_prize": "5678",
            "third_prize": "9012",
            "starter": ["3456", "7890"],
            "consolation": ["1111", "2222"]
            
            // For TOTO:
            "winning_numbers": [1, 2, 3, 4, 5, 6],
            "additional_number": 7
        }
    }
    
    Returns:
        Confirmation of storage
    """
    try:
        game_type = request.get("game_type")
        draw_date = request.get("draw_date")
        draw_id = request.get("draw_id")
        results_data = request.get("results")

        if not all([game_type, draw_date, draw_id, results_data]):
            raise HTTPException(
                status_code=400,
                detail="Missing required fields: game_type, draw_date, draw_id, results",
            )

        if game_type not in ["4D", "TOTO"]:
            raise HTTPException(status_code=400, detail="Invalid game_type")

        # Validate date format
        try:
            datetime.strptime(draw_date, "%Y-%m-%d")
        except ValueError:
            raise HTTPException(
                status_code=400, detail="draw_date must be in format YYYY-MM-DD"
            )

        # Use draw results manager
        draw_manager = create_draw_results_manager()
        result = draw_manager.store_draw_results(
            game_type=game_type,
            draw_date=draw_date,
            draw_id=draw_id,
            results_data=results_data,
        )

        if result.get("status") == "error":
            raise HTTPException(status_code=500, detail=result.get("message"))

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error storing draw results: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/draw-history/{game_type}")
async def get_draw_history(
    game_type: str,
    start_date: Optional[str] = Query(None, description="Start date YYYY-MM-DD"),
    end_date: Optional[str] = Query(None, description="End date YYYY-MM-DD"),
    limit: int = Query(10, ge=1, le=100, description="Number of results to return"),
):
    """
    Get historical draw results for a game type.
    
    Args:
        game_type: "4D" or "TOTO"
        start_date: Optional start date filter
        end_date: Optional end date filter
        limit: Maximum number of results (default 10, max 100)
    
    Returns:
        List of historical draw results
    """
    if game_type not in ["4D", "TOTO"]:
        raise HTTPException(status_code=400, detail="game_type must be '4D' or 'TOTO'")

    try:
        draw_manager = create_draw_results_manager()

        # If date range provided, use it
        if start_date and end_date:
            # Validate dates
            try:
                datetime.strptime(start_date, "%Y-%m-%d")
                datetime.strptime(end_date, "%Y-%m-%d")
            except ValueError:
                raise HTTPException(
                    status_code=400, detail="Dates must be in format YYYY-MM-DD"
                )

            results = draw_manager.get_results_for_date_range(
                game_type=game_type,
                start_date=start_date,
                end_date=end_date,
            )
        else:
            # Get recent results
            supabase = get_supabase_client()
            response = (
                supabase.table("lottery_results")
                .select("*")
                .eq("game_type", game_type)
                .order("draw_date", desc=True)
                .limit(limit)
                .execute()
            )

            if not response.data:
                return []

            # Parse results
            import json
            results = []
            for result in response.data:
                raw_wn = result["winning_numbers"]
                winning_numbers = raw_wn if isinstance(raw_wn, dict) else json.loads(raw_wn)
                results.append({
                    "game_type": result["game_type"],
                    "draw_date": result["draw_date"],
                    "draw_id": result["draw_id"],
                    "results": winning_numbers,
                    "additional_number": result.get("additional_number"),
                })

        return results

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching draw history: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/evaluate-batch")
async def evaluate_batch_tickets(
    tickets: list,
    background_tasks: BackgroundTasks,
):
    """
    Evaluate multiple tickets at once.
    
    Request body:
    [
        {...ticket_data...},
        {...ticket_data...}
    ]
    
    Returns:
        Dict with evaluation results for all tickets
    """
    try:
        scraper = create_scraper()
        results = []
        supabase = get_supabase_client()

        for ticket_data in tickets:
            ticket_id = ticket_data.get("ticket_id")
            game_type = ticket_data.get("game_type")
            draw_date = ticket_data.get("draw_date")

            # Skip if missing required fields
            if not all([ticket_id, game_type, draw_date]):
                results.append(
                    {
                        "ticket_id": ticket_id,
                        "status": "error",
                        "message": "Missing required fields",
                    }
                )
                continue

            # Skip if draw is in future
            if not should_evaluate_ticket(draw_date):
                results.append(
                    {
                        "ticket_id": ticket_id,
                        "status": "pending",
                        "message": "Draw date in future",
                    }
                )
                continue

            # Fetch results (once per game type)
            official_results = scraper.get_latest_results(game_type)

            if official_results.get("status") == "error":
                results.append(
                    {
                        "ticket_id": ticket_id,
                        "status": "pending",
                        "message": "Results not available",
                    }
                )
                continue

            # Evaluate
            evaluation = evaluate_ticket(ticket_data, official_results)

            results.append(
                {
                    "ticket_id": ticket_id,
                    "status": "evaluated",
                    "evaluation": evaluation,
                }
            )

            # Queue for database update
            background_tasks.add_task(
                _update_ticket_status,
                ticket_id,
                evaluation,
            )

        return {
            "total": len(tickets),
            "evaluated": len([r for r in results if r.get("status") == "evaluated"]),
            "pending": len([r for r in results if r.get("status") == "pending"]),
            "errors": len([r for r in results if r.get("status") == "error"]),
            "results": results,
        }

    except Exception as e:
        logger.error(f"Error in batch evaluation: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def _update_ticket_status(ticket_id: str, evaluation: dict):
    """
    Update ticket status in Supabase based on evaluation.
    
    Args:
        ticket_id: The ticket UUID
        evaluation: Evaluation result from evaluate_ticket()
    """
    try:
        supabase = get_supabase_client()

        # Determine status and prize info
        is_winner = evaluation.get("is_winner", False)
        prize_tier = evaluation.get("prize_tier", "No Prize")

        # Build update payload
        update_data = {
            "status": "won" if is_winner else "lost",
            "prize_tier": prize_tier,
            "evaluation_result": evaluation,
            "evaluated_at": datetime.utcnow().isoformat(),
        }

        # Update ticket with backward compatibility for schemas missing optional fields.
        optional_fields = ["evaluated_at", "evaluation_result", "prize_tier"]
        response = None
        while True:
            try:
                response = supabase.table("tickets").update(update_data).eq("id", ticket_id).execute()
                break
            except Exception as update_err:
                err_text = str(update_err)
                removed_field = None
                for field in optional_fields:
                    if field in err_text and field in update_data:
                        removed_field = field
                        update_data.pop(field, None)
                        logger.warning(
                            f"Column '{field}' not found in tickets table; retrying update without it"
                        )
                        break

                if not removed_field:
                    raise

        if response.data:
            logger.info(f"Ticket {ticket_id} status updated to {update_data['status']}")
        else:
            logger.warning(f"Failed to update ticket {ticket_id}")

    except Exception as e:
        logger.error(f"Error updating ticket {ticket_id}: {str(e)}")


@router.post("/setup-polling")
async def setup_polling_config(config: dict):
    """
    Configure polling schedule for automatic result checks.
    
    Request body:
    {
        "enabled": true,
        "schedule_time": "18:45",  # HH:MM format (6:45 PM)
        "check_4d": true,
        "check_toto": true,
        "game_types": ["4D", "TOTO"]
    }
    
    Returns:
        Confirmation of polling setup
    
    Note: This requires integration with a task scheduler like APScheduler
    or a cloud job scheduler (Cloud Tasks, Lambda, etc.)
    """
    try:
        polling_config = {
            "enabled": config.get("enabled", True),
            "schedule_time": config.get("schedule_time", "18:45"),
            "check_4d": config.get("check_4d", True),
            "check_toto": config.get("check_toto", True),
            "game_types": config.get("game_types", ["4D", "TOTO"]),
        }

        # Validate time format
        try:
            datetime.strptime(polling_config["schedule_time"], "%H:%M")
        except ValueError:
            raise HTTPException(status_code=400, detail="schedule_time must be HH:MM format")

        # Here you would save config to database or environment
        logger.info(f"Polling config set: {polling_config}")

        return {
            "status": "configured",
            "config": polling_config,
            "note": "Integrate with APScheduler or cloud job scheduler for actual polling",
        }

    except Exception as e:
        logger.error(f"Error setting up polling: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Polling Function (to be scheduled separately)
# ============================================================================


async def polling_check_results():
    """
    Polling function to be scheduled at 6:45 PM on draw days.
    
    This function should be scheduled using:
    - APScheduler (for local/server deployments)
    - Google Cloud Tasks / AWS Lambda / Vercel Cron (for serverless)
    
    Schedule: Run at 18:45 (6:45 PM) on:
    - Every Saturday for TOTO
    - Every Wednesday & Saturday for 4D (adjust if needed)
    
    Example with APScheduler:
    ```python
    from apscheduler.schedulers.background import BackgroundScheduler
    
    scheduler = BackgroundScheduler()
    scheduler.add_job(
        polling_check_results,
        'cron',
        day_of_week='0,2',  # Saturday, Monday-Wednesday depending on game
        hour=18,
        minute=45,
        id='lottery_polling'
    )
    scheduler.start()
    ```
    
    Example with Vercel Cron:
    In vercel.json:
    ```json
    {
        "crons": [{
            "path": "/api/cron/check-results",
            "schedule": "45 18 * * SAT"
        }]
    }
    ```
    """
    logger.info("Starting polling check for results...")

    try:
        scraper = create_scraper()
        supabase = get_supabase_client()

        # Check both games
        for game_type in ["4D", "TOTO"]:
            logger.info(f"Polling for {game_type} results...")

            # Fetch latest results
            results = scraper.get_latest_results(game_type)

            if results.get("status") == "error":
                logger.warning(f"Could not fetch {game_type} results: {results.get('message')}")
                continue

            # Query all pending tickets for this game type (today's draw)
            today = date.today().isoformat()

            pending_tickets = (
                supabase.table("tickets")
                .select("*")
                .eq("game_type", game_type)
                .eq("draw_date", today)
                .eq("status", "pending")
                .execute()
            )

            if not pending_tickets.data:
                logger.info(f"No pending {game_type} tickets for today")
                continue

            # Evaluate each ticket
            for ticket in pending_tickets.data:
                logger.info(f"Evaluating ticket {ticket['id']}...")

                # Build ticket dict for evaluation
                user_ticket = {
                    "game_type": ticket.get("game_type"),
                    "numbers": ticket.get("selected_numbers", []),
                    "expanded_combinations": ticket.get("expanded_combinations"),
                }

                # Evaluate
                evaluation = evaluate_ticket(user_ticket, results)

                # Update status
                await _update_ticket_status(ticket["id"], evaluation)

        logger.info("Polling check completed successfully")

    except Exception as e:
        logger.error(f"Error in polling check: {str(e)}")


# ============================================================================
# Cron Endpoint for Vercel/Cloud Functions
# ============================================================================


@router.post("/cron/check-results")
async def cron_check_results(x_vercel_cron_secret: Optional[str] = None):
    """
    Cron endpoint for Vercel or similar cloud platforms.
    
    To use with Vercel:
    1. Add to vercel.json:
      {
        "crons": [{
          "path": "/api/results/cron/check-results",
          "schedule": "45 18 * * SAT"
        }]
      }
    
    2. Add CRON_SECRET to environment
    
    3. This endpoint will be called automatically by Vercel at the scheduled time
    """
    # For production, verify the cron secret
    import os

    expected_secret = os.getenv("VERCEL_CRON_SECRET")
    if expected_secret and x_vercel_cron_secret != expected_secret:
        logger.warning("Unauthorized cron request")
        raise HTTPException(status_code=401, detail="Unauthorized")

    try:
        await polling_check_results()
        return {"status": "success", "message": "Polling check completed"}
    except Exception as e:
        logger.error(f"Cron error: {str(e)}")
        return {"status": "error", "message": str(e)}
