"""POST /data_transformation — request models, response models, and route handler."""
from __future__ import annotations

import logging
import time
import uuid
from typing import Any

from fastapi import APIRouter, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, field_validator, model_validator

from src.modules.data_transformer import (
    TransformationError,
    apply_pipeline,
    available_operations,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["Data Transformation"])

_MAX_PIPELINE_STEPS = 20
_MAX_PAYLOAD_KEYS = 500


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------

class TransformStep(BaseModel):
    operation: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="Name of the transform operation to apply.",
    )
    params: dict[str, Any] = Field(
        default_factory=dict,
        description="Operation-specific parameters.",
    )

    @field_validator("operation")
    @classmethod
    def operation_must_be_known(cls, v: str) -> str:
        known = available_operations()
        if v not in known:
            raise ValueError(
                f"Unknown operation '{v}'. Available: {known}"
            )
        return v


class DataTransformationRequest(BaseModel):
    data: dict[str, Any] = Field(
        ...,
        description="Flat or nested JSON object to transform.",
    )
    pipeline: list[TransformStep] = Field(
        ...,
        min_length=1,
        description="Ordered list of transformation steps.",
    )
    request_id: str | None = Field(
        default=None,
        description="Optional caller-supplied correlation ID.",
    )

    @field_validator("data")
    @classmethod
    def data_size_limit(cls, v: dict) -> dict:
        if len(v) > _MAX_PAYLOAD_KEYS:
            raise ValueError(
                f"'data' exceeds the maximum of {_MAX_PAYLOAD_KEYS} top-level keys."
            )
        return v

    @model_validator(mode="after")
    def pipeline_length_limit(self) -> "DataTransformationRequest":
        if len(self.pipeline) > _MAX_PIPELINE_STEPS:
            raise ValueError(
                f"'pipeline' exceeds the maximum of {_MAX_PIPELINE_STEPS} steps."
            )
        return self


class DataTransformationResponse(BaseModel):
    request_id: str
    status: str
    result: dict[str, Any]
    steps_applied: int
    duration_ms: float


class ErrorDetail(BaseModel):
    request_id: str
    status: str
    error: str
    detail: str | None = None


# ---------------------------------------------------------------------------
# Route
# ---------------------------------------------------------------------------

@router.post(
    "/data_transformation",
    response_model=DataTransformationResponse,
    status_code=status.HTTP_200_OK,
    summary="Transform a JSON payload through a declarative pipeline.",
    responses={
        400: {"model": ErrorDetail, "description": "Validation or transformation error"},
        422: {"description": "Request body schema violation"},
        500: {"model": ErrorDetail, "description": "Unexpected server error"},
    },
)
async def data_transformation(
    body: DataTransformationRequest,
    request: Request,
) -> JSONResponse:
    """Apply a sequence of named transformations to an input JSON object.

    Each pipeline step names an operation and passes optional params.
    Steps are executed in order; the output of each step is the input
    to the next.

    **Built-in operations**:
    - ``rename_keys`` — rename top-level keys via a mapping object
    - ``filter_keys`` — keep only a specified list of keys
    - ``cast_types`` — cast field values to str / int / float / bool
    - ``add_metadata`` — inject ``_transformed_at`` timestamp and/or ``_checksum``
    - ``flatten`` — flatten one level of nested dicts with a configurable separator
    - ``regex_replace`` — apply a regex substitution to a string field
    """
    request_id = body.request_id or str(uuid.uuid4())
    client_ip = getattr(request.client, "host", "unknown") if request.client else "unknown"
    logger.info(
        "data_transformation started",
        extra={"request_id": request_id, "client_ip": client_ip, "steps": len(body.pipeline)},
    )

    t0 = time.perf_counter()

    try:
        pipeline_dicts = [
            {"operation": step.operation, "params": step.params}
            for step in body.pipeline
        ]
        result = apply_pipeline(body.data, pipeline_dicts)
    except TransformationError as exc:
        duration_ms = round((time.perf_counter() - t0) * 1000, 3)
        logger.warning(
            "data_transformation failed: %s",
            exc,
            extra={"request_id": request_id, "duration_ms": duration_ms},
        )
        return JSONResponse(
            status_code=status.HTTP_400_BAD_REQUEST,
            content=ErrorDetail(
                request_id=request_id,
                status="error",
                error="TransformationError",
                detail=str(exc),
            ).model_dump(),
        )
    except Exception as exc:  # noqa: BLE001
        duration_ms = round((time.perf_counter() - t0) * 1000, 3)
        logger.exception(
            "data_transformation unexpected error",
            extra={"request_id": request_id, "duration_ms": duration_ms},
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=ErrorDetail(
                request_id=request_id,
                status="error",
                error="InternalServerError",
                detail="An unexpected error occurred. Check server logs.",
            ).model_dump(),
        )

    duration_ms = round((time.perf_counter() - t0) * 1000, 3)
    logger.info(
        "data_transformation complete",
        extra={"request_id": request_id, "duration_ms": duration_ms},
    )
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content=DataTransformationResponse(
            request_id=request_id,
            status="success",
            result=result,
            steps_applied=len(body.pipeline),
            duration_ms=duration_ms,
        ).model_dump(),
    )
