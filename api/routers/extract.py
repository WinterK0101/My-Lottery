from datetime import datetime, date
import logging
import re
from io import BytesIO
from typing import Optional
import uuid

from fastapi import APIRouter, File, HTTPException, UploadFile
from google.cloud import vision
import numpy as np
from PIL import Image

try:
    from ..services.vision import get_vision_client
    from ..services.combinations import (
        expand_toto_combinations,
        expand_toto_system_roll,
        validate_system_type,
    )
    from ..services.supabase import get_supabase_client
    from ..schemas import (
        TicketCreate,
        TicketMetadata,
        GameType,
        TicketCombinationBatch,
    )
except ImportError:
    from services.vision import get_vision_client
    from services.combinations import (
        expand_toto_combinations,
        expand_toto_system_roll,
        validate_system_type,
    )
    from services.supabase import get_supabase_client
    from schemas import (
        TicketCreate,
        TicketMetadata,
        GameType,
        TicketCombinationBatch,
    )

router = APIRouter()
logger = logging.getLogger(__name__)


def upload_image_to_supabase_storage(
    image_bytes: bytes,
    filename: str,
) -> Optional[str]:
    """
    Upload image to Supabase storage and return public URL.
    
    Args:
        image_bytes: Raw image bytes
        filename: Filename for the uploaded image
    
    Returns:
        Public URL of uploaded image, or None if upload fails
    """
    try:
        supabase = get_supabase_client()
        
        # Generate unique filename to prevent collisions
        unique_filename = f"{uuid.uuid4()}_{filename}"
        
        # Upload to 'ticket-images' bucket
        bucket_name = "ticket-images"
        storage_path = f"uploads/{unique_filename}"
        
        # Upload file
        response = supabase.storage.from_(bucket_name).upload(
            path=storage_path,
            file=image_bytes,
            file_options={"content-type": "image/jpeg"},
        )
        
        # Get public URL
        public_url = supabase.storage.from_(bucket_name).get_public_url(storage_path)
        
        logger.info(f"Image uploaded successfully: {public_url}")
        return public_url
        
    except Exception as e:
        logger.error(f"Failed to upload image to Supabase storage: {str(e)}")
        return None


def insert_ticket_to_supabase(
    extracted_data: dict,
    user_id: Optional[str] = None,
    image_url: Optional[str] = None,
) -> dict:
    """
    Insert extracted ticket data and expanded combinations into Supabase.
    
    Args:
        extracted_data: The extracted lottery data from OCR
        user_id: Optional user ID to associate with the ticket
        image_url: Optional URL of uploaded image in Supabase storage
    
    Returns:
        Dict with ticket_id and status
    """
    try:
        # Default to fixed user_id if not provided
        if not user_id:
            user_id = 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d'
        
        supabase = get_supabase_client()
        
        game_type = extracted_data.get("game_type")
        ticket_type = extracted_data.get("ticket_type")
        draw_date = extracted_data.get("draw_date")
        draw_id = extracted_data.get("draw_id")
        numbers = extracted_data.get("numbers", [])
        ticket_serial_number = extracted_data.get("ticket_serial_number")
        expanded_combinations = extracted_data.get("expanded_combinations", [])
        confidence = extracted_data.get("confidence", 0.0)
        combinations_count = extracted_data.get("combinations_count", 0)
        
        # Validate data before insertion
        if not numbers:
            logger.warning("Cannot insert ticket: no numbers extracted")
            return {"status": "skipped", "reason": "no_numbers"}
        
        # Check for duplicate ticket by serial number
        if ticket_serial_number:
            try:
                existing_ticket = (
                    supabase.table("tickets")
                    .select("id, created_at, status, prize_tier, user_id, game_type, draw_date, draw_id, winning_amount")
                    .eq("ticket_serial_number", ticket_serial_number)
                    .execute()
                )
                
                if existing_ticket.data and len(existing_ticket.data) > 0:
                    existing = existing_ticket.data[0]
                    logger.info(f"Duplicate ticket detected: {ticket_serial_number}")
                    
                    # If ticket has been evaluated and has a user_id, re-send notification
                    if existing.get("status") in ["won", "lost"] and existing.get("user_id"):
                        try:
                            from ..services.notification_service import create_notification_service
                            notification_service = create_notification_service()
                            
                            is_winner = existing.get("status") == "won"
                            prize_tier = existing.get("prize_tier", "No Prize")
                            prize_amount = existing.get("winning_amount", 0)
                            
                            notification_sent = notification_service.notify_ticket_result(
                                user_id=existing.get("user_id"),
                                ticket_id=existing["id"],
                                is_winner=is_winner,
                                prize_tier=prize_tier,
                                prize_amount=prize_amount,
                                game_type=existing.get("game_type", "Unknown"),
                                draw_date=existing.get("draw_date", "Unknown"),
                                draw_id=existing.get("draw_id")
                            )
                            
                            logger.info(f"Re-sent notification for duplicate ticket: {ticket_serial_number}, sent={notification_sent}")
                        except Exception as notify_err:
                            logger.error(f"Failed to re-send notification for duplicate: {str(notify_err)}")
                    
                    return {
                        "status": "duplicate",
                        "ticket_id": existing["id"],
                        "message": f"This ticket was already uploaded on {existing['created_at']}",
                        "existing_ticket": existing,
                        "notification_resent": existing.get("status") in ["won", "lost"],
                    }
            except Exception as dup_check_error:
                logger.warning(f"Duplicate check failed: {str(dup_check_error)}")
                # Continue with insertion if duplicate check fails
        
        # Step 1: Insert main ticket record using schema
        # For non-system tickets, combinations_count is 1 (the single selected combination)
        final_combinations_count = combinations_count if combinations_count is not None else (
            len(expanded_combinations) if expanded_combinations else 1
        )
        
        ticket_schema = TicketCreate(
            user_id=user_id,
            game_type=GameType(game_type),
            ticket_type=ticket_type,
            draw_date=date.fromisoformat(draw_date) if isinstance(draw_date, str) else draw_date,
            draw_id=draw_id,
            ticket_serial_number=ticket_serial_number,
            selected_numbers=numbers,
            combinations_count=final_combinations_count,
            ocr_confidence=confidence,
            image_url=image_url,
            metadata=TicketMetadata(
                ocr_confidence=confidence,
                is_system_bet="System" in (ticket_type or ""),
                is_system_roll="System Roll" in (ticket_type or ""),
            ),
        )
        
        # Insert ticket record
        ticket_response = supabase.table("tickets").insert(ticket_schema.to_db_dict()).execute()
        
        if not ticket_response.data:
            logger.error(f"Failed to insert ticket: {ticket_response}")
            return {"status": "error", "reason": "ticket_insert_failed"}
        
        inserted_ticket_id = ticket_response.data[0]["id"]
        logger.info(f"Ticket inserted with ID: {inserted_ticket_id}")
        
        combinations_inserted = 0
        
        # Step 2: Insert expanded combinations using schema (if available)
        if expanded_combinations:
            # Create batch using schema
            combinations_batch_schema = TicketCombinationBatch.from_ticket(
                ticket_id=inserted_ticket_id,
                combinations=expanded_combinations
            )
            
            # Batch insert in chunks of 100
            all_combinations = combinations_batch_schema.to_db_list()
            for i in range(0, len(all_combinations), 100):
                chunk = all_combinations[i:i + 100]
                insert_response = (
                    supabase.table("ticket_combinations")
                    .insert(chunk)
                    .execute()
                )
                combinations_inserted += len(chunk)
            
            logger.info(f"Inserted {combinations_inserted} combinations for ticket {inserted_ticket_id}")
        
        return {
            "status": "success",
            "ticket_id": inserted_ticket_id,
            "combinations_inserted": combinations_inserted,
        }
    
    except Exception as e:
        logger.error(f"Error inserting ticket to Supabase: {str(e)}", exc_info=True)
        return {"status": "error", "reason": str(e)}


@router.post("/api/extract")
async def extract_lottery_data(file: UploadFile = File(...), user_id: Optional[str] = None):
    """Extract lottery numbers from ticket image using OCR and save to Supabase"""
    try:
        # Default to fixed user_id if not provided
        if not user_id:
            user_id = 'a1b2c3d4-e5f6-4a7b-8c9d-0e1f2a3b4c5d'
        
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")

        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid file type: {file.content_type}. Allowed: {', '.join(allowed_types)}",
            )

        # Read and parse image
        try:
            contents = await file.read()
            image_bytes = BytesIO(contents)
        except Exception as e:
            logger.error(f"Image reading error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Could not read image: {str(e)}")

        # Run OCR using Google Cloud Vision API
        try:
            client = get_vision_client()
            image = vision.Image(content=contents)
            response = client.text_detection(image=image)

            if response.error and response.error.message:
                raise RuntimeError(response.error.message)

            # Convert Vision API response to easyocr-like format
            results_with_boxes = []
            annotations = response.text_annotations
            full_text = annotations[0].description if annotations else ""

            if not annotations:
                results_with_boxes = []
            else:
                # Skip the first annotation (it's the full text)
                for annotation in annotations[1:]:
                    vertices = annotation.bounding_poly.vertices
                    # Convert vertices to list of [x, y] coordinates
                    bbox = [[int(v.x or 0), int(v.y or 0)] for v in vertices]
                    if len(bbox) < 4:
                        bbox = (bbox + [[0, 0], [0, 0], [0, 0], [0, 0]])[:4]
                    text = annotation.description
                    confidence = float(
                        getattr(annotation, "confidence", 0.0)
                        or getattr(annotation, "score", 0.0)
                        or 0.95
                    )
                    results_with_boxes.append([bbox, text, confidence])
        except Exception as e:
            logger.error(f"OCR error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")

        # Extract text from OCR results - join into single string for regex matching
        text_strings = [text[1] for text in results_with_boxes]
        if not full_text:
            full_text = " ".join(text_strings)
        confidence = np.mean([float(text[2]) for text in results_with_boxes]) if results_with_boxes else 0.0

        # Extract ticket serial number (format: 739462-6-6419873-005)
        ticket_serial_number = None
        serial_pattern = r"\b\d{5,7}-\d{1,2}-\d{6,8}-\d{3,4}\b"
        serial_match = re.search(serial_pattern, full_text)
        if serial_match:
            ticket_serial_number = serial_match.group()
            logger.info(f"Extracted ticket serial number: {ticket_serial_number}")
        else:
            # Try alternative patterns (numbers might be split by spaces in OCR)
            compact_text = re.sub(r"\s+", "", full_text)
            serial_match_compact = re.search(serial_pattern, compact_text)
            if serial_match_compact:
                ticket_serial_number = serial_match_compact.group()
                logger.info(f"Extracted ticket serial number (compact): {ticket_serial_number}")

        # Robust game type detection (handles OCR variants like "4 D", "4-D", "40", split tokens)
        full_text_upper = full_text.upper()
        compact_text = re.sub(r"[^A-Z0-9]", "", full_text_upper)
        normalized_tokens = [re.sub(r"[^A-Z0-9]", "", token.upper()) for token in text_strings]
        normalized_tokens = [token for token in normalized_tokens if token]

        has_toto = (
            bool(re.search(r"\bTOTO\b", full_text_upper))
            or "TOTO" in compact_text
            or any(token == "TOTO" for token in normalized_tokens)
        )

        has_4d = (
            bool(re.search(r"\b4\W*[D0O]\b", full_text_upper))
            or any(token in {"4D", "40", "4O"} for token in normalized_tokens)
        )

        # Handle split OCR tokens like "4" followed by "D"/"0"/"O"
        if not has_4d:
            for idx in range(len(normalized_tokens) - 1):
                if normalized_tokens[idx] == "4" and normalized_tokens[idx + 1] in {"D", "0", "O"}:
                    has_4d = True
                    break

        if has_toto:
            detected_game_type = "TOTO"
        elif has_4d:
            detected_game_type = "4D"
        else:
            detected_game_type = "Unknown"
        ticket_type = None
        expected_number_count = None

        if detected_game_type == "TOTO":
            system_size_match = re.search(r"\bSYSTEM\D*([7-9]|1[0-2])\b", full_text_upper)
            is_system_roll = bool(re.search(r"\bSYSTEM\W*ROLL\b", full_text_upper))

            if is_system_roll:
                ticket_type = "System Roll"
                expected_number_count = 5
            elif system_size_match:
                system_size = int(system_size_match.group(1))
                ticket_type = f"System {system_size}"
                expected_number_count = system_size
            elif "ORDINARY" in full_text_upper:
                ticket_type = "Ordinary"
                expected_number_count = 6
            elif "SYSTEM" in full_text_upper:
                ticket_type = "System"
                expected_number_count = 6
            else:
                ticket_type = "Unknown"
                expected_number_count = 6
        elif detected_game_type == "4D":
            ticket_type = "Ordinary"
            expected_number_count = 1
        else:
            return {
                "status": "error",
                "message": "Unable to detect lottery type (TOTO or 4D). Please retake the picture with the ticket clearly visible.",
                "extracted_data": {
                    "game_type": "Unknown",
                    "ticket_type": None,
                    "draw_date": None,
                    "numbers": [],
                    "expected_number_count": None,
                    "confidence": round(confidence, 2),
                },
            }

        # Extract draw date (matches format DD/MM/YY or DD/MM/YYYY)
        draw_date = None
        date_match = re.search(r"\d{2}/\d{2}/\d{2,4}", full_text)
        if date_match:
            date_str = date_match.group()
            try:
                # Parse DD/MM/YY or DD/MM/YYYY
                parts = date_str.split("/")
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                if len(parts[2]) == 2:
                    year = 2000 + year
                draw_date = f"{year:04d}-{month:02d}-{day:02d}"
            except:
                draw_date = datetime.now().strftime("%Y-%m-%d")
        else:
            draw_date = datetime.now().strftime("%Y-%m-%d")

        # Extract draw ID (format: 4162/26 where draw_id = 4162)
        # Usually appears right after draw date on the ticket
        draw_id = None
        draw_id_match = re.search(r"\b(\d{4})/(\d{2})\b", full_text)
        if draw_id_match:
            draw_id = draw_id_match.group(1)  # Extract just the first part (4162)
            logger.info(f"Extracted draw ID: {draw_id}")
        else:
            # Try alternative pattern without slash (just 4-digit number near date)
            # Look for 4-digit numbers that aren't part of a date
            lines = full_text.split("\n")
            for line in lines:
                if date_match and date_match.group() in line:
                    # Found the line with the date, look for draw ID
                    potential_ids = re.findall(r"(?<!\d)\d{4}(?!/)", line)
                    if potential_ids:
                        draw_id = potential_ids[0]
                        logger.info(f"Extracted draw ID (alternative): {draw_id}")
                        break

        # Extract lottery numbers from full OCR text
        # Vision API is accurate enough; no need for complex ROI/alignment filtering

        # Filter for valid lottery numbers based on game type
        if detected_game_type == "TOTO":
            # TOTO: Extract from group marker lines (A-E) in order
            target_count = expected_number_count if expected_number_count is not None else 6

            # Find the first group marker line (A through E for multiple bet groups)
            first_marker_index = -1
            lines = full_text.split("\n")
            for i, line in enumerate(lines):
                if re.search(r"^[A-E]\.", line) or re.search(r"^\s*[A-E]\.?\s+\d", line):
                    first_marker_index = i
                    break

            # Extract numbers from first marker onwards, including continuation lines
            candidates = []
            if first_marker_index >= 0:
                # Collect all numbers from marker line onwards until we have enough
                remaining_text = "\n".join(lines[first_marker_index:])
                all_numbers = re.findall(r"\b\d{1,2}\b", remaining_text)
                for num_str in all_numbers:
                    num = int(num_str)
                    if 1 <= num <= 49:
                        candidates.append(num)
                        if len(candidates) >= target_count:
                            break

            # Remove duplicates while preserving order
            seen = set()
            numbers = []
            for num in candidates:
                if num not in seen and num != 0:
                    seen.add(num)
                    numbers.append(num)

            numbers = numbers[:target_count]
        elif detected_game_type == "4D":
            # 4D: Extract first 4-digit number from full_text
            four_digit_matches = re.findall(r"\b\d{4}\b", full_text)
            if four_digit_matches:
                numbers = [int(four_digit_matches[0])]
            else:
                # Fallback: OCR may read leading "A." as "4" and produce a 5-digit number
                prefixed_matches = re.findall(r"\b4\d{4}\b", full_text)
                if prefixed_matches:
                    numbers = [int(prefixed_matches[0][1:])]
                else:
                    numbers = []

        if not numbers:
            # Debug: log what was detected
            debug_info = {
                "game_type": detected_game_type,
                "full_ocr_text": full_text[:200],  # First 200 chars
                "total_detections": len(results_with_boxes),
                "detection_samples": [
                    {"text": det[1], "bbox_y_range": [int(np.min(det[0][:, 1])), int(np.max(det[0][:, 1]))]}
                    for det in results_with_boxes[:5]
                ],
            }
            logger.error(f"No numbers extracted. Debug: {debug_info}")

            return {
                "status": "warning",
                "message": "No lottery numbers detected. Please try a clearer image.",
                "extracted_data": {
                    "game_type": detected_game_type,
                    "ticket_type": ticket_type,
                    "draw_date": draw_date,
                    "numbers": [],
                    "expected_number_count": expected_number_count,
                    "confidence": round(confidence, 2),
                },
                "debug": debug_info,
            }

        # Expand combinations for TOTO System bets
        expanded_combinations = None
        if detected_game_type == "TOTO" and ticket_type:
            try:
                # Check if it's a System Roll
                if "System Roll" in ticket_type:
                    expanded_combinations = expand_toto_system_roll(numbers)
                    logger.info(f"System Roll: {len(numbers)} numbers expanded to {len(expanded_combinations)} combinations")
                else:
                    # Check if it's a regular System bet (7-12)
                    system_type = validate_system_type(ticket_type)
                    if system_type:
                        expanded_combinations = expand_toto_combinations(numbers, system_type)
                        logger.info(f"System {system_type}: expanded to {len(expanded_combinations)} combinations")
            except ValueError as e:
                logger.warning(f"Combination expansion failed: {str(e)}")
                # Continue without expanded combinations if validation fails

        # Prepare extracted data for return and database insertion
        extracted_data_dict = {
            "game_type": detected_game_type,
            "ticket_type": ticket_type,
            "draw_date": draw_date,
            "draw_id": draw_id,
            "numbers": numbers,
            "ticket_serial_number": ticket_serial_number,
            "expected_number_count": expected_number_count,
            "confidence": round(confidence, 2),
            "count": len(numbers),
            "expanded_combinations": expanded_combinations,
            "combinations_count": len(expanded_combinations) if expanded_combinations else None,
        }
        
        # Upload image to Supabase storage
        image_url = upload_image_to_supabase_storage(
            image_bytes=contents,
            filename=file.filename or "ticket.jpg",
        )
        
        # Attempt to insert into Supabase
        db_result = insert_ticket_to_supabase(
            extracted_data_dict,
            user_id=user_id,
            image_url=image_url,
        )
        
        # If ticket was successfully inserted and draw date is in the past, evaluate immediately
        evaluation_result = None
        notification_sent = False
        
        if db_result.get("status") == "success" and draw_date:
            try:
                # Check if draw date is in the past (including today)
                ticket_draw_date = date.fromisoformat(draw_date) if isinstance(draw_date, str) else draw_date
                today = date.today()
                
                if ticket_draw_date <= today:
                    logger.info(f"Draw date {ticket_draw_date} is in the past. Attempting immediate evaluation.")
                    
                    # Import services for evaluation
                    from ..services.draw_results_manager import create_draw_results_manager
                    from ..services.prize_matching import evaluate_ticket, get_prize_amount
                    from ..services.notification_service import create_notification_service
                    
                    draw_manager = create_draw_results_manager()
                    notification_service = create_notification_service()
                    
                    # Fetch draw results for this date
                    draw_results = draw_manager.get_draw_results(
                        game_type=detected_game_type,
                        draw_date=draw_date,
                        fetch_if_missing=True  # Try to fetch from web if not in database
                    )
                    
                    if draw_results and draw_results.get("status") == "success":
                        logger.info(f"Found draw results for {detected_game_type} on {draw_date}")
                        
                        # Prepare ticket data for evaluation
                        ticket_id = db_result.get("ticket_id")
                        ticket_data = {
                            "game_type": detected_game_type,
                            "numbers": numbers,
                            "ticket_type": ticket_type,
                        }
                        
                        # Evaluate the ticket
                        eval_result = evaluate_ticket(ticket_data, draw_results)
                        evaluation_result = eval_result
                        
                        # Determine status and prize tier
                        prize_tier = eval_result.get("prize_tier", "No Prize")
                        is_winner = eval_result.get("is_winner", False)
                        status = "won" if is_winner else "lost"
                        winning_amount = get_prize_amount(detected_game_type, prize_tier) if is_winner else 0.0
                        
                        # Update ticket in database with evaluation results
                        supabase = get_supabase_client()
                        update_data = {
                            "status": status,
                            "prize_tier": prize_tier,
                            "winning_amount": winning_amount,
                        }
                        
                        supabase.table("tickets").update(update_data).eq("id", ticket_id).execute()
                        logger.info(f"Updated ticket {ticket_id}: status={status}, prize_tier={prize_tier}")
                        
                        # Send notification
                        notification_sent = notification_service.notify_ticket_result(
                            user_id=user_id,
                            ticket_id=ticket_id,
                            game_type=detected_game_type,
                            draw_date=draw_date,
                            draw_id=draw_id,
                            is_winner=is_winner,
                            prize_tier=prize_tier,
                            prize_amount=int(winning_amount),
                        )
                        logger.info(f"Notification sent for ticket {ticket_id}: {notification_sent}")
                    else:
                        logger.info(f"No draw results found yet for {detected_game_type} on {draw_date}")
            
            except Exception as eval_error:
                logger.error(f"Error during immediate evaluation: {str(eval_error)}", exc_info=True)
                # Don't fail the entire request if evaluation fails
        
        return {
            "status": "success",
            "extracted_data": extracted_data_dict,
            "database": db_result,
            "evaluation": evaluation_result,
            "notification_sent": notification_sent,
            "diagnostics": {
                "total_vision_detections": len(results_with_boxes),
                "full_ocr_text_preview": full_text[:300],
            },
        }

    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Extract error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")
