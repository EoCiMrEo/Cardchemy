"""Public bundle guards, without downloading or importing application settings."""
import hashlib
import io
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'scripts'))
import download_local_relation_4b as download


def test_exact_frozen_public_manifest_and_budget():
    values = download.manifest()
    assert sum(size for size, _digest in values['PINS'].values()) == 2_897_393_599
    assert set(values['PINS']) == download.PUBLIC_FILES
    assert all(len(digest) == 64 and size > 0 for size, digest in values['PINS'].values())
    assert download.MAX_BYTES == 3 * 1024**3
    assert download.MAX_SECONDS == 1800


def test_exact_public_tree_url_mapping_rejects_unexpected_names():
    values = download.manifest()
    base = (f"https://huggingface.co/{values['REPOSITORY']}/resolve/"
            f"{values['REVISION']}/")
    assert download.public_artifact_url(values, 'README.md') == base + 'README.md'
    for name in download.EXPORT_FILES:
        assert (download.public_artifact_url(values, name)
                == base + values['REPOSITORY_DIRECTORY'] + '/' + name)
    for name in ('unexpected', '../README.md', 'README.md/', 'onnxruntime/README.md'):
        with pytest.raises(ValueError, match='download_manifest_invalid'):
            download.public_artifact_url(values, name)


def test_no_authorization_never_opens_network_or_creates_directory(monkeypatch):
    monkeypatch.delenv('CARDCH_PUBLIC_4B_DOWNLOAD_APPROVED', raising=False)
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    monkeypatch.setattr(download, 'check_destination', lambda: pytest.fail('filesystem'))
    assert download.download() == {'status': 'download_not_authorized', 'artifact_requests': 0}


def test_content_verification_and_mismatch(tmp_path):
    path = tmp_path / 'model'
    path.write_bytes(b'public')
    digest = hashlib.sha256(b'public').hexdigest()
    assert download.verify_file(path, 6, digest)
    assert not download.verify_file(path, 7, digest)
    assert not download.verify_file(path, 6, '0' * 64)


def fake_download(monkeypatch, tmp_path):
    values = download.manifest()
    values['PINS'] = {'model.onnx': (6, hashlib.sha256(b'public').hexdigest())}
    monkeypatch.setenv('CARDCH_PUBLIC_4B_DOWNLOAD_APPROVED', 'ONE_PINNED_PUBLIC_BUNDLE_NO_RETRY')
    monkeypatch.setattr(download, 'manifest', lambda: values)
    monkeypatch.setattr(download, 'check_destination', lambda: tmp_path)
    return values


def test_existing_mismatch_stops_without_overwrite_or_network(monkeypatch, tmp_path):
    fake_download(monkeypatch, tmp_path)
    path = tmp_path / 'model.onnx'
    path.write_bytes(b'original')
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    result = download.download()
    assert result['status'] == 'download_unavailable'
    assert result['artifact_requests'] == 0
    assert path.read_bytes() == b'original'


def test_streamed_download_verifies_then_renames(monkeypatch, tmp_path, capsys):
    fake_download(monkeypatch, tmp_path)
    class Response(io.BytesIO):
        status = 200
        headers = {'Content-Length': '6'}
    calls = []
    def open_url(request, **kwargs):
        calls.append((request, kwargs))
        return Response(b'public')
    monkeypatch.setattr(download, 'urlopen', open_url)
    result = download.download()
    assert result['status'] == 'download_completed'
    assert result['artifact_requests'] == 1
    assert (tmp_path / 'model.onnx').read_bytes() == b'public'
    assert not (tmp_path / 'model.onnx.part').exists()
    assert calls[0][0].full_url == download.public_artifact_url(download.manifest(), 'model.onnx')
    assert calls[0][1]['timeout'] <= 60
    assert 'https://' not in capsys.readouterr().out


def test_transport_failure_never_retries_or_emits_exception(monkeypatch, tmp_path, capsys):
    fake_download(monkeypatch, tmp_path)
    calls = []
    def fail(*_args, **_kwargs):
        calls.append(1)
        raise OSError('private signed redirect URL')
    monkeypatch.setattr(download, 'urlopen', fail)
    result = download.download()
    assert result['status'] == 'download_unavailable'
    assert result['artifact_requests'] == 1
    assert len(calls) == 1
    assert 'private' not in repr(result) + capsys.readouterr().out


def test_default_refuses_unverified_partial_without_network(monkeypatch, tmp_path):
    fake_download(monkeypatch, tmp_path)
    (tmp_path / 'model.onnx.part').write_bytes(b'pub')
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    assert download.download()['artifact_requests'] == 0


def test_deliberate_range_continuation_hashes_full_file(monkeypatch, tmp_path):
    fake_download(monkeypatch, tmp_path)
    (tmp_path / 'model.onnx.part').write_bytes(b'pub')
    class Response(io.BytesIO):
        status = 206
        headers = {'Content-Length': '3', 'Content-Range': 'bytes 3-5/6'}
    calls = []
    def open_url(request, **kwargs):
        assert request.get_header('Range') == 'bytes=3-'
        calls.append(1)
        return Response(b'lic')
    monkeypatch.setattr(download, 'urlopen', open_url)
    result = download.download(resume_public_partial=True)
    assert result['status'] == 'download_completed' and len(calls) == 1
    assert (tmp_path / 'model.onnx').read_bytes() == b'public'
    assert download.MAX_RESUME_SECONDS == 7200


@pytest.mark.parametrize('status,content_range', [(200, 'bytes 3-5/6'), (206, 'bytes 0-2/6'), (206, None)])
def test_range_must_match_before_partial_mutation(monkeypatch, tmp_path, status, content_range):
    fake_download(monkeypatch, tmp_path)
    partial = tmp_path / 'model.onnx.part'
    partial.write_bytes(b'pub')
    class Response(io.BytesIO):
        headers = {'Content-Length': '3', 'Content-Range': content_range}
    response = Response(b'lic')
    response.status = status
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: response)
    result = download.download(resume_public_partial=True)
    assert result['status'] == 'download_unavailable'
    assert partial.read_bytes() == b'pub'
    assert not (tmp_path / 'model.onnx').exists()


def test_complete_partial_needs_full_digest_before_finalization(monkeypatch, tmp_path):
    fake_download(monkeypatch, tmp_path)
    partial = tmp_path / 'model.onnx.part'
    partial.write_bytes(b'wrong!')
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    result = download.download(resume_public_partial=True)
    assert result['status'] == 'download_unavailable' and result['artifact_requests'] == 0
    assert partial.read_bytes() == b'wrong!' and not (tmp_path / 'model.onnx').exists()


def test_compressed_range_never_appends(monkeypatch, tmp_path):
    fake_download(monkeypatch, tmp_path)
    partial = tmp_path / 'model.onnx.part'
    partial.write_bytes(b'pub')
    class Response(io.BytesIO):
        status = 206
        headers = {'Content-Length': '3', 'Content-Range': 'bytes 3-5/6', 'Content-Encoding': 'gzip'}
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: Response(b'lic'))
    assert download.download(resume_public_partial=True)['status'] == 'download_unavailable'
    assert partial.read_bytes() == b'pub'


def test_replaced_partial_identity_never_appends(monkeypatch, tmp_path):
    fake_download(monkeypatch, tmp_path)
    partial = tmp_path / 'model.onnx.part'
    partial.write_bytes(b'pub')
    class Response(io.BytesIO):
        status = 206
        headers = {'Content-Length': '3', 'Content-Range': 'bytes 3-5/6'}
    def open_url(*_args, **_kwargs):
        partial.rename(tmp_path / 'original')
        partial.write_bytes(b'bad')
        return Response(b'lic')
    monkeypatch.setattr(download, 'urlopen', open_url)
    assert download.download(resume_public_partial=True)['status'] == 'download_unavailable'
    assert partial.read_bytes() == b'bad'
    assert (tmp_path / 'original').read_bytes() == b'pub'


def test_prefix_mutation_cannot_pass_incremental_hash(monkeypatch, tmp_path):
    fake_download(monkeypatch, tmp_path)
    partial = tmp_path / 'model.onnx.part'
    partial.write_bytes(b'pub')
    class Response(io.BytesIO):
        status = 206
        headers = {'Content-Length': '3', 'Content-Range': 'bytes 3-5/6'}
    def open_url(*_args, **_kwargs):
        with partial.open('r+b') as changed:
            changed.write(b'bad')
        return Response(b'lic')
    monkeypatch.setattr(download, 'urlopen', open_url)
    assert download.download(resume_public_partial=True)['status'] == 'download_unavailable'
    assert not (tmp_path / 'model.onnx').exists()


def test_manual_continuation_is_single_use(monkeypatch, tmp_path):
    fake_download(monkeypatch, tmp_path)
    (tmp_path / '.range-continuation-used').write_text('already used', encoding='ascii')
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    assert download.download(resume_public_partial=True)['artifact_requests'] == 0


def test_second_continuation_requires_separate_process_opt_in(monkeypatch, tmp_path):
    fake_download(monkeypatch, tmp_path)
    (tmp_path / '.range-continuation-used').write_text('first was used', encoding='ascii')
    (tmp_path / 'model.onnx.part').write_bytes(b'pub')
    monkeypatch.delenv('CARDCH_PUBLIC_4B_SECOND_CONTINUATION_APPROVED', raising=False)
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    result = download.download(resume_public_partial=True, approved_second_continuation=True)
    assert result['status'] == 'download_not_authorized'
    assert not (tmp_path / '.range-continuation-2-used').exists()


def test_second_continuation_keeps_both_markers_and_final_sha(monkeypatch, tmp_path):
    fake_download(monkeypatch, tmp_path)
    first = tmp_path / '.range-continuation-used'
    first.write_text('first was used', encoding='ascii')
    (tmp_path / 'model.onnx.part').write_bytes(b'pub')
    monkeypatch.setenv('CARDCH_PUBLIC_4B_SECOND_CONTINUATION_APPROVED', 'ONE_MORE_PINNED_RANGE_NO_RETRY')
    class Response(io.BytesIO):
        status = 206
        headers = {'Content-Length': '3', 'Content-Range': 'bytes 3-5/6'}
    calls = []
    def open_url(request, **_kwargs):
        assert request.get_header('Range') == 'bytes=3-'
        calls.append(1)
        return Response(b'lic')
    monkeypatch.setattr(download, 'urlopen', open_url)
    result = download.download(resume_public_partial=True, approved_second_continuation=True)
    assert result['status'] == 'download_completed' and result['artifact_requests'] == 1
    assert (tmp_path / 'model.onnx').read_bytes() == b'public'
    assert first.read_text(encoding='ascii') == 'first was used'
    assert (tmp_path / '.range-continuation-2-used').is_file()
    assert len(calls) == 1
    assert download.download(resume_public_partial=True, approved_second_continuation=True)['status'] == 'download_unavailable'
    assert len(calls) == 1


def test_second_continuation_refuses_missing_first_marker(monkeypatch, tmp_path):
    fake_download(monkeypatch, tmp_path)
    (tmp_path / 'model.onnx.part').write_bytes(b'pub')
    monkeypatch.setenv('CARDCH_PUBLIC_4B_SECOND_CONTINUATION_APPROVED', 'ONE_MORE_PINNED_RANGE_NO_RETRY')
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    result = download.download(resume_public_partial=True, approved_second_continuation=True)
    assert result['status'] == 'download_unavailable' and result['artifact_requests'] == 0
    assert not (tmp_path / '.range-continuation-2-used').exists()


def fake_segmented(monkeypatch, tmp_path):
    values = download.manifest()
    values['PINS'] = {
        'model.onnx': (5, hashlib.sha256(b'graph').hexdigest()),
        'model.onnx.data': (6, hashlib.sha256(b'public').hexdigest()),
        'tokenizer.json': (3, hashlib.sha256(b'tok').hexdigest()),
    }
    monkeypatch.setattr(download, 'manifest', lambda: values)
    monkeypatch.setattr(download, 'check_destination', lambda: tmp_path)
    monkeypatch.setattr(download, 'SEGMENTED_DATA_OFFSET', 3)
    monkeypatch.setattr(download, 'SEGMENTED_TRANSFER_BYTES', 6)
    monkeypatch.setattr(download, 'SEGMENT_BYTES', 2)
    monkeypatch.setenv('CARDCH_PUBLIC_4B_DOWNLOAD_APPROVED', 'ONE_PINNED_PUBLIC_BUNDLE_NO_RETRY')
    monkeypatch.setenv('CARDCH_PUBLIC_4B_SEGMENTED_CONTINUATION_APPROVED',
                       'ONE_FROZEN_SEGMENTED_RANGE_NO_RETRY')
    (tmp_path / '.range-continuation-used').write_text('first', encoding='ascii')
    (tmp_path / '.range-continuation-2-used').write_text('second', encoding='ascii')
    (tmp_path / 'model.onnx').write_bytes(b'graph')
    (tmp_path / 'model.onnx.data.part').write_bytes(b'pub')
    return values


def segment_response(body, *, name, start, end, size, **headers):
    class Response(io.BytesIO):
        status = 206
    response = Response(body)
    response.headers = {'Content-Range': f'bytes {start}-{end}/{size}',
                        'Content-Length': str(end - start + 1), **headers}
    return response


def test_segmented_frozen_public_state_completes_with_exact_ranges(monkeypatch, tmp_path):
    fake_segmented(monkeypatch, tmp_path)
    responses = [
        segment_response(b'li', name='model.onnx.data', start=3, end=4, size=6),
        segment_response(b'c', name='model.onnx.data', start=5, end=5, size=6),
        segment_response(b'to', name='tokenizer.json', start=0, end=1, size=3),
        segment_response(b'k', name='tokenizer.json', start=2, end=2, size=3),
    ]
    seen = []
    def open_url(request, **kwargs):
        assert request.full_url == download.public_artifact_url(download.manifest(),
                                                                request.full_url.rsplit('/', 1)[1])
        seen.append((request.get_header('Range'), request.get_header('Accept-encoding'), kwargs['timeout']))
        return responses.pop(0)
    monkeypatch.setattr(download, 'urlopen', open_url)
    result = download.download(resume_public_partial=True, approved_segmented_continuation=True)
    assert result['status'] == 'download_completed'
    assert (result['artifact_requests'], result['transferred_bytes'], result['bundle_bytes']) == (4, 6, 14)
    assert [entry[0] for entry in seen] == ['bytes=3-4', 'bytes=5-5', 'bytes=0-1', 'bytes=2-2']
    assert all(0 < timeout <= 60 and encoding == 'identity' for _, encoding, timeout in seen)
    assert (tmp_path / 'model.onnx.data').read_bytes() == b'public'
    assert (tmp_path / 'tokenizer.json').read_bytes() == b'tok'
    assert (tmp_path / '.range-continuation-used').read_text(encoding='ascii') == 'first'
    assert (tmp_path / '.range-continuation-2-used').read_text(encoding='ascii') == 'second'
    assert (tmp_path / download.SEGMENTED_MARKER).is_file()
    assert download.download(resume_public_partial=True,
                             approved_segmented_continuation=True)['artifact_requests'] == 0


def test_segmented_needs_separate_process_opt_in_and_priors(monkeypatch, tmp_path):
    fake_segmented(monkeypatch, tmp_path)
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    monkeypatch.delenv('CARDCH_PUBLIC_4B_SEGMENTED_CONTINUATION_APPROVED')
    assert download.download(resume_public_partial=True,
                             approved_segmented_continuation=True)['status'] == 'download_not_authorized'
    assert not (tmp_path / download.SEGMENTED_MARKER).exists()
    monkeypatch.setenv('CARDCH_PUBLIC_4B_SEGMENTED_CONTINUATION_APPROVED',
                       'ONE_FROZEN_SEGMENTED_RANGE_NO_RETRY')
    (tmp_path / '.range-continuation-2-used').unlink()
    result = download.download(resume_public_partial=True, approved_segmented_continuation=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'preflight' and result['artifact_requests'] == 0
    assert not (tmp_path / download.SEGMENTED_MARKER).exists()


@pytest.mark.parametrize('change', ['wrong_offset', 'too_many_requests', 'unexpected_file'])
def test_segmented_changed_state_or_budget_stops_before_marker_and_network(monkeypatch, tmp_path, change):
    fake_segmented(monkeypatch, tmp_path)
    if change == 'wrong_offset':
        (tmp_path / 'model.onnx.data.part').write_bytes(b'pu')
    elif change == 'too_many_requests':
        monkeypatch.setattr(download, 'MAX_SEGMENT_REQUESTS', 3)
    else:
        (tmp_path / 'unreviewed').write_bytes(b'x')
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    result = download.download(resume_public_partial=True, approved_segmented_continuation=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'preflight' and result['artifact_requests'] == 0
    assert not (tmp_path / download.SEGMENTED_MARKER).exists()


@pytest.mark.parametrize('change', ['status', 'range', 'length', 'encoding'])
def test_segmented_rejects_inexact_response_before_mutation(monkeypatch, tmp_path, change):
    fake_segmented(monkeypatch, tmp_path)
    response = segment_response(b'li', name='model.onnx.data', start=3, end=4, size=6)
    if change == 'status':
        response.status = 200
    elif change == 'range':
        response.headers['Content-Range'] = 'bytes 0-1/6'
    elif change == 'length':
        response.headers.pop('Content-Length')
    else:
        response.headers['Content-Encoding'] = 'gzip'
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: response)
    result = download.download(resume_public_partial=True, approved_segmented_continuation=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'response_contract' and result['artifact_requests'] == 1
    assert (tmp_path / 'model.onnx.data.part').read_bytes() == b'pub'
    assert not (tmp_path / 'model.onnx.data').exists()


@pytest.mark.parametrize('body', [b'l', b'lix'])
def test_segmented_short_or_overlong_body_cannot_finalize(monkeypatch, tmp_path, body):
    fake_segmented(monkeypatch, tmp_path)
    monkeypatch.setattr(download, 'urlopen',
                        lambda *_args, **_kwargs: segment_response(body, name='model.onnx.data',
                                                                    start=3, end=4, size=6))
    result = download.download(resume_public_partial=True, approved_segmented_continuation=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'response_length' and result['artifact_requests'] == 1
    assert not (tmp_path / 'model.onnx.data').exists()


def test_segmented_transport_failure_reports_fixed_stage_without_exception(monkeypatch, tmp_path):
    fake_segmented(monkeypatch, tmp_path)
    def fail(*_args, **_kwargs):
        raise OSError('private signed redirect URL')
    monkeypatch.setattr(download, 'urlopen', fail)
    result = download.download(resume_public_partial=True, approved_segmented_continuation=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'transport_open' and result['artifact_requests'] == 1
    assert 'private' not in repr(result)


def test_segmented_read_failure_reports_transport_stage_without_exception(monkeypatch, tmp_path):
    fake_segmented(monkeypatch, tmp_path)
    class Response(io.BytesIO):
        status = 206
        headers = {'Content-Range': 'bytes 3-4/6', 'Content-Length': '2'}
        def read1(self, _size=-1):
            raise OSError('private signed redirect URL')
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: Response(b''))
    result = download.download(resume_public_partial=True, approved_segmented_continuation=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'transport_read' and result['artifact_requests'] == 1
    assert 'private' not in repr(result)


def test_segmented_replaced_partial_identity_never_appends(monkeypatch, tmp_path):
    fake_segmented(monkeypatch, tmp_path)
    partial = tmp_path / 'model.onnx.data.part'
    def open_url(*_args, **_kwargs):
        partial.rename(tmp_path / 'original')
        partial.write_bytes(b'bad')
        return segment_response(b'li', name='model.onnx.data', start=3, end=4, size=6)
    monkeypatch.setattr(download, 'urlopen', open_url)
    result = download.download(resume_public_partial=True, approved_segmented_continuation=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'disk_write' and result['artifact_requests'] == 1
    assert partial.read_bytes() == b'bad'
    assert (tmp_path / 'original').read_bytes() == b'pub'


def test_segmented_prefix_mutation_cannot_pass_disk_digest(monkeypatch, tmp_path):
    fake_segmented(monkeypatch, tmp_path)
    responses = [
        segment_response(b'li', name='model.onnx.data', start=3, end=4, size=6),
        segment_response(b'c', name='model.onnx.data', start=5, end=5, size=6),
    ]
    def open_url(*_args, **_kwargs):
        if len(responses) == 2:
            with (tmp_path / 'model.onnx.data.part').open('r+b') as changed:
                changed.write(b'bad')
        return responses.pop(0)
    monkeypatch.setattr(download, 'urlopen', open_url)
    result = download.download(resume_public_partial=True, approved_segmented_continuation=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'digest' and result['artifact_requests'] == 2
    assert not (tmp_path / 'model.onnx.data').exists()


def test_segmented_rechecks_existing_graph_before_reporting_complete(monkeypatch, tmp_path):
    fake_segmented(monkeypatch, tmp_path)
    responses = [
        segment_response(b'li', name='model.onnx.data', start=3, end=4, size=6),
        segment_response(b'c', name='model.onnx.data', start=5, end=5, size=6),
        segment_response(b'to', name='tokenizer.json', start=0, end=1, size=3),
        segment_response(b'k', name='tokenizer.json', start=2, end=2, size=3),
    ]
    def open_url(*_args, **_kwargs):
        if len(responses) == 1:
            (tmp_path / 'model.onnx').write_bytes(b'other')
        return responses.pop(0)
    monkeypatch.setattr(download, 'urlopen', open_url)
    result = download.download(resume_public_partial=True, approved_segmented_continuation=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'bundle_digest' and result['artifact_requests'] == 4


def fake_six_small_files(monkeypatch, tmp_path):
    values = download.manifest()
    small = {
        'tokenizer.json': b'a', 'config.json': b'b', 'genai_config.json': b'c',
        'tokenizer_config.json': b'd', 'chat_template.jinja': b'e', 'README.md': b'f',
    }
    values['PINS'] = {
        'model.onnx': (5, hashlib.sha256(b'graph').hexdigest()),
        'model.onnx.data': (4, hashlib.sha256(b'data').hexdigest()),
        **{name: (len(body), hashlib.sha256(body).hexdigest()) for name, body in small.items()},
    }
    monkeypatch.setattr(download, 'manifest', lambda: values)
    monkeypatch.setattr(download, 'check_destination', lambda: tmp_path)
    monkeypatch.setattr(download, 'SMALL_FILES_TRANSFER_BYTES', 6)
    monkeypatch.setenv('CARDCH_PUBLIC_4B_DOWNLOAD_APPROVED', 'ONE_PINNED_PUBLIC_BUNDLE_NO_RETRY')
    monkeypatch.setenv('CARDCH_PUBLIC_4B_SIX_SMALL_FILES_APPROVED',
                       'ONE_FROZEN_SIX_FILES_NO_RETRY')
    for marker in ('.range-continuation-used', '.range-continuation-2-used',
                   download.SEGMENTED_MARKER):
        (tmp_path / marker).write_text('used', encoding='ascii')
    (tmp_path / 'model.onnx').write_bytes(b'graph')
    (tmp_path / 'model.onnx.data').write_bytes(b'data')
    return small


def small_file_response(body):
    class Response(io.BytesIO):
        status = 200
    response = Response(body)
    response.headers = {'Content-Length': str(len(body))}
    return response


def test_six_small_files_completion_exactly_one_request_each_and_full_bundle(monkeypatch, tmp_path):
    small = fake_six_small_files(monkeypatch, tmp_path)
    seen = []
    def open_url(request, **kwargs):
        name = request.full_url.rsplit('/', 1)[1]
        assert request.full_url == download.public_artifact_url(download.manifest(), name)
        seen.append((name, request.get_header('Range'), request.get_header('Accept-encoding'),
                     kwargs['timeout']))
        return small_file_response(small[name])
    monkeypatch.setattr(download, 'urlopen', open_url)
    result = download.download(approved_six_small_files=True)
    assert result['status'] == 'download_completed'
    assert (result['artifact_requests'], result['transferred_bytes'], result['bundle_bytes']) == (6, 6, 15)
    assert [name for name, *_rest in seen] == list(small)
    assert all(byte_range is None and encoding == 'identity' and 0 < timeout <= 60
               for _name, byte_range, encoding, timeout in seen)
    assert all((tmp_path / name).read_bytes() == body for name, body in small.items())
    assert (tmp_path / download.SMALL_FILES_MARKER).is_file()
    assert download.download(approved_six_small_files=True)['artifact_requests'] == 0


def test_six_small_files_requires_separate_process_opt_in_and_three_prior_markers(monkeypatch, tmp_path):
    fake_six_small_files(monkeypatch, tmp_path)
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    monkeypatch.delenv('CARDCH_PUBLIC_4B_SIX_SMALL_FILES_APPROVED')
    assert download.download(approved_six_small_files=True)['status'] == 'download_not_authorized'
    assert not (tmp_path / download.SMALL_FILES_MARKER).exists()
    monkeypatch.setenv('CARDCH_PUBLIC_4B_SIX_SMALL_FILES_APPROVED',
                       'ONE_FROZEN_SIX_FILES_NO_RETRY')
    (tmp_path / download.SEGMENTED_MARKER).unlink()
    result = download.download(approved_six_small_files=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'preflight' and result['artifact_requests'] == 0
    assert not (tmp_path / download.SMALL_FILES_MARKER).exists()


@pytest.mark.parametrize('change', ['data_digest', 'extra_file', 'missing_graph'])
def test_six_small_files_frozen_state_stops_before_marker_or_network(monkeypatch, tmp_path, change):
    fake_six_small_files(monkeypatch, tmp_path)
    if change == 'data_digest':
        (tmp_path / 'model.onnx.data').write_bytes(b'evil')
    elif change == 'extra_file':
        (tmp_path / 'unexpected').write_bytes(b'x')
    else:
        (tmp_path / 'model.onnx').unlink()
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    result = download.download(approved_six_small_files=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'preflight' and result['artifact_requests'] == 0
    assert not (tmp_path / download.SMALL_FILES_MARKER).exists()


@pytest.mark.parametrize('change', ['status', 'length', 'encoding'])
def test_six_small_files_rejects_inexact_response_before_write(monkeypatch, tmp_path, change):
    fake_six_small_files(monkeypatch, tmp_path)
    response = small_file_response(b'a')
    if change == 'status':
        response.status = 206
    elif change == 'length':
        response.headers.pop('Content-Length')
    else:
        response.headers['Content-Encoding'] = 'gzip'
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: response)
    result = download.download(approved_six_small_files=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'response_contract' and result['artifact_requests'] == 1
    assert not (tmp_path / 'tokenizer.json.part').exists()


def test_six_small_files_digest_mismatch_retains_untrusted_partial(monkeypatch, tmp_path):
    fake_six_small_files(monkeypatch, tmp_path)
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: small_file_response(b'z'))
    result = download.download(approved_six_small_files=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'digest' and result['artifact_requests'] == 1
    assert (tmp_path / 'tokenizer.json.part').read_bytes() == b'z'
    assert not (tmp_path / 'tokenizer.json').exists()


@pytest.mark.parametrize('body', [b'', b'aa'])
def test_six_small_files_rejects_short_or_overlong_body(monkeypatch, tmp_path, body):
    fake_six_small_files(monkeypatch, tmp_path)
    response = small_file_response(body)
    response.headers['Content-Length'] = '1'
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: response)
    result = download.download(approved_six_small_files=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'response_length' and result['artifact_requests'] == 1
    assert not (tmp_path / 'tokenizer.json').exists()


def test_six_small_files_transport_failure_has_safe_fixed_stage(monkeypatch, tmp_path):
    fake_six_small_files(monkeypatch, tmp_path)
    def fail(*_args, **_kwargs):
        raise OSError('private signed redirect URL')
    monkeypatch.setattr(download, 'urlopen', fail)
    result = download.download(approved_six_small_files=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'transport_open' and result['artifact_requests'] == 1
    assert 'private' not in repr(result)


def test_six_small_files_transient_local_rename_retries_without_http_retry(monkeypatch, tmp_path):
    small = fake_six_small_files(monkeypatch, tmp_path)
    network, renames = [], []
    def open_url(request, **_kwargs):
        network.append(request.full_url)
        return small_file_response(small[request.full_url.rsplit('/', 1)[1]])
    monkeypatch.setattr(download, 'urlopen', open_url)
    original_rename = Path.rename
    def rename_once(self, target):
        if self.name == 'tokenizer.json.part':
            renames.append(1)
            if len(renames) == 1:
                raise OSError('transient local rename')
        return original_rename(self, target)
    monkeypatch.setattr(Path, 'rename', rename_once)
    monkeypatch.setattr(download, 'sleep', lambda _seconds: None)
    result = download.download(approved_six_small_files=True)
    assert result['status'] == 'download_completed'
    assert len(renames) == 2 and len(network) == 6


def test_six_small_files_persistent_local_rename_stops_without_http_retry(monkeypatch, tmp_path):
    fake_six_small_files(monkeypatch, tmp_path)
    network = []
    def open_url(*_args, **_kwargs):
        network.append(1)
        return small_file_response(b'a')
    monkeypatch.setattr(download, 'urlopen', open_url)
    original_rename = Path.rename
    renames = []
    def always_fail_first(self, target):
        if self.name == 'tokenizer.json.part':
            renames.append(1)
            raise OSError('local rename unavailable')
        return original_rename(self, target)
    monkeypatch.setattr(Path, 'rename', always_fail_first)
    monkeypatch.setattr(download, 'sleep', lambda _seconds: None)
    result = download.download(approved_six_small_files=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'finalize' and result['artifact_requests'] == 1
    assert len(renames) == download.LOCAL_FINALIZE_ATTEMPTS and len(network) == 1
    assert (tmp_path / 'tokenizer.json.part').read_bytes() == b'a'


def test_six_small_files_rechecks_large_bundle_after_network(monkeypatch, tmp_path):
    small = fake_six_small_files(monkeypatch, tmp_path)
    def open_url(request, **_kwargs):
        name = request.full_url.rsplit('/', 1)[1]
        if name == 'README.md':
            (tmp_path / 'model.onnx.data').write_bytes(b'evil')
        return small_file_response(small[name])
    monkeypatch.setattr(download, 'urlopen', open_url)
    result = download.download(approved_six_small_files=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'bundle_digest' and result['artifact_requests'] == 6


def fake_readme_only(monkeypatch, tmp_path):
    values = download.manifest()
    existing = {
        'model.onnx': b'g', 'model.onnx.data': b'd', 'tokenizer.json': b't',
        'config.json': b'c', 'genai_config.json': b'e',
        'tokenizer_config.json': b'f', 'chat_template.jinja': b'j',
    }
    values['PINS'] = {
        **{name: (len(body), hashlib.sha256(body).hexdigest())
           for name, body in existing.items()},
        download.README_NAME: (1, hashlib.sha256(b'r').hexdigest()),
    }
    monkeypatch.setattr(download, 'manifest', lambda: values)
    monkeypatch.setattr(download, 'check_destination', lambda: tmp_path)
    monkeypatch.setattr(download, 'README_BYTES', 1)
    monkeypatch.setattr(download, 'FROZEN_BUNDLE_BYTES', 8)
    monkeypatch.setenv('CARDCH_PUBLIC_4B_DOWNLOAD_APPROVED', 'ONE_PINNED_PUBLIC_BUNDLE_NO_RETRY')
    monkeypatch.setenv('CARDCH_PUBLIC_4B_README_ONLY_APPROVED',
                       'ONE_FROZEN_PUBLIC_README_NO_RETRY')
    for marker in ('.range-continuation-used', '.range-continuation-2-used',
                   download.SEGMENTED_MARKER, download.SMALL_FILES_MARKER):
        (tmp_path / marker).write_text('used', encoding='ascii')
    for name, body in existing.items():
        (tmp_path / name).write_bytes(body)
    return values


def test_readme_only_exact_single_public_get_and_full_bundle(monkeypatch, tmp_path):
    fake_readme_only(monkeypatch, tmp_path)
    requests = []
    def open_url(request, **kwargs):
        requests.append((request.full_url, request.get_header('Range'),
                         request.get_header('Accept-encoding'), kwargs['timeout']))
        return small_file_response(b'r')
    monkeypatch.setattr(download, 'urlopen', open_url)
    result = download.download(approved_readme_only=True)
    assert result['status'] == 'download_completed'
    assert (result['artifact_requests'], result['transferred_bytes'], result['bundle_bytes']) == (1, 1, 8)
    assert len(requests) == 1
    assert requests[0][0] == download.public_artifact_url(download.manifest(), 'README.md')
    assert requests[0][1] is None and requests[0][2] == 'identity' and 0 < requests[0][3] <= 60
    assert (tmp_path / 'README.md').read_bytes() == b'r'
    assert (tmp_path / download.README_MARKER).is_file()
    assert download.download(approved_readme_only=True)['artifact_requests'] == 0


def test_readme_only_requires_new_opt_in_and_four_prior_markers(monkeypatch, tmp_path):
    fake_readme_only(monkeypatch, tmp_path)
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    monkeypatch.delenv('CARDCH_PUBLIC_4B_README_ONLY_APPROVED')
    assert download.download(approved_readme_only=True)['status'] == 'download_not_authorized'
    assert not (tmp_path / download.README_MARKER).exists()
    monkeypatch.setenv('CARDCH_PUBLIC_4B_README_ONLY_APPROVED',
                       'ONE_FROZEN_PUBLIC_README_NO_RETRY')
    (tmp_path / download.SMALL_FILES_MARKER).unlink()
    result = download.download(approved_readme_only=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'preflight' and result['artifact_requests'] == 0
    assert not (tmp_path / download.README_MARKER).exists()


@pytest.mark.parametrize('change', ['existing_digest', 'unexpected_file', 'premature_readme'])
def test_readme_only_changed_state_stops_before_marker_or_network(monkeypatch, tmp_path, change):
    fake_readme_only(monkeypatch, tmp_path)
    if change == 'existing_digest':
        (tmp_path / 'model.onnx.data').write_bytes(b'x')
    elif change == 'unexpected_file':
        (tmp_path / 'unexpected').write_bytes(b'x')
    else:
        (tmp_path / 'README.md').write_bytes(b'r')
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    result = download.download(approved_readme_only=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'preflight' and result['artifact_requests'] == 0
    assert not (tmp_path / download.README_MARKER).exists()


@pytest.mark.parametrize('change', ['status', 'length', 'encoding'])
def test_readme_only_requires_exact_http_contract_before_write(monkeypatch, tmp_path, change):
    fake_readme_only(monkeypatch, tmp_path)
    response = small_file_response(b'r')
    if change == 'status':
        response.status = 206
    elif change == 'length':
        response.headers.pop('Content-Length')
    else:
        response.headers['Content-Encoding'] = 'gzip'
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: response)
    result = download.download(approved_readme_only=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'response_contract' and result['artifact_requests'] == 1
    assert not (tmp_path / 'README.md.part').exists()


@pytest.mark.parametrize('body', [b'', b'rr'])
def test_readme_only_rejects_short_or_overlong_body(monkeypatch, tmp_path, body):
    fake_readme_only(monkeypatch, tmp_path)
    response = small_file_response(body)
    response.headers['Content-Length'] = '1'
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: response)
    result = download.download(approved_readme_only=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'response_length' and result['artifact_requests'] == 1
    assert not (tmp_path / 'README.md').exists()


def test_readme_only_digest_mismatch_keeps_untrusted_partial(monkeypatch, tmp_path):
    fake_readme_only(monkeypatch, tmp_path)
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: small_file_response(b'x'))
    result = download.download(approved_readme_only=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'digest' and result['artifact_requests'] == 1
    assert (tmp_path / 'README.md.part').read_bytes() == b'x'
    assert not (tmp_path / 'README.md').exists()


def test_readme_only_transport_failure_uses_safe_stage(monkeypatch, tmp_path):
    fake_readme_only(monkeypatch, tmp_path)
    def fail(*_args, **_kwargs):
        raise OSError('private signed redirect URL')
    monkeypatch.setattr(download, 'urlopen', fail)
    result = download.download(approved_readme_only=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'transport_open' and result['artifact_requests'] == 1
    assert 'private' not in repr(result)


def test_readme_only_local_rename_retry_never_repeats_http(monkeypatch, tmp_path):
    fake_readme_only(monkeypatch, tmp_path)
    network, renames = [], []
    def open_url(*_args, **_kwargs):
        network.append(1)
        return small_file_response(b'r')
    monkeypatch.setattr(download, 'urlopen', open_url)
    original_rename = Path.rename
    def transient(self, target):
        if self.name == 'README.md.part':
            renames.append(1)
            if len(renames) == 1:
                raise OSError('local rename unavailable')
        return original_rename(self, target)
    monkeypatch.setattr(Path, 'rename', transient)
    monkeypatch.setattr(download, 'sleep', lambda _seconds: None)
    result = download.download(approved_readme_only=True)
    assert result['status'] == 'download_completed'
    assert len(network) == 1 and len(renames) == 2


def test_readme_only_rechecks_existing_bundle_after_get(monkeypatch, tmp_path):
    fake_readme_only(monkeypatch, tmp_path)
    def open_url(*_args, **_kwargs):
        (tmp_path / 'model.onnx.data').write_bytes(b'x')
        return small_file_response(b'r')
    monkeypatch.setattr(download, 'urlopen', open_url)
    result = download.download(approved_readme_only=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'bundle_digest' and result['artifact_requests'] == 1


def fake_corrected_readme(monkeypatch, tmp_path):
    values = fake_readme_only(monkeypatch, tmp_path)
    (tmp_path / download.README_MARKER).write_text('previous README request used', encoding='ascii')
    monkeypatch.setenv('CARDCH_PUBLIC_4B_CORRECTED_README_APPROVED',
                       'ONE_CORRECTED_ROOT_README_NO_RETRY')
    return values


def test_corrected_readme_requires_fifth_marker_and_separate_opt_in(monkeypatch, tmp_path):
    fake_corrected_readme(monkeypatch, tmp_path)
    monkeypatch.setattr(download, 'urlopen', lambda *_args, **_kwargs: pytest.fail('network'))
    monkeypatch.delenv('CARDCH_PUBLIC_4B_CORRECTED_README_APPROVED')
    assert download.download(approved_corrected_readme=True)['status'] == 'download_not_authorized'
    assert not (tmp_path / download.CORRECTED_README_MARKER).exists()
    monkeypatch.setenv('CARDCH_PUBLIC_4B_CORRECTED_README_APPROVED',
                       'ONE_CORRECTED_ROOT_README_NO_RETRY')
    (tmp_path / download.README_MARKER).unlink()
    result = download.download(approved_corrected_readme=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'preflight' and result['artifact_requests'] == 0
    assert not (tmp_path / download.CORRECTED_README_MARKER).exists()


def test_corrected_readme_one_root_get_keeps_history_and_verifies_bundle(monkeypatch, tmp_path):
    values = fake_corrected_readme(monkeypatch, tmp_path)
    urls = []
    def open_url(request, **kwargs):
        urls.append((request.full_url, request.get_header('Range'), kwargs['timeout']))
        return small_file_response(b'r')
    monkeypatch.setattr(download, 'urlopen', open_url)
    result = download.download(approved_corrected_readme=True)
    assert result['status'] == 'download_completed'
    assert (result['artifact_requests'], result['transferred_bytes'], result['bundle_bytes']) == (1, 1, 8)
    assert len(urls) == 1
    assert urls[0][0] == download.public_artifact_url(values, 'README.md')
    assert urls[0][1] is None and 0 < urls[0][2] <= 60
    assert (tmp_path / download.README_MARKER).read_text(encoding='ascii') == 'previous README request used'
    assert (tmp_path / download.CORRECTED_README_MARKER).is_file()
    assert (tmp_path / 'README.md').read_bytes() == b'r'
    assert download.download(approved_corrected_readme=True)['artifact_requests'] == 0


def test_corrected_readme_failed_request_consumes_only_new_marker_without_retry(monkeypatch, tmp_path):
    fake_corrected_readme(monkeypatch, tmp_path)
    calls = []
    def fail(*_args, **_kwargs):
        calls.append(1)
        raise OSError('signed redirect must stay private')
    monkeypatch.setattr(download, 'urlopen', fail)
    result = download.download(approved_corrected_readme=True)
    assert result['status'] == 'download_unavailable'
    assert result['failure_stage'] == 'transport_open' and result['artifact_requests'] == 1
    assert len(calls) == 1 and (tmp_path / download.CORRECTED_README_MARKER).is_file()
    assert (tmp_path / download.README_MARKER).is_file()
    assert 'signed' not in repr(result)
