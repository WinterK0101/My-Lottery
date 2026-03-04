from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn
from datetime import datetime
import logging
import os
from pywebpush import webpush, WebPushException
import json
from dotenv import load_dotenv
from pathlib import Path
import numpy as np
from io import BytesIO
from PIL import Image
import easyocr
import re

# Load environment variables from .env.local in parent directory
env_path = Path(__file__).parent.parent / '.env.local'
load_dotenv(dotenv_path=env_path)

app = FastAPI()

# Enable CORS for frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8000",
        "http://127.0.0.1:8000",
    ],
    allow_origin_regex=r"^https?://(" \
                       r"localhost|127\.0\.0\.1|" \
                       r"192\.168\.\d+\.\d+|" \
                       r"10\.\d+\.\d+\.\d+|" \
                       r"172\.(1[6-9]|2\d|3[0-1])\.\d+\.\d+|" \
                       r"[a-zA-Z0-9-]+\.ngrok-free\.app|" \
                       r"[a-zA-Z0-9-]+\.ngrok-free\.dev|" \
                       r"[a-zA-Z0-9-]+\.ngrok\.io" \
                       r")(:\d+)?$",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

logger = logging.getLogger(__name__)

# Initialize OCR reader (once on startup - cached)
try:
    ocr_reader = easyocr.Reader(['en'], gpu=False)  # Use CPU to avoid GPU issues
except Exception:
    ocr_reader = None

def get_ocr_reader():
    """Get OCR reader instance"""
    global ocr_reader
    if ocr_reader is None:
        try:
            ocr_reader = easyocr.Reader(['en'], gpu=False)
        except Exception as e:
            logger.error(f"Failed to initialize OCR reader: {e}", exc_info=True)
            raise RuntimeError(f"OCR reader initialization failed: {e}")
    return ocr_reader

# Store subscription in memory (in production, use a database)
subscription = None

class NotificationRequest(BaseModel):
    message: str

@app.get("/api/python")
def hello_world():
    return {"message": "Hello from FastAPI!"}

@app.post("/api/send-notification")
async def send_notification(req: NotificationRequest):
    """Send push notification to subscribed users"""
    global subscription
    try:
        if not req.message:
            raise HTTPException(status_code=400, detail="message is required")
        
        if not subscription:
            raise HTTPException(status_code=400, detail="No subscription available")
        
        # Get VAPID keys from environment
        vapid_private_key = os.getenv("VAPID_PRIVATE_KEY")
        vapid_public_key = os.getenv("NEXT_PUBLIC_VAPID_PUBLIC_KEY")
        
        if not vapid_private_key or not vapid_public_key:
            raise HTTPException(status_code=500, detail="VAPID keys not configured")
        
        # Prepare notification payload
        notification_payload = json.dumps({
            "title": "Lottery Update",
            "body": req.message,
            "icon": "/web-app-manifest-192x192.png"
        })
        
        # Send push notification using pywebpush
        try:
            webpush(
                subscription_info=subscription,
                data=notification_payload,
                vapid_private_key=vapid_private_key,
                vapid_claims={
                    "sub": "mailto:example@yourdomain.com"
                }
            )
            return {"success": True, "message": "Notification sent"}
        except WebPushException as e:
            logger.error(f"WebPush error: {e}")
            # If push fails due to expired subscription, clear it
            if e.response and e.response.status_code in [404, 410]:
                subscription = None
                raise HTTPException(status_code=410, detail="Subscription expired")
            raise HTTPException(status_code=500, detail=f"Push failed: {str(e)}")
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Error sending notification: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/api/subscribe")
async def subscribe(data: dict):
    """Subscribe user to push notifications"""
    global subscription
    try:
        subscription = data
        return {"success": True, "message": "Subscribed successfully"}
    except Exception as e:
        logger.error(f"Subscribe error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/api/unsubscribe")
async def unsubscribe():
    """Unsubscribe user from push notifications"""
    global subscription
    try:
        subscription = None
        return {"success": True, "message": "Unsubscribed successfully"}
    except Exception as e:
        logger.error(f"Unsubscribe error: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.post("/api/extract")
async def extract_lottery_data(file: UploadFile = File(...)):
    """Extract lottery numbers from ticket image using OCR"""
    try:
        if not file:
            raise HTTPException(status_code=400, detail="No file provided")
        
        # Validate file type
        allowed_types = ["image/jpeg", "image/png", "image/webp", "image/jpg"]
        if file.content_type not in allowed_types:
            raise HTTPException(
                status_code=400, 
                detail=f"Invalid file type: {file.content_type}. Allowed: {', '.join(allowed_types)}"
            )
        
        # Read and parse image
        try:
            contents = await file.read()
            image = Image.open(BytesIO(contents))
            image_array = np.array(image)
        except Exception as e:
            logger.error(f"Image reading error: {str(e)}")
            raise HTTPException(status_code=400, detail=f"Could not read image: {str(e)}")
        
        # Run OCR with detailed results for internal filtering
        try:
            reader = get_ocr_reader()
            results_with_boxes = reader.readtext(image_array, detail=1)
        except Exception as e:
            logger.error(f"OCR error: {str(e)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"OCR processing failed: {str(e)}")
        
        # Extract text from OCR results - join into single string for regex matching
        text_strings = [text[1] for text in results_with_boxes]
        full_text = " ".join(text_strings)
        confidence = np.mean([float(text[2]) for text in results_with_boxes]) if results_with_boxes else 0.0
        
        # Robust game type detection (handles OCR variants like "4 D", "4-D", "40", split tokens)
        full_text_upper = full_text.upper()
        compact_text = re.sub(r'[^A-Z0-9]', '', full_text_upper)
        normalized_tokens = [re.sub(r'[^A-Z0-9]', '', token.upper()) for token in text_strings]
        normalized_tokens = [token for token in normalized_tokens if token]

        has_toto = (
            bool(re.search(r'\bTOTO\b', full_text_upper))
            or "TOTO" in compact_text
            or any(token == "TOTO" for token in normalized_tokens)
        )

        has_4d = (
            bool(re.search(r'\b4\W*[D0O]\b', full_text_upper))
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
            system_size_match = re.search(r'\bSYSTEM\D*([7-9]|1[0-2])\b', full_text_upper)
            is_system_roll = bool(re.search(r'\bSYSTEM\W*ROLL\b', full_text_upper))

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
                    "confidence": round(confidence, 2)
                }
            }
        
        # Extract draw date (matches format DD/MM/YY or DD/MM/YYYY)
        draw_date = None
        date_match = re.search(r'\d{2}/\d{2}/\d{2,4}', full_text)
        if date_match:
            date_str = date_match.group()
            try:
                # Parse DD/MM/YY or DD/MM/YYYY
                parts = date_str.split('/')
                day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                if len(parts[2]) == 2:
                    year = 2000 + year
                draw_date = f"{year:04d}-{month:02d}-{day:02d}"
            except:
                draw_date = datetime.now().strftime("%Y-%m-%d")
        else:
            draw_date = datetime.now().strftime("%Y-%m-%d")
        
        # Extract lottery numbers - find all 2-digit numbers
        # Filter by confidence to avoid misreading background text
        CONFIDENCE_THRESHOLD = 0.4  # Adjustable threshold for filtering low-confidence detections
        
        # Find boundary keywords to define the region of interest (ROI)
        # Numbers should be between bet type (ORDINARY/SYSTEM 7-12/QUICKPICK) and 'DRAW'
        top_boundary_y = None
        draw_y = None
        top_boundary_text = None
        
        for bbox, text, conf in results_with_boxes:
            text_upper = text.upper()
            coords = np.array(bbox)
            centroid_y = np.mean(coords[:, 1])
            
            # Check for top boundary: ORDINARY, SYSTEM 7-12, QUICKPICK, ROLL
            is_top_boundary = False
            if 'ORDINARY' in text_upper:
                is_top_boundary = True
            elif 'QUICKPICK' in text_upper:
                is_top_boundary = True
            elif 'ROLL' in text_upper:
                is_top_boundary = True
            elif 'SYSTEM' in text_upper:
                # Match SYSTEM followed by optional number (7-12)
                # This catches "SYSTEM", "SYSTEM 7", "SYSTEM7", etc.
                is_top_boundary = True
            
            if is_top_boundary:
                # Take the lowest Y (topmost position) as the boundary
                if top_boundary_y is None or centroid_y < top_boundary_y:
                    top_boundary_y = centroid_y
                    top_boundary_text = text
            
            # Check for bottom boundary: DRAW
            if 'DRAW' in text_upper and 'DRAW' not in ['WITHDRAW', 'DRAWING']:
                # Take the highest Y (bottommost position) as the boundary
                if draw_y is None or centroid_y > draw_y:
                    draw_y = centroid_y
        
        # Define ROI with some padding
        Y_PADDING = 50  # pixels padding above/below boundaries
        if top_boundary_y is not None and draw_y is not None:
            # Ensure top boundary is above draw (smaller Y value)
            y_min = min(top_boundary_y, draw_y) - Y_PADDING
            y_max = max(top_boundary_y, draw_y) + Y_PADDING
        elif top_boundary_y is not None:
            # Only found top boundary, use it as reference
            y_min = top_boundary_y - Y_PADDING
            y_max = top_boundary_y + 400  # Assume numbers are within 400px below
        else:
            # No boundaries found, don't filter by region
            y_min = None
            y_max = None
        
        # First pass: collect all numbers with their positions
        number_detections = []
        for bbox, text, conf in results_with_boxes:
            # Only process high-confidence detections for number extraction
            if conf > CONFIDENCE_THRESHOLD:
                # Find digits in this text fragment
                digits = re.findall(r'\b\d{1,2}\b', text)
                if digits:
                    # Calculate centroid of bounding box
                    coords = np.array(bbox)
                    centroid_x = np.mean(coords[:, 0])
                    centroid_y = np.mean(coords[:, 1])
                    
                    # Check if within ROI
                    in_roi = True
                    if y_min is not None and y_max is not None:
                        in_roi = y_min <= centroid_y <= y_max
                    
                    for digit in digits:
                        number_detections.append({
                            'number': digit,
                            'centroid_x': centroid_x,
                            'centroid_y': centroid_y,
                            'bbox': bbox,
                            'conf': conf,
                            'text': text,
                            'in_roi': in_roi
                        })
        
        # Filter by ROI
        if y_min is not None and y_max is not None:
            in_roi_detections = [det for det in number_detections if det['in_roi']]
            number_detections = in_roi_detections
        
        # Additional filter: numbers should be horizontally aligned (similar Y-coordinates)
        # Lottery numbers are typically printed on the same horizontal line
        if len(number_detections) > 0:
            Y_ALIGNMENT_THRESHOLD = 30  # pixels - max difference in Y-coordinate for horizontal alignment
            
            # Group numbers by Y-coordinate similarity
            horizontal_groups = []
            used_indices = set()
            
            for i, det in enumerate(number_detections):
                if i in used_indices:
                    continue
                
                # Start a new horizontal group with this detection
                group = [i]
                group_y_values = [det['centroid_y']]
                
                # Find all other detections with similar Y-coordinate
                for j, other_det in enumerate(number_detections):
                    if j <= i or j in used_indices:
                        continue
                    
                    # Check if Y-coordinate is similar to any in the group
                    y_diff = abs(det['centroid_y'] - other_det['centroid_y'])
                    
                    # Only add to group if aligned AND group hasn't reached expected size
                    # This filters out groups with too many numbers
                    if y_diff < Y_ALIGNMENT_THRESHOLD and len(group) < expected_number_count:
                        group.append(j)
                        group_y_values.append(other_det['centroid_y'])
                        used_indices.add(j)
                
                used_indices.add(i)
                avg_y = np.mean(group_y_values)
                horizontal_groups.append({
                    'indices': group,
                    'avg_y': avg_y,
                    'size': len(group)
                })
            
            if len(horizontal_groups) > 1:
                # Select the largest horizontal group (most numbers aligned)
                largest_group = max(horizontal_groups, key=lambda g: g['size'])
                aligned_detections = [number_detections[i] for i in largest_group['indices']]
                number_detections = aligned_detections
        
        # Extract numbers from filtered detections
        numbers_match = [det['number'] for det in number_detections]
        
        # Filter for valid lottery numbers based on game type
        if detected_game_type == "TOTO":
            # TOTO: number count depends on bet type
            valid_numbers = [int(n) for n in numbers_match if 1 <= int(n) <= 49]
            # Remove duplicates while preserving order
            seen = set()
            numbers = []
            for num in valid_numbers:
                if num not in seen and num != 0:
                    seen.add(num)
                    numbers.append(num)
            target_count = expected_number_count if expected_number_count is not None else 6
            numbers = numbers[:target_count]
        elif detected_game_type == "4D":
            # 4D: look for 4-digit numbers with ROI filtering
            four_digit_detections = []
            
            for bbox, text, conf in results_with_boxes:
                if conf > CONFIDENCE_THRESHOLD:
                    four_digit_matches = re.findall(r'\b\d{4}\b', text)
                    if four_digit_matches:
                        # Calculate centroid
                        coords = np.array(bbox)
                        centroid_x = np.mean(coords[:, 0])
                        centroid_y = np.mean(coords[:, 1])
                        
                        # Check if within ROI
                        in_roi = True
                        if y_min is not None and y_max is not None:
                            in_roi = y_min <= centroid_y <= y_max
                        
                        for match in four_digit_matches:
                            four_digit_detections.append({
                                'number': int(match),
                                'centroid_y': centroid_y,
                                'conf': conf,
                                'text': text,
                                'in_roi': in_roi
                            })
            
            # Filter by ROI (same as TOTO)
            if y_min is not None and y_max is not None:
                filtered_4d = [det for det in four_digit_detections if det['in_roi']]
                four_digit_detections = filtered_4d
            
            # 4D only needs one number; pick the highest-confidence candidate after ROI filtering
            if len(four_digit_detections) > 1:
                best_4d = max(four_digit_detections, key=lambda det: det['conf'])
                numbers = [best_4d['number']]

            elif len(four_digit_detections) == 1:
                numbers = [four_digit_detections[0]['number']]
            else:
                # Fallback: OCR may read leading "A." as "4" and produce a 5-digit number
                five_digit_candidates = []
                for bbox, text, conf in results_with_boxes:
                    if conf <= CONFIDENCE_THRESHOLD:
                        continue

                    # Only consider 5-digit strings that start with 4 (e.g., 41234 -> 1234)
                    prefixed_matches = re.findall(r'\b4\d{4}\b', text)
                    if not prefixed_matches:
                        continue

                    coords = np.array(bbox)
                    centroid_y = np.mean(coords[:, 1])

                    in_roi = True
                    if y_min is not None and y_max is not None:
                        in_roi = y_min <= centroid_y <= y_max

                    if not in_roi:
                        continue

                    for match in prefixed_matches:
                        five_digit_candidates.append({
                            'original': match,
                            'number': int(match[1:]),
                            'conf': conf
                        })

                if five_digit_candidates:
                    best_5d = max(five_digit_candidates, key=lambda det: det['conf'])
                    numbers = [best_5d['number']]
                else:
                    numbers = []
        
        if not numbers:
            return {
                "status": "warning",
                "message": "No lottery numbers detected. Please try a clearer image.",
                "extracted_data": {
                    "game_type": detected_game_type,
                    "ticket_type": ticket_type,
                    "draw_date": draw_date,
                    "numbers": [],
                    "expected_number_count": expected_number_count,
                    "confidence": round(confidence, 2)
                }
            }
        
        return {
            "status": "success",
            "extracted_data": {
                "game_type": detected_game_type,
                "ticket_type": ticket_type,
                "draw_date": draw_date,
                "numbers": numbers,
                "expected_number_count": expected_number_count,
                "confidence": round(confidence, 2),
                "count": len(numbers)
            }
        }
    
    except HTTPException as e:
        raise e
    except Exception as e:
        logger.error(f"Extract error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)