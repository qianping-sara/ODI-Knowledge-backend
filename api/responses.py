from __future__ import annotations

from fastapi.responses import JSONResponse


def success(data: object | None = None, message: str | None = None) -> dict[str, object]:
    body: dict[str, object] = {"code": 200}
    if message:
        body["message"] = message
    if data is not None:
        body["data"] = data
    return body


def error(code: int, message: str, status_code: int | None = None) -> JSONResponse:
    return JSONResponse(status_code=status_code or code, content={"code": code, "message": message})
