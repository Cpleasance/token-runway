"""JSON-RPC 2.0 protocol definitions and message envelopes for MCP."""

from __future__ import annotations

import json
import sys
from typing import Any, Dict, Optional, Union

PARSE_ERROR = -32700
INVALID_REQUEST = -32600
METHOD_NOT_FOUND = -32601
INVALID_PARAMS = -32602
INTERNAL_ERROR = -32603

MCP_PROTOCOL_VERSION = "2024-11-05"


def make_response(req_id: Union[int, str, None], result: Any) -> Dict[str, Any]:
    """Construct a JSON-RPC 2.0 success response envelope."""
    return {"jsonrpc": "2.0", "id": req_id, "result": result}


def make_error(
    req_id: Union[int, str, None], code: int, message: str, data: Optional[Any] = None
) -> Dict[str, Any]:
    """Construct a JSON-RPC 2.0 error response envelope."""
    err: Dict[str, Any] = {"code": code, "message": message}
    if data is not None:
        err["data"] = data
    return {"jsonrpc": "2.0", "id": req_id, "error": err}


def write_message(msg: Dict[str, Any], out_stream=None) -> None:
    """Serialize and write a JSON-RPC message line followed by a newline."""
    stream = out_stream or sys.stdout
    line = json.dumps(msg, ensure_ascii=False)
    stream.write(line + "\n")
    stream.flush()
