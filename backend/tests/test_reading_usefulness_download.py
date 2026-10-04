"""Offline admission tests for one public Mixedbread artifact acquisition."""
from __future__ import annotations

import hashlib
import io
import json
from pathlib import Path
import sys
from urllib.error import HTTPError, URLError

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import download_reading_usefulness_bundle as bundle


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
        self.requests.append(request.full_url)
        answer = next(self.responses)
        if isinstance(answer, Exception):
            raise answer
        return answer


def git_oid(data):
    return hashlib.sha1(b'blob ' + str(len(data)).encode() + b'\0' + data).hexdigest()


def fixture():
    files = {bundle.MODEL: b'onnx', 'config.json': b'{}',
             'tokenizer.json': b'{}', 'README.md': b'license: apache-2.0',
             'LICENSE': b'Apache License\nVersion 2.0'}
    entries = []
    for name, data in files.items():
        row = {'path': name, 'type': 'file', 'size': len(data), 'oid': git_oid(data)}
        if name == bundle.MODEL:
            row['lfs'] = {'oid': hashlib.sha256(data).hexdigest(), 'size': len(data)}
        entries.append(row)
    return files, entries


def test_no_call_preflight(capsys, monkeypatch):
    monkeypatch.setattr(bundle, 'Acquisition', lambda *_: pytest.fail('network'))
    assert bundle.main([]) == 0
    assert json.loads(capsys.readouterr().out)['network_requests'] == 0


def test_required_manifest_and_graph_pin(tmp_path, monkeypatch):
    files, entries = fixture()
    monkeypatch.setattr(bundle, 'MODEL_SHA256', hashlib.sha256(files[bundle.MODEL]).hexdigest())
    opener = Opener([Response(json.dumps(entries).encode())])
    audit = bundle.Acquisition(tmp_path, opener, clock=lambda: 0)
    audit.save()
    assert set(audit.metadata()) == set(files)
    assert audit.ledger['gets'] == 1

    entries = [row for row in entries if row['path'] != 'LICENSE']
    missing = bundle.Acquisition(tmp_path / 'missing', Opener([Response(json.dumps(entries).encode())]),
                                 clock=lambda: 0)
    missing.destination.mkdir()
    missing.save()
    with pytest.raises(bundle.GuardError, match='manifest_incomplete'):
        missing.metadata()


def test_manual_redirect_and_host_budget(tmp_path):
    opener = Opener([HTTPError('https://huggingface.co/a', 302, 'redirect',
                               {'Location': 'https://cdn.hf.co/a'}, io.BytesIO()),
                     Response(b'ok')])
    audit = bundle.Acquisition(tmp_path, opener, clock=lambda: 0)
    audit.save()
    with audit.get('https://huggingface.co/a') as response:
        assert audit.read(response, 2) == b'ok'
    assert audit.ledger['gets'] == len(opener.requests) == 2
    with pytest.raises(bundle.GuardError, match='public_host_rejected'):
        bundle.check_url('https://huggingface.co.evil/a')


def test_one_retry_only_for_transport(tmp_path):
    opener = Opener([URLError('opaque'), URLError('opaque')])
    audit = bundle.Acquisition(tmp_path, opener, clock=lambda: 0)
    audit.save()
    with pytest.raises(bundle.GuardError, match='transport_retry_exhausted'):
        audit.file('config.json', {'size': 2, 'upstream_git_oid': git_oid(b'{}')})
    assert audit.ledger['gets'] == len(opener.requests) == 2


def test_complete_bundle_has_hashes_and_license(tmp_path, monkeypatch):
    files, entries = fixture()
    monkeypatch.setattr(bundle, 'MODEL_SHA256', hashlib.sha256(files[bundle.MODEL]).hexdigest())
    opener = Opener([Response(json.dumps(entries).encode()),
                     *(Response(files[name]) for name in sorted(files))])
    audit = bundle.Acquisition(tmp_path, opener, clock=lambda: 0)
    result = audit.execute()
    assert result['status'] == 'verified'
    assert result['gets'] == 1 + len(files)
    manifest = json.loads((tmp_path / 'manifest.json').read_text())
    assert set(manifest['files']) == set(files)
    assert all(manifest['files'][name]['sha256'] == hashlib.sha256(data).hexdigest()
               for name, data in files.items())


def test_license_mismatch_is_not_usable(tmp_path, monkeypatch):
    files, entries = fixture()
    files['README.md'] = b'license: other'
    next(row for row in entries if row['path'] == 'README.md')['oid'] = git_oid(files['README.md'])
    next(row for row in entries if row['path'] == 'README.md')['size'] = len(files['README.md'])
    monkeypatch.setattr(bundle, 'MODEL_SHA256', hashlib.sha256(files[bundle.MODEL]).hexdigest())
    opener = Opener([Response(json.dumps(entries).encode()),
                     *(Response(files[name]) for name in sorted(files))])
    result = bundle.Acquisition(tmp_path, opener, clock=lambda: 0).execute()
    assert result['status'] == 'license_declaration_invalid'
    assert not (tmp_path / 'manifest.json').exists()


def test_one_metadata_transport_resume_preserves_cumulative_ledger(tmp_path, monkeypatch):
    files, entries = fixture()
    monkeypatch.setattr(bundle, 'MODEL_SHA256', hashlib.sha256(files[bundle.MODEL]).hexdigest())
    first = bundle.Acquisition(tmp_path, Opener([URLError('opaque')]), clock=lambda: 0)
    assert first.execute() == {'status': 'metadata_or_transport_unavailable',
                               'gets': 1, 'received_bytes': 0}
    next_opener = Opener([Response(json.dumps(entries).encode()),
                          *(Response(files[name]) for name in sorted(files))])
    second = bundle.Acquisition(tmp_path, next_opener, clock=lambda: 0)
    result = second.resume_metadata_once()
    assert result['status'] == 'verified'
    assert result['gets'] == 2 + len(files)
    assert json.loads((tmp_path / 'acquisition-ledger.json').read_text())['metadata_retry_consumed']
    with pytest.raises(bundle.GuardError, match='resume_identity_rejected'):
        bundle.Acquisition(tmp_path, Opener([]), clock=lambda: 0).resume_metadata_once()


def test_resume_refuses_changed_state_before_get(tmp_path):
    first = bundle.Acquisition(tmp_path, Opener([URLError('opaque')]), clock=lambda: 0)
    assert first.execute()['gets'] == 1
    (tmp_path / 'stray').write_text('public')
    next_opener = Opener([])
    with pytest.raises(bundle.GuardError, match='resume_identity_rejected'):
        bundle.Acquisition(tmp_path, next_opener, clock=lambda: 0).resume_metadata_once()
    assert not next_opener.requests
