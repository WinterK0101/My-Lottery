"""
Pydantic schemas for prediction API requests and responses.
"""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class FourDPrediction(BaseModel):
    """Prediction output for 4D."""

    number: str = Field(..., description="4-digit string, e.g. '1234'")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")
    reasoning: str = Field(..., description="Short explanation of prediction basis")


class TotoPrediction(BaseModel):
    """Prediction output for TOTO System 12."""

    numbers: List[int] = Field(..., description="12 numbers for System 12")
    primary: List[int] = Field(..., description="Primary 6 numbers")
    supplementary: List[int] = Field(..., description="Supplementary 6 numbers")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")
    reasoning: str = Field(..., description="Short explanation of prediction basis")


class ModelPrediction(BaseModel):
    """One predictive model output block."""

    model_name: str
    model_key: str
    description: str
    four_d: FourDPrediction
    toto: TotoPrediction
    methodology: str
    assumptions: str
    validation: str
    confidence_note: str


class PredictionResponse(BaseModel):
    """Prediction API response payload."""

    disclaimer: str
    models: List[ModelPrediction]
    data_points_used: int


class PredictionGenerateRequest(BaseModel):
    """Input options for prediction generation."""

    limit: int = Field(
        default=50,
        ge=1,
        le=500,
        description="Draw history rows to load per game type when results are fetched from Supabase",
    )
    results: Optional[List[Dict[str, Any]]] = Field(
        default=None,
        description="Optional legacy payload. If provided, this data is used directly.",
    )
