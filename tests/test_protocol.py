import json
import io
from token_runway.server.protocol import (
    INTERNAL_ERROR,
    INVALID_REQUEST,
    make_error,
    make_response,
    write_message,
)


def test_make_response():
    resp = make_response(1, {"ok": True})
    assert resp["jsonrpc"] == "2.0"
    assert resp["id"] == 1
    assert resp["result"] == {"ok": True}


def test_make_error():
    err = make_error(2, INVALID_REQUEST, "Bad request", data={"detail": "foo"})
    assert err["jsonrpc"] == "2.0"
    assert err["id"] == 2
    assert err["error"]["code"] == INVALID_REQUEST
    assert err["error"]["message"] == "Bad request"
    assert err["error"]["data"] == {"detail": "foo"}


def test_write_message():
    buf = io.StringIO()
    msg = {"jsonrpc": "2.0", "id": 10, "result": "hello"}
    write_message(msg, buf)
    buf.seek(0)
    line = buf.read()
    assert line.endswith("\n")
    assert json.loads(line) == msg
