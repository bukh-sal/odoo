"""One reviewed distribution-only correction; never a package-defined patch."""
import hashlib

PARSER_PATH='odoo/tools/parse_version.py'
SOURCE_SHA256='71eeb2085e17c03fd4c31a222559d38d6c78cddb278ef0f4b17c5ecf8163b214'
TARGET_SHA256='dfbad4b881f38deea7185535e3f249b3908dd6c3c9dc8fbfeafcee8d9067e175'
PATCH_ID='native-numeric-width-v1'

def patch_record():
    return {'path':PARSER_PATH,'patch_id':PATCH_ID,'source_sha256':SOURCE_SHA256,'result_sha256':TARGET_SHA256}

def corrected_parser(raw):
    """Keep checked-out upstream bytes untouched; transform only a fresh copy."""
    if hashlib.sha256(raw).hexdigest()!=SOURCE_SHA256:
        raise ValueError('Native version parser source differs from the reviewed upstream preimage')
    helper=b"""def _numeric_component(part):
    # Modular Platform: compare decimal width before value, without a fixed pad.
    digits = part.lstrip('0') or '0'
    width = str(len(digits))
    return '1' * len(width) + '0' + width + ':' + digits


"""
    raw=raw.replace(b'def _parse_version_parts(s):',helper+b'def _parse_version_parts(s):')
    raw=raw.replace(b'part.zfill(8)    # pad for numeric comparison',b'_numeric_component(part)  # width-independent numeric comparison')
    raw=raw.replace(b"parts[-1]=='00000000'",b"parts[-1]==_numeric_component('0')")
    raw=raw.replace(b'    version are padded to 8 digits so they will compare numerically, but\n    without relying on how numbers compare relative to strings.',
        b'    version use width-prefixed decimal keys so they compare numerically even\n    beyond eight digits, without mixing numbers and strings.')
    if hashlib.sha256(raw).hexdigest()!=TARGET_SHA256:
        raise ValueError('Native version parser correction differs from its reviewed output')
    return raw

def reviewed_transition(before,after):
    """Exact bytes AND provenance; cached/package assertions confer no authority."""
    if before['files'].get(PARSER_PATH)!=SOURCE_SHA256 or after['files'].get(PARSER_PATH)!=TARGET_SHA256:
        return False
    old=before.get('generated_patches',[])
    return patch_record() not in old and after.get('generated_patches',[])==old+[patch_record()]
