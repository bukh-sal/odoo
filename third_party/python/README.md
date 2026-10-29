# Supplemental Python dependency notices

These upstream files accompany the qualified application image because its installed Python distributions did not retain standalone notice files in their installed metadata:

| Package | Version | Retained notice | Source |
| --- | --- | --- | --- |
| GeoIP2 | 2.9.0 | `geoip2-2.9.0/LICENSE` | [Versioned PyPI source](https://pypi.org/project/geoip2/2.9.0/) |
| pySerial | 3.5 | `pyserial-3.5/LICENSE.txt` | [Versioned PyPI source](https://pypi.org/project/pyserial/3.5/) |
| xlwt | 1.3.0 | `xlwt-1.3.0/docs/licenses.rst` | [Versioned PyPI source](https://pypi.org/project/xlwt/1.3.0/) |

The files are unchanged. Their source archives were checked against the existing runtime dependency lock before reading notice members; no downloaded package code was executed. [Archive URLs, exact hashes and member provenance](../../docs/evidence/G5/20261029-provenance-01/supplemental-notices.json) and the [complete release notice inventory](../../docs/evidence/G5/20261029-provenance-01/notice-bundle-final.json) are retained. Keep these files with the image, root LICENSE/COPYRIGHT and other dependency notices; see [release provenance](../../docs/provenance.md).
