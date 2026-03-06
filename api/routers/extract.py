from datetime import datetime
import logging
import re
from io import BytesIO
from typing import Optional

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
except ImportError:
    from services.vision import get_vision_client
    from services.combinations import (
        expand_toto_combinations,
        expand_toto_system_roll,
        validate_system_type,
    )
    from services.supabase import get_supabase_client

router = APIRouter()
logger = logging.getLogger(__name__)


def insert_ticket_to_supabase(
    extracted_data: dict,
    user_id: Optional[str] = None,
) -> dict:
    """
    Insert extracted ticket data and expanded combinations into Supabase.
    
    Args:
        extracted_data: The extracted lottery data from OCR
        user_id: Optional user ID to associate with the ticket
    
    Returns:
        Dict with ticket_id and status
    """
    try:
        supabase = get_supabase_client()
        
        game_type = extracted_data.get("game_type")
        ticket_type = extracted_data.get("ticket_type")
        draw_date = extracted_data.get("draw_date")
        numbers = extracted_data.get("numbers", [])
        expanded_combinations = extracted_data.get("expanded_combinations", [])
        confidence = extracted_data.get("confidence", 0.0)
        combinations_count = extracted_data.get("combinations_count", 0)
        
        # Validate data before insertion
        if not numbers:
            logger.warning("Cannot insert ticket: no numbers extracted")
            return {"status": "skipped", "reason": "no_numbers"}
        
        # Step 1: Insert main ticket record
        ticket_data = {
            "user_id": user_id,
            "game_type": game_type,
            "ticket_type": ticket_type,
            "draw_date": draw_date,
            "selected_numbers": numbers,
            "combinations_count": combinations_count,
            "ocr_confidence": confidence,
            "metadata": {
                "ocr_confidence": confidence,
                "is_system_bet": "System" in (ticket_type or ""),
                "is_system_roll": "System Roll" in (ticket_type or ""),
            },
            "status": "pending",
        }
        
        # Insert ticket record
        ticket_response = supabase.table("tickets").insert(ticket_data).execute()
        
        if not ticket_response.data:
            logger.error(f"Failed to insert ticket: {ticket_response}")
            return {"status": "error", "reason": "ticket_insert_failed"}
        
        inserted_ticket_id = ticket_response.data[0]["id"]
        logger.info(f"Ticket inserted with ID: {inserted_ticket_id}")
        
        combinations_inserted = 0
        
        # Step 2: Insert expanded combinations (if available)
        if expanded_combinations:
            combinations_batch = []
            
            for idx, combination in enumerate(expanded_combinations):
                combination_record = {
                    "ticket_id": inserted_ticket_id,
                    "combination_index": idx,
                    "numbers": combination,
                    "sorted_numbers": sorted(combination),
                }
                combinations_batch.append(combination_record)
                
                # Batch insert in chunks of 100
                if len(combinations_batch) >= 100:
                    insert_response = (
                        supabase.table("ticket_combinations")
                        .insert(combinations_batch)
                        .execute()
                    )
                    combinations_inserted += len(combinations_batch)
                    combinations_batch = []
            
            # Insert remaining combinations
            if combinations_batch:
                insert_response = (
                    supabase.table("ticket_combinations")
                    .insert(combinations_batch)
                    .execute()
                )
                combinations_inserted += len(combinations_batch)
            
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
            "numbers": numbers,
            "expected_number_count": expected_number_count,
            "confidence": round(confidence, 2),
            "count": len(numbers),
            "expanded_combinations": expanded_combinations,
            "combinations_count": len(expanded_combinations) if expanded_combinations else None,
        }
        
        # Attempt to insert into Supabase
        db_result = insert_ticket_to_supabase(extracted_data_dict, user_id=user_id)
        
        return {
            "status": "success",
            "extracted_data": extracted_data_dict,
            "database": db_result,
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
