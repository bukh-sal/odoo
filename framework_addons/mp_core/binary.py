"""Bounded current-actor binary transport; storage and file policy are app-owned.

Only trusted native registration supplies models, private handlers and schemas.
Browser IDs/header values never select arbitrary model attributes or grant access.
Legacy attachment/token/stream APIs remain unavailable for scoped records.
"""
import copy
from dataclasses import dataclass
import json
import re
import unicodedata
from urllib.parse import quote
from uuid import UUID

from jsonschema import Draft202012Validator
from odoo import http
from odoo.exceptions import AccessError
from odoo.http import request
from modular_platform.artifacts import ArtifactValidator
from modular_platform.contracts import ContractError, FORMAT_CHECKER, load_json

from .controllers import PublicError, result


MAX_BYTES = 8 * 1024 * 1024
MAX_METADATA = 4096
ENDPOINTS = {}


@dataclass(frozen=True)
class BinaryEndpoint:
    model: str
    upload: str
    download: str
    metadata_schema: dict
    output_schema: dict
    max_bytes: int


@dataclass(frozen=True)
class BinaryContent:
    data: bytes
    filename: str


def safe_filename(value):
    if (not isinstance(value, str) or not 1 <= len(value) <= 180
            or unicodedata.normalize('NFC', value) != value
            or value in {'.', '..'} or value != value.strip()
            or any(c in '/\\' or unicodedata.category(c).startswith('C') for c in value)):
        raise ContractError('A bounded plain filename is required')
    return value


def register_binary(plugin, resource, endpoint):
    """Native startup seam, not an HTTP/DB/artifact-selected authorization root."""
    if (not isinstance(plugin, str) or not re.fullmatch(r'[a-z][a-z0-9]*(?:[._-][a-z0-9]+)+', plugin)
            or not isinstance(resource, str) or not re.fullmatch(r'[a-z][a-z0-9_-]{0,63}', resource)
            or not isinstance(endpoint, BinaryEndpoint)
            or not isinstance(endpoint.model, str) or not re.fullmatch(r'[a-z][a-z0-9_.]+', endpoint.model)
            or any(not isinstance(name, str) or not re.fullmatch(r'_mp_binary_[a-z][a-z0-9_]*', name)
                   for name in (endpoint.upload, endpoint.download))
            or type(endpoint.max_bytes) is not int or not 0 < endpoint.max_bytes <= MAX_BYTES):
        raise ValueError('Invalid binary endpoint registration')
    if (plugin, resource) in ENDPOINTS:
        raise ValueError('Duplicate binary endpoint')
    for schema in (endpoint.metadata_schema, endpoint.output_schema):
        if not isinstance(schema, dict):
            raise ValueError('Owned binary schemas required')
        Draft202012Validator.check_schema(schema)
        ArtifactValidator._local_refs(schema)
    ENDPOINTS[plugin, resource] = copy.deepcopy(endpoint)


def _endpoint(plugin, resource, action):
    endpoint = ENDPOINTS.get((plugin, resource))
    if endpoint is None:
        raise PublicError('NOT_FOUND')
    model = request.env[endpoint.model]
    if not getattr(model, '_mp_scoped', False) or model._mp_plugin_id != plugin:
        raise AccessError('Binary resource ownership mismatch')
    # Scope refresh, current membership/role/action, feature and installation
    # checks are exactly the supported model guard, without sudo/user fallback.
    model._mp_guard(action)
    return endpoint, model


def _metadata(endpoint):
    raw = request.httprequest.headers.get('X-MP-Binary-Metadata', '')
    if not isinstance(raw, str) or len(raw.encode('utf8')) > MAX_METADATA:
        raise ContractError('Bounded binary metadata required')
    value = load_json(raw.encode('utf8'))
    if not isinstance(value, dict) or not Draft202012Validator(
            endpoint.metadata_schema, format_checker=FORMAT_CHECKER).is_valid(value):
        raise ContractError('Invalid binary metadata')
    return value


def _download_response(content):
    # The handler is trusted native code, but its output still has a hard bound
    # and cannot inject headers or request inline active-content rendering.
    if not isinstance(content, BinaryContent) or type(content.data) is not bytes or len(content.data) > MAX_BYTES:
        raise PublicError('INTERNAL_ERROR')
    name = safe_filename(content.filename)
    return request.make_response(content.data, headers=[
        ('Content-Type', 'application/octet-stream'),
        ('Content-Disposition', "attachment; filename=download; filename*=UTF-8''" + quote(name, safe='')),
        ('Content-Length', str(len(content.data))),
        ('Cache-Control', 'no-store'),
        ('X-Content-Type-Options', 'nosniff'),
        ('Content-Security-Policy', "default-src 'none'; sandbox"),
        ('Referrer-Policy', 'no-referrer'),
    ])


class BinaryGateway(http.Controller):
    @http.route('/api/v1/binary/<string:plugin>/<string:resource>', type='http',
                auth='public', methods=['POST'], csrf=False, max_content_length=MAX_BYTES)
    def upload(self, plugin, resource, **kwargs):
        def run():
            endpoint, model = _endpoint(plugin, resource, 'create')
            if not request.validate_csrf(request.httprequest.headers.get('X-CSRFToken')):
                raise AccessError('CSRF required')
            if (kwargs or request.httprequest.query_string
                    or request.httprequest.mimetype != 'application/octet-stream'
                    or request.httprequest.headers.get('Content-Encoding')):
                raise ContractError('Unencoded raw binary required')
            metadata = _metadata(endpoint)
            if (request.httprequest.content_length or 0) > endpoint.max_bytes:
                raise ContractError('File exceeds binary endpoint bound')
            # Native route max_content_length also bounds unknown/chunked input
            # before get_data; endpoint-specific bound is checked on actual data.
            data = request.httprequest.get_data()
            if not data or len(data) > endpoint.max_bytes:
                raise ContractError('File exceeds binary endpoint bound')
            value = getattr(model, endpoint.upload)(metadata, data)
            model._mp_guard('create')
            if (not Draft202012Validator(endpoint.output_schema, format_checker=FORMAT_CHECKER).is_valid(value)
                    or len(json.dumps(value, ensure_ascii=False).encode('utf8')) > 65536):
                raise PublicError('INTERNAL_ERROR')
            return value
        return result(run)

    @http.route('/api/v1/binary/<string:plugin>/<string:resource>/<string:ident>',
                type='http', auth='public', methods=['GET'])
    def download(self, plugin, resource, ident, **kwargs):
        def run():
            endpoint, model = _endpoint(plugin, resource, 'read')
            if kwargs or request.httprequest.query_string or request.httprequest.headers.get('Range'):
                raise ContractError('Whole authenticated resource required')
            try:
                if str(UUID(ident)) != ident:
                    raise ValueError()
            except (ValueError, TypeError, AttributeError):
                raise ContractError('Canonical binary identifier required') from None
            content = getattr(model, endpoint.download)(ident)
            model._mp_guard('read')
            if not isinstance(content, BinaryContent) or type(content.data) is not bytes or len(content.data) > endpoint.max_bytes:
                raise PublicError('INTERNAL_ERROR')
            return content
        return result(run, response_factory=_download_response)
