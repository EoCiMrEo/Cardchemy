"""One approved public Mixedbread acquisition; no application imports or inference.

Without --execute-approved this is a read-only, network-free preflight. A durable
ledger consumes the authorization before the first GET, including redirects.
"""
from __future__ import annotations

import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

REPOSITORY = 'mixedbread-ai/mxbai-rerank-xsmall-v1'
REVISION = 'd1ba0a474aeed7c9fa96c3f57b128277580c5fae'
MODEL = 'onnx/model_quantized.onnx'
MODEL_SHA256 = '15ef19a6de90be7d52b627f2c784107bd806e64826450f41fb75fa4f0179ab30'
REQUIRED_FILES = frozenset({MODEL, 'config.json', 'tokenizer.json', 'README.md', 'LICENSE'})
OPTIONAL_FILES = frozenset({'tokenizer_config.json', 'special_tokens_map.json'})
FILES = REQUIRED_FILES | OPTIONAL_FILES
DESTINATION = Path(__file__).resolve().parents[1] / 'artifacts' / 'reading-usefulness-audit-20260928'
MAX_GETS = 12
MAX_BYTES = 160 * 1024**2
MAX_SECONDS = 1800
METADATA_MAX_BYTES = 256 * 1024
SMALL_MAX_BYTES = 16 * 1024**2
CHUNK_BYTES = 1024**2
TRANSPORT_ERRORS = (URLError, TimeoutError, socket.timeout, ConnectionError, http.client.IncompleteRead)


class GuardError(Exception):
    """Only fixed safe codes cross the command-line boundary."""


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def check_url(url: str) -> None:
    parts = urlsplit(url)
    host = parts.hostname or ''
    if (parts.scheme != 'https' or parts.username or parts.password
            or parts.port not in (None, 443)
            or not (host == 'huggingface.co' or host.endswith('.hf.co'))):
        raise GuardError('public_host_rejected')


def sha256_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(CHUNK_BYTES), b''):
            result.update(block)
    return result.hexdigest()


def atomic_json(path: Path, value: dict) -> None:
    staging = path.with_name(path.name + '.local-write')
    with staging.open('w', encoding='utf-8') as stream:
        json.dump(value, stream, sort_keys=True, indent=2)
        stream.write('\n')
        stream.flush()
        os.fsync(stream.fileno())
    staging.replace(path)


class Acquisition:
    def __init__(self, destination: Path, opener=None, clock=time.monotonic):
        self.destination = destination
        self.opener = opener or build_opener(NoRedirect())
        self.clock = clock
        self.deadline = clock() + MAX_SECONDS
        self.ledger = {'schema': 'reading_usefulness_download_v1', 'repository': REPOSITORY,
                       'revision': REVISION, 'gets': 0, 'received_bytes': 0,
                       'status': 'consumed', 'files': {}}
        self.ledger_path = destination / 'acquisition-ledger.json'

    def save(self):
        atomic_json(self.ledger_path, self.ledger)

    def budget(self):
        if self.clock() >= self.deadline:
            raise GuardError('time_budget_exhausted')

    def get(self, url, headers=None):
        """Manual redirects count as GETs; no implicit adapter retry."""
        while True:
            self.budget()
            check_url(url)
            if self.ledger['gets'] >= MAX_GETS:
                raise GuardError('request_budget_exhausted')
            self.ledger['gets'] += 1
            self.save()
            try:
                response = self.opener.open(Request(url, headers={
                    'Accept-Encoding': 'identity', 'User-Agent': 'Cardchemy-public-artifact-audit/1',
                    **(headers or {}),
                }), timeout=min(120, max(1, self.deadline - self.clock())))
            except HTTPError as error:
                if error.code in (301, 302, 303, 307, 308):
                    location = error.headers.get('Location')
                    error.close()
                    if not location:
                        raise GuardError('redirect_location_missing') from None
                    url = urljoin(url, location)
                    continue
                error.close()
                raise GuardError('http_status_rejected') from None
            if response.getcode() in (301, 302, 303, 307, 308):
                location = response.headers.get('Location')
                response.close()
                if not location:
                    raise GuardError('redirect_location_missing')
                url = urljoin(url, location)
                continue
            if response.headers.get('Content-Encoding', 'identity').lower() != 'identity':
                response.close()
                raise GuardError('content_encoding_rejected')
            return response

    def read(self, response, amount):
        self.budget()
        remaining = MAX_BYTES - self.ledger['received_bytes']
        if remaining <= 0:
            raise GuardError('byte_budget_exhausted')
        amount = min(amount, remaining)
        # urllib's socket timeout is per blocking operation. Reduce it as the
        # overall deadline approaches, instead of admitting a fresh 120 seconds.
        socket_object = getattr(getattr(getattr(response, 'fp', None), 'raw', None), '_sock', None)
        if socket_object is not None:
            socket_object.settimeout(min(120, max(0.001, self.deadline - self.clock())))
        incomplete = None
        try:
            block = response.read(amount)
        except http.client.IncompleteRead as error:
            block = error.partial
            incomplete = error
        self.ledger['received_bytes'] += len(block)
        self.save()
        self.budget()
        if len(block) > amount or self.ledger['received_bytes'] > MAX_BYTES:
            raise GuardError('byte_budget_exhausted')
        if incomplete is not None:
            raise incomplete
        return block

    def metadata(self):
        url = f'https://huggingface.co/api/models/{REPOSITORY}/tree/{REVISION}?recursive=true&expand=false'
        with self.get(url) as response:
            if response.getcode() != 200:
                raise GuardError('metadata_status_rejected')
            raw = self.read(response, METADATA_MAX_BYTES + 1)
            if len(raw) > METADATA_MAX_BYTES:
                raise GuardError('metadata_budget_exhausted')
            # No pagination can silently leave a manifest incomplete.
            if response.headers.get('Link'):
                raise GuardError('metadata_pagination_rejected')
        try:
            entries = json.loads(raw)
        except (ValueError, UnicodeDecodeError):
            raise GuardError('metadata_invalid') from None
        pins = {}
        if not isinstance(entries, list):
            raise GuardError('metadata_invalid')
        for entry in entries:
            if not isinstance(entry, dict) or entry.get('path') not in FILES:
                continue
            name = entry['path']
            if name in pins or entry.get('type') != 'file':
                raise GuardError('metadata_invalid')
            size, oid = entry.get('size'), entry.get('oid')
            if not isinstance(size, int) or isinstance(size, bool) or size <= 0:
                raise GuardError('metadata_invalid')
            if name == MODEL:
                lfs = entry.get('lfs', {})
                if lfs.get('oid') != MODEL_SHA256 or lfs.get('size') != size:
                    raise GuardError('model_pin_mismatch')
                pins[name] = {'size': size, 'sha256': MODEL_SHA256, 'upstream_git_oid': oid,
                              'upstream_lfs_sha256': MODEL_SHA256}
            else:
                if size > SMALL_MAX_BYTES or not isinstance(oid, str) or not re.fullmatch('[0-9a-f]{40}', oid):
                    raise GuardError('small_file_pin_invalid')
                pins[name] = {'size': size, 'upstream_git_oid': oid}
        if (not REQUIRED_FILES <= set(pins) or not set(pins) <= FILES
                or sum(pin['size'] for pin in pins.values()) > MAX_BYTES):
            raise GuardError('manifest_incomplete_or_over_budget')
        atomic_json(self.destination / 'upstream-pins.json', {
            'repository': REPOSITORY, 'revision': REVISION, 'files': pins,
            'metadata_sha256': hashlib.sha256(raw).hexdigest()})
        return pins

    def file(self, name, pin):
        if name not in FILES:
            raise GuardError('artifact_name_rejected')
        target = self.destination / name
        target.parent.mkdir(parents=True, exist_ok=True)
        partial = target.with_name(target.name + '.partial')
        if target.exists() or partial.exists() or target.is_symlink():
            raise GuardError('preexisting_artifact_rejected')
        state = {'attempts': 0, 'bytes': 0, 'prefix_sha256': hashlib.sha256(b'').hexdigest()}
        self.ledger['files'][name] = state
        self.save()
        url = (f'https://huggingface.co/{REPOSITORY}/'
               f'{"resolve" if name == MODEL else "raw"}/{REVISION}/{name}')
        for attempt in range(2):
            state['attempts'] += 1
            self.save()
            offset = state['bytes']
            if offset and (partial.stat().st_size != offset or sha256_file(partial) != state['prefix_sha256']):
                raise GuardError('partial_identity_changed')
            headers = {'Range': f'bytes={offset}-'} if offset else {}
            try:
                with self.get(url, headers) as response:
                    expected_status = 206 if offset else 200
                    if response.getcode() != expected_status:
                        raise GuardError('artifact_status_rejected')
                    if offset and response.headers.get('Content-Range') != f'bytes {offset}-{pin["size"] - 1}/{pin["size"]}':
                        raise GuardError('range_identity_rejected')
                    if response.headers.get('Content-Length') != str(pin['size'] - offset):
                        raise GuardError('artifact_length_rejected')
                    with partial.open('ab' if partial.exists() else 'xb') as stream:
                        while state['bytes'] < pin['size']:
                            try:
                                block = self.read(response, min(CHUNK_BYTES, pin['size'] - state['bytes']))
                            except http.client.IncompleteRead as error:
                                # HTTPResponse has already received these bytes.
                                # read() accounted for them before propagating;
                                # retain the validated-length prefix for one resume.
                                stream.write(error.partial)
                                stream.flush()
                                os.fsync(stream.fileno())
                                state['bytes'] += len(error.partial)
                                raise
                            if not block:
                                raise ConnectionError('incomplete_transfer')
                            stream.write(block)
                            stream.flush()
                            os.fsync(stream.fileno())
                            state['bytes'] += len(block)
                        if self.read(response, 1):
                            raise GuardError('artifact_overlength')
                break
            except TRANSPORT_ERRORS:
                # Only transport failures consume the one retry/resume. Metadata,
                # status, range and integrity errors never receive a retry.
                state['prefix_sha256'] = sha256_file(partial) if partial.exists() else hashlib.sha256(b'').hexdigest()
                self.save()
                if attempt == 1 or state['bytes'] == pin['size']:
                    raise GuardError('transport_retry_exhausted') from None
        if partial.stat().st_size != pin['size']:
            raise GuardError('artifact_size_mismatch')
        digest = sha256_file(partial)
        self.budget()
        if name == MODEL:
            if digest != MODEL_SHA256:
                raise GuardError('artifact_hash_mismatch')
        else:
            git_digest = hashlib.sha1(b'blob ' + str(pin['size']).encode('ascii') + b'\0' + partial.read_bytes()).hexdigest()
            if git_digest != pin['upstream_git_oid']:
                raise GuardError('artifact_git_hash_mismatch')
        pin = {**pin, 'sha256': digest}
        state['prefix_sha256'] = digest
        state['verified'] = True
        self.save()
        partial.replace(target)  # A local finalization failure must never repeat GETs.
        return pin

    def execute(self):
        if any(parent.is_symlink() for parent in (self.destination, *self.destination.parents)):
            raise GuardError('destination_symlink_rejected')
        self.destination.mkdir(parents=True, exist_ok=True)
        # Exclusive marker survives failure/interruption: the CLI cannot restart
        # an already consumed approval or regenerate its limits.
        with self.ledger_path.open('x', encoding='utf-8') as stream:
            json.dump(self.ledger, stream)
        return self.finish()

    def resume_metadata_once(self):
        """Resume this same consumed ledger after a zero-byte metadata transport failure.

        The failed first GET may have reached the host. This consumes its sole
        metadata retry before a second GET and never resets cumulative budgets.
        """
        if (any(parent.is_symlink() for parent in (self.destination, *self.destination.parents))
                or self.ledger_path.is_symlink() or not self.ledger_path.is_file()):
            raise GuardError('resume_identity_rejected')
        try:
            prior = json.loads(self.ledger_path.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            raise GuardError('resume_identity_rejected') from None
        expected = {'schema': 'reading_usefulness_download_v1', 'repository': REPOSITORY,
                    'revision': REVISION, 'gets': 1, 'received_bytes': 0,
                    'status': 'metadata_or_transport_unavailable', 'files': {}}
        if (prior != expected or set(self.destination.iterdir()) != {self.ledger_path}
                or self.clock() >= self.deadline):
            raise GuardError('resume_identity_rejected')
        # The initial attempt and receipt were both recorded in this ledger.
        # Refuse a delayed retry; this intentionally errs on the side of stopping.
        elapsed_since_failure = time.time() - self.ledger_path.stat().st_mtime
        if not 0 <= elapsed_since_failure < MAX_SECONDS:
            raise GuardError('resume_time_rejected')
        self.deadline = self.clock() + (MAX_SECONDS - elapsed_since_failure)
        self.ledger = prior
        self.ledger['metadata_retry_consumed'] = True
        self.ledger['status'] = 'metadata_retry_consumed'
        self.save()
        return self.finish()

    def finish(self):
        try:
            for name in FILES:
                target = self.destination / name
                if (target.exists() or target.is_symlink()
                        or target.with_name(target.name + '.partial').exists()
                        or any(parent.is_symlink() for parent in target.parents)):
                    raise GuardError('preexisting_artifact_rejected')
            pins = self.metadata()
            verified = {name: self.file(name, pins[name]) for name in sorted(pins)}
            license_text = (self.destination / 'LICENSE').read_text(encoding='utf-8')
            card_text = (self.destination / 'README.md').read_text(encoding='utf-8')
            if ('Apache License' not in license_text or 'Version 2.0' not in license_text
                    or 'apache-2.0' not in card_text.lower()):
                raise GuardError('license_declaration_invalid')
            atomic_json(self.destination / 'manifest.json', {
                'schema': 'reading_usefulness_bundle_v1', 'repository': REPOSITORY,
                'revision': REVISION, 'files': verified})
            self.ledger['status'] = 'verified'
        except GuardError as error:
            self.ledger['status'] = str(error)
        except TRANSPORT_ERRORS:
            self.ledger['status'] = 'metadata_or_transport_unavailable'
        except (OSError, ValueError, KeyError, TypeError):
            self.ledger['status'] = 'local_or_manifest_unavailable'
        self.save()
        return {key: self.ledger[key] for key in ('status', 'gets', 'received_bytes')}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-approved', action='store_true')
    parser.add_argument('--resume-metadata-once', action='store_true')
    args = parser.parse_args(argv)
    if args.execute_approved and args.resume_metadata_once:
        parser.error('choose one acquisition mode')
    if not args.execute_approved and not args.resume_metadata_once:
        result = {'status': 'preflight_only', 'repository': REPOSITORY, 'revision': REVISION,
                  'required_file_count': len(REQUIRED_FILES),
                  'optional_file_count': len(OPTIONAL_FILES),
                  'max_gets': MAX_GETS, 'max_bytes': MAX_BYTES,
                  'max_seconds': MAX_SECONDS, 'network_requests': 0}
    else:
        try:
            acquisition = Acquisition(DESTINATION)
            result = (acquisition.resume_metadata_once() if args.resume_metadata_once
                      else acquisition.execute())
        except FileExistsError:
            result = {'status': 'approval_already_consumed', 'network_requests': 0}
        except OSError:
            result = {'status': 'local_unavailable', 'network_requests': 0}
        except GuardError as error:
            result = {'status': str(error), 'network_requests': 0}
    print(json.dumps(result, sort_keys=True))
    return 0 if result['status'] in ('preflight_only', 'verified') else 1


if __name__ == '__main__':
    raise SystemExit(main())
