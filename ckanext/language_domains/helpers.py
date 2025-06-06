from flask import redirect as _flask_redirect
from urllib.parse import urlsplit
import json

from typing import Any, cast, Union, Tuple
from ckan.types import Response

from ckan.plugins.toolkit import h, config, request


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
    for lang_code, lang_domains in language_domains.items():
        # TODO: figure out lang_domains[0] from current subdomain or not??
        if lang_code == current_lang and current_domain not in lang_domains:
            correct_lang_domain = lang_domains[0]
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

    if _url.startswith('/'):
        current_lang = h.lang()
        if _url.startswith(f'/{current_lang}/'):
            _url = _url[len(f'/{current_lang}'):]
        _schema, _host = _get_correct_language_domain()
        _url = str(f'{_schema}://{_host}{_url}')

    return cast(Response, _flask_redirect(_url))


def get_site_protocol_and_host() -> Union[Tuple[str, str], Tuple[None, None]]:
    """
    Overrides and monkey patches the Core helper get_site_protocol_and_host
    to use ckanext.language_domains.domain_map instead of ckan.site_url
    """
    return _get_correct_language_domain()