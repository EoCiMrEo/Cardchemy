"""Credential-free transport and admission checks for the public continuation."""

from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import sys

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import call_public_source_id_multipdf_35_lite_continuation_v1 as caller  # noqa: E402
from evaluate_source_id_multipdf_35_lite import (  # noqa: E402
    build_pilot_request,
)


def _wire() -> dict:
    return build_pilot_request("How is the public method defined?", [{
        "id": "S01", "page": 2,
        "page_text": "The public method has a concise definition.",
        "cue": "a concise definition",
    }])


def _args(tmp_path: Path) -> argparse.Namespace:
    return argparse.Namespace(
        prior_dir=tmp_path / "prior", packet_dir=tmp_path / "packet",
        labels_path=tmp_path / "labels" / "frozen-labels.json",
        old_approval_path=tmp_path / "old" / "approval.json",
        new_approval_path=None, new_approval_sha256=None,
        output=tmp_path / "fresh-output", ack_live=False, execute=False,
    )


def test_preapproval_checks_prior_and_output_without_key_or_claim(
    tmp_path, monkeypatch,
):
    args = _args(tmp_path)
    called = []

    def prior(*_args):
        called.append("prior")
        return ({"requests": [{} for _ in range(48)]}, {}, {
            "prior_accepted_groups": 10,
            "prior_uncertain_group_number": 11,
            "source_packet_sha256": "a" * 64,
        })

    monkeypatch.setattr(caller.continuation, "validate_prior", prior)
    monkeypatch.setattr(caller, "_output_preflight",
                        lambda *_: called.append("output"))
    monkeypatch.setattr(caller.continuation, "validate_approval",
                        lambda *_: pytest.fail("approval read during preapproval"))
    monkeypatch.setattr(caller, "_source_judge_key",
                        lambda: pytest.fail("key read during preapproval"))
    result = caller._admit(args, approved=False)
    assert called == ["prior", "output"]
    assert result["authorization_pending"] is True
    assert result["prior_accepted_groups"] == 10
    assert result["prior_uncertain_group_number"] == 11
    assert not args.output.exists()

    args.new_approval_path = tmp_path / "unapproved.json"
    with pytest.raises(caller.PilotFailure, match="preapproval_arguments_invalid"):
        caller._admit(args, approved=False)


def test_pending_authorization_cannot_read_key_or_claim(tmp_path, monkeypatch):
    monkeypatch.setattr(caller.continuation, "AUTHORIZATION_ID",
                        "PENDING_SEPARATE_OPERATOR_APPROVAL")
    args = _args(tmp_path)
    args.new_approval_path = tmp_path / "approval.json"
    args.new_approval_sha256 = "b" * 64
    monkeypatch.setattr(caller.continuation, "validate_prior",
                        lambda *_: ({"requests": []}, {}, {
                            "prior_accepted_groups": 10,
                            "prior_uncertain_group_number": 11,
                            "source_packet_sha256": "a" * 64,
                        }))
    monkeypatch.setattr(caller, "_output_preflight", lambda *_: None)
    monkeypatch.setattr(caller, "_source_judge_key",
                        lambda: pytest.fail("key read before approval"))
    with pytest.raises(caller.PilotFailure,
                       match="separate_operator_approval_required"):
        caller._admit(args, approved=True)
    assert not args.output.exists()


def test_execute_requires_explicit_flag_before_any_preflight(tmp_path, monkeypatch):
    args = _args(tmp_path)
    monkeypatch.setattr(caller, "_admit",
                        lambda *_args, **_kwargs: pytest.fail("admitted without flag"))
    with pytest.raises(caller.PilotFailure,
                       match="explicit_live_execution_required"):
        asyncio.run(caller._execute(args))


@pytest.mark.asyncio
async def test_one_public_post_exact_body_no_retry_or_redirect():
    seen = []

    def server(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, json={"candidates": []})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(server), follow_redirects=False,
    ) as client:
        response = await caller._post_public_wire(client, "fake-key", _wire())
    assert len(seen) == 1
    request = seen[0]
    assert request.method == "POST"
    assert str(request.url) == caller.ENDPOINT
    assert request.headers["x-goog-api-key"] == "fake-key"
    body = json.loads(request.content)
    assert body["store"] is False
    assert body["generationConfig"]["thinkingConfig"] == {
        "thinkingLevel": "low",
    }
    assert body["generationConfig"]["maxOutputTokens"] == 1024
    assert "How is the public method defined?" in body["contents"][0]["parts"][0]["text"]
    assert "prior_for_local_context_only" not in request.content.decode()
    assert response.status_code == 200
    assert json.loads(response.content) == {"candidates": []}


@pytest.mark.asyncio
async def test_success_response_bytes_are_bounded():
    def server(_request):
        return httpx.Response(200, content=b"x" * (caller.MAX_HTTP_RESPONSE_BYTES + 1))

    async with httpx.AsyncClient(transport=httpx.MockTransport(server)) as client:
        with pytest.raises(caller.PilotFailure,
                           match="provider_response_oversize"):
            await caller._post_public_wire(client, "fake-key", _wire())


@pytest.mark.asyncio
async def test_error_body_is_never_consumed_and_429_has_no_retry():
    class Unreadable(httpx.AsyncByteStream):
        async def __aiter__(self):
            raise AssertionError("error body was read")
            yield b"unreachable"  # pragma: no cover

        async def aclose(self):
            pass

    calls = []

    def server(request):
        calls.append(request)
        return httpx.Response(429, stream=Unreadable())

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(server), follow_redirects=False,
    ) as client:
        response = await caller._post_public_wire(client, "fake-key", _wire())
    assert len(calls) == 1
    assert response.status_code == 429
    assert response.content == b""


@pytest.mark.asyncio
async def test_redirect_is_returned_without_second_request():
    calls = []

    def server(request):
        calls.append(request)
        return httpx.Response(302, headers={"location": "https://example.invalid/"})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(server), follow_redirects=False,
    ) as client:
        response = await caller._post_public_wire(client, "fake-key", _wire())
    assert len(calls) == 1
    assert response.status_code == 302
    assert response.content == b""
