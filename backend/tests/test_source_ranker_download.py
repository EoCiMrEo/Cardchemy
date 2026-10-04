"""Offline HTTP simulation of the approved public acquisition envelope."""
import hashlib
import http.client
import io
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import download_source_ranker_bundle as bundle


class Response(io.BytesIO):
    def __init__(self, body=b'', status=200, headers=None):
        super().__init__(body)
        self.status = status
        self.headers = {'Content-Length': str(len(body)), **(headers or {})}

    def getcode(self):
        return self.status


class Opener:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.requests = []

    def open(self, request, timeout):
        self.requests.append((request.full_url, dict(request.header_items()), timeout))
        response = next(self.responses)
        if isinstance(response, Exception):
            raise response
        return response


def start(tmp_path, responses, clock=lambda: 0):
    opener = Opener(responses)
    audit = bundle.Acquisition(tmp_path, opener, clock)
    audit.save()
    return audit, opener


def git_pin(data):
    return {'size': len(data), 'upstream_git_oid': hashlib.sha1(
        b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()}


def metadata(model=b'model', small=b'{}'):
    return [
        {'path': name, 'type': 'file', 'size': len(model) if name == bundle.MODEL else len(small),
         'oid': 'a' * 40,
         **({'lfs': {'oid': bundle.MODEL_SHA256, 'size': len(model)}} if name == bundle.MODEL
            else {'oid': git_pin(small)['upstream_git_oid']})}
        for name in bundle.FILES
    ]


def test_preflight_is_network_and_filesystem_free(monkeypatch, capsys):
    monkeypatch.setattr(bundle, 'Acquisition', lambda *_: pytest.fail('acquisition'))
    assert bundle.main([]) == 0
    assert json.loads(capsys.readouterr().out)['network_requests'] == 0


@pytest.mark.parametrize('url', [
    'http://huggingface.co/x', 'https://huggingface.co.evil/x',
    'https://hf.co/x', 'https://a.hf.co.evil/x',
    'https://user:pass@huggingface.co/x', 'https://huggingface.co:444/x',
])
def test_hosts_protocol_and_credentials_rejected(url):
    with pytest.raises(bundle.GuardError, match='public_host_rejected'):
        bundle.check_url(url)


def test_redirects_count_and_signed_urls_stay_out_of_ledger(tmp_path):
    audit, opener = start(tmp_path, [
        Response(status=302, headers={'Location': 'https://cdn.hf.co/a?signature=private'}),
        Response(b'ok'),
    ])
    with audit.get('https://huggingface.co/model') as response:
        assert audit.read(response, 2) == b'ok'
    assert len(opener.requests) == audit.ledger['gets'] == 2
    assert 'signature' not in audit.ledger_path.read_text()


def test_urllib_http_redirect_is_handled_manually(tmp_path):
    redirect = HTTPError('https://huggingface.co/a', 307, 'redirect',
                         {'Location': 'https://cdn.hf.co/model'}, io.BytesIO())
    audit, opener = start(tmp_path, [redirect, Response(b'ok')])
    audit.get('https://huggingface.co/a').close()
    assert len(opener.requests) == 2


def test_redirect_outside_public_hosts_never_fetched(tmp_path):
    audit, opener = start(tmp_path, [Response(status=302, headers={'Location': 'https://evil.example/a'})])
    with pytest.raises(bundle.GuardError, match='public_host_rejected'):
        audit.get('https://huggingface.co/a')
    assert len(opener.requests) == 1


def test_redirect_loop_stops_exact_get_budget(tmp_path):
    audit, opener = start(tmp_path, [Response(status=302, headers={'Location': '/a'}) for _ in range(10)])
    with pytest.raises(bundle.GuardError, match='request_budget_exhausted'):
        audit.get('https://huggingface.co/a')
    assert len(opener.requests) == audit.ledger['gets'] == 10


def test_deadline_stops_before_network(tmp_path):
    audit, opener = start(tmp_path, [])
    audit.clock = lambda: bundle.MAX_SECONDS
    with pytest.raises(bundle.GuardError, match='time_budget_exhausted'):
        audit.get('https://huggingface.co/a')
    assert not opener.requests


def test_pin_metadata_requires_every_exact_file_and_lfs_sha(tmp_path):
    audit, _ = start(tmp_path, [Response(json.dumps(metadata()).encode())])
    pins = audit.metadata()
    assert set(pins) == set(bundle.FILES)
    assert pins[bundle.MODEL]['sha256'] == bundle.MODEL_SHA256
    assert json.loads((tmp_path / 'upstream-pins.json').read_text())['revision'] == bundle.REVISION


@pytest.mark.parametrize('mutation,code', [
    (lambda rows: rows.pop(), 'manifest_incomplete'),
    (lambda rows: rows[0]['lfs'].update(oid='0' * 64), 'model_pin_mismatch'),
    (lambda rows: rows.append(rows[-1]), 'metadata_invalid'),
    (lambda rows: rows[1].update(oid='invalid'), 'small_file_pin_invalid'),
])
def test_invalid_metadata_stops_without_file_requests(tmp_path, mutation, code):
    rows = metadata()
    mutation(rows)
    audit, opener = start(tmp_path, [Response(json.dumps(rows).encode())])
    with pytest.raises(bundle.GuardError, match=code):
        audit.metadata()
    assert len(opener.requests) == 1


def test_small_file_git_object_verified_and_sha256_recorded(tmp_path):
    data = b'{"public":true}'
    audit, opener = start(tmp_path, [Response(data)])
    result = audit.file('config.json', git_pin(data))
    assert result['sha256'] == hashlib.sha256(data).hexdigest()
    assert (tmp_path / 'config.json').read_bytes() == data
    assert '/raw/' in opener.requests[0][0]


def test_hash_failure_no_retry_or_final_file(tmp_path):
    audit, opener = start(tmp_path, [Response(b'evil')])
    with pytest.raises(bundle.GuardError, match='artifact_git_hash_mismatch'):
        audit.file('config.json', git_pin(b'good'))
    assert len(opener.requests) == 1
    assert not (tmp_path / 'config.json').exists()


class Interrupted(Response):
    def __init__(self):
        super().__init__(b'pub', headers={'Content-Length': '6'})
        self.reads = 0

    def read(self, amount):
        self.reads += 1
        if self.reads == 2:
            raise URLError('signed url must never be printed')
        return super().read(amount)


def test_partial_transport_resume_preserves_prefix_and_requires_exact_range(tmp_path):
    audit, opener = start(tmp_path, [Interrupted(), Response(b'lic', 206,
        {'Content-Range': 'bytes 3-5/6'})])
    result = audit.file('config.json', git_pin(b'public'))
    assert result['sha256'] == hashlib.sha256(b'public').hexdigest()
    assert opener.requests[1][1]['Range'] == 'bytes=3-'
    assert audit.ledger['received_bytes'] == 6
    assert audit.ledger['files']['config.json']['attempts'] == 2


@pytest.mark.parametrize('response,code', [
    (Response(b'lic'), 'artifact_status_rejected'),
    (Response(b'lic', 206, {'Content-Range': 'bytes 0-2/6'}), 'range_identity_rejected'),
    (Response(b'lic', 206, {'Content-Range': 'bytes 3-5/6', 'Content-Length': '2'}), 'artifact_length_rejected'),
])
def test_resume_identity_failures_do_not_get_third_attempt(tmp_path, response, code):
    audit, opener = start(tmp_path, [Interrupted(), response])
    with pytest.raises(bundle.GuardError, match=code):
        audit.file('config.json', git_pin(b'public'))
    assert len(opener.requests) == 2
    assert (tmp_path / 'config.json.partial').read_bytes() == b'pub'


def test_two_transport_failures_end_file(tmp_path):
    audit, opener = start(tmp_path, [URLError('secret'), URLError('secret')])
    with pytest.raises(bundle.GuardError, match='transport_retry_exhausted'):
        audit.file('config.json', git_pin(b'public'))
    assert len(opener.requests) == 2


def test_preexisting_files_never_overwritten_or_requested(tmp_path):
    (tmp_path / 'config.json').write_bytes(b'keep')
    audit, opener = start(tmp_path, [])
    with pytest.raises(bundle.GuardError, match='preexisting_artifact_rejected'):
        audit.file('config.json', git_pin(b'public'))
    assert not opener.requests
    assert (tmp_path / 'config.json').read_bytes() == b'keep'


def test_consumed_ledger_cannot_restart(tmp_path):
    audit, opener = start(tmp_path, [])
    with pytest.raises(FileExistsError):
        audit.execute()
    assert not opener.requests


def test_success_full_manifest_frozen_without_importing_model(tmp_path, monkeypatch):
    model, small = b'model', b'{}'
    monkeypatch.setattr(bundle, 'MODEL_SHA256', hashlib.sha256(model).hexdigest())
    opener = Opener([Response(json.dumps(metadata(model, small)).encode()), Response(model),
                     *(Response(small) for _ in range(4))])
    audit = bundle.Acquisition(tmp_path, opener, clock=lambda: 0)
    result = audit.execute()
    assert result['status'] == 'verified'
    manifest = json.loads((tmp_path / 'manifest.json').read_text())
    assert set(manifest['files']) == set(bundle.FILES)
    assert all(pin['size'] > 0 and len(pin['sha256']) == 64 for pin in manifest['files'].values())
    assert result['gets'] == 6


def test_encoded_response_rejected_before_bytes(tmp_path):
    audit, _ = start(tmp_path, [Response(b'secret', headers={'Content-Encoding': 'gzip'})])
    with pytest.raises(bundle.GuardError, match='content_encoding_rejected'):
        audit.get('https://huggingface.co/a')
    assert audit.ledger['received_bytes'] == 0


def test_received_bytes_budget_includes_failed_transfers(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle, 'MAX_BYTES', 5)
    audit, _ = start(tmp_path, [Interrupted(), Response(b'lic', 206, {'Content-Range': 'bytes 3-5/6'})])
    with pytest.raises(bundle.GuardError, match='byte_budget_exhausted'):
        audit.file('config.json', git_pin(b'public'))
    assert audit.ledger['received_bytes'] == 5


def test_path_traversal_never_reaches_network(tmp_path):
    audit, opener = start(tmp_path, [])
    with pytest.raises(bundle.GuardError, match='artifact_name_rejected'):
        audit.file('../secret', git_pin(b'public'))
    assert not opener.requests


def test_existing_artifact_is_detected_before_metadata_request(tmp_path):
    (tmp_path / 'tokenizer.json').write_bytes(b'keep')
    opener = Opener([])
    result = bundle.Acquisition(tmp_path, opener, clock=lambda: 0).execute()
    assert result['status'] == 'preexisting_artifact_rejected'
    assert result['gets'] == 0
    assert (tmp_path / 'tokenizer.json').read_bytes() == b'keep'


class IncompleteBody(Response):
    def read(self, amount):
        raise http.client.IncompleteRead(b'pub', 3)


def test_incomplete_read_partial_is_counted_and_preserved_for_resume(tmp_path):
    audit, opener = start(tmp_path, [
        IncompleteBody(headers={'Content-Length': '6'}),
        Response(b'lic', 206, {'Content-Range': 'bytes 3-5/6'}),
    ])
    audit.file('config.json', git_pin(b'public'))
    assert audit.ledger['received_bytes'] == 6
    assert opener.requests[1][1]['Range'] == 'bytes=3-'
    assert (tmp_path / 'config.json').read_bytes() == b'public'


def test_incomplete_read_cannot_escape_received_byte_cap(tmp_path, monkeypatch):
    monkeypatch.setattr(bundle, 'MAX_BYTES', 2)
    audit, opener = start(tmp_path, [IncompleteBody(headers={'Content-Length': '6'})])
    with pytest.raises(bundle.GuardError, match='byte_budget_exhausted'):
        audit.file('config.json', git_pin(b'public'))
    assert audit.ledger['received_bytes'] == 3  # Honest receipt, including error.partial.
    assert len(opener.requests) == 1
    assert (tmp_path / 'config.json.partial').read_bytes() == b''
