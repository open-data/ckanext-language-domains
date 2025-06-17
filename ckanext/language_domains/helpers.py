from flask import redirect as _flask_redirect
from urllib.parse import urlsplit
import json

from typing import Any, cast, Union, Tuple, Dict
from ckan.types import Response

from ckan.plugins.toolkit import h, config, request


def _get_domain_index(current_domain: str, language_domains: Dict[str, str]) -> int:
    for _lang_code, lang_domains in language_domains.items():
        for index, domain in enumerate(lang_domains):
            if current_domain == domain:
                return index
    return 0


def _get_correct_language_domain() -> Tuple[str, str]:
    """
    Returns the HTTP scheme and mapped domain for the current language.

    At this point, the LanguageDomainMiddleware has already set the
    correct language for the current domain.
    """
    current_domain = request.url
    uri_parts = urlsplit(current_domain)
    current_domain = uri_parts.netloc
    default_domain = config.get('ckan.site_url', '')
    uri_parts = urlsplit(default_domain)
    default_scheme = uri_parts.scheme
    language_domains = config.get('ckanext.language_domains.domain_map', '')
    if not language_domains:
        language_domains = {}
    else:
        language_domains = json.loads(language_domains)
    current_lang = h.lang()
    correct_lang_domain = current_domain
    domain_index_match = _get_domain_index(current_domain, language_domains)
    for lang_code, lang_domains in language_domains.items():
        if lang_code == current_lang and current_domain not in lang_domains:
            correct_lang_domain = lang_domains[domain_index_match]
    return (default_scheme, correct_lang_domain)


def redirect_to(*args: Any, **kw: Any) -> Response:
    """
    Overrides the Core helper redirect_to to use
    ckanext.language_domains.domain_map instead of ckan.site_url
    """
    uargs = [str(arg) if isinstance(arg, str) else arg for arg in args]

    _url = ''
    skip_url_parsing = False
    parse_url = kw.pop('parse_url', False)
    if uargs and len(uargs) == 1 and isinstance(uargs[0], str) \
            and (uargs[0].startswith('/') or h.is_url(uargs[0])) \
            and parse_url is False:
        skip_url_parsing = True
        _url = uargs[0]

    if skip_url_parsing is False:
        _url = h.url_for(*uargs, **kw)

    status_code = 302

    if _url.startswith('/'):
        current_lang = h.lang()
        if _url.startswith(f'/{current_lang}/'):
            status_code = 301
            _url = _url[len(f'/{current_lang}'):]
        root_path = config.get('ckan.root_path', '')
        if root_path is None:
            root_path = ''
        root_path = root_path.replace('/{{LANG}}', '')
        if not _url.startswith(root_path):
            _url = root_path + _url
        _scheme, _host = _get_correct_language_domain()
        _url = str(f'{_scheme}://{_host}{_url}')

    return cast(Response, _flask_redirect(_url, code=status_code))


def get_site_protocol_and_host() -> Union[Tuple[str, str], Tuple[None, None]]:
    """
    Overrides and monkey patches the Core helper get_site_protocol_and_host
    to use ckanext.language_domains.domain_map instead of ckan.site_url
    """
    return _get_correct_language_domain()
