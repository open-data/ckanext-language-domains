from flask import (
    redirect as _flask_redirect,
    url_for as _flask_default_url_for
)
from urllib.parse import urlparse, urlunparse, urlsplit, quote
import re

from typing import Any, cast, Union, Tuple, Dict, Optional
from ckan.types import Response

from ckan.exceptions import CkanUrlException
from ckan.lib import i18n
from ckan.lib.helpers import _get_auto_flask_context
from ckan.plugins.toolkit import h, config, request

from logging import getLogger
log = getLogger(__name__)


def _get_domain_index(current_domain: str, language_domains: Dict[str, str]) -> int:
    for _lang_code, lang_domains in language_domains.items():
        try:
            return lang_domains.index(current_domain)
        except ValueError:
            continue
    return 0


def _get_correct_language_domain(locale: Optional[str] = None) -> Tuple[str, str]:
    """
    Returns the HTTP scheme and mapped domain for the current language.

    At this point, the LanguageDomainMiddleware has already set the
    correct language for the current domain.
    """
    default_domain = config.get('ckan.site_url', '')
    uri_parts = urlsplit(default_domain)
    default_scheme = uri_parts.scheme
    default_domain = uri_parts.netloc
    try:
        current_domain = request.url
        uri_parts = urlsplit(current_domain)
        current_domain = uri_parts.netloc
        current_lang = locale or h.lang()
    except RuntimeError:
        # outside of the Flask request/view context,
        # use default domain & language
        current_domain = default_domain
        current_lang = locale or config['ckan.locale_default']
    language_domains = config.get('ckanext.language_domains.domain_map')
    correct_lang_domain = current_domain
    domain_index_match = _get_domain_index(current_domain, language_domains)
    for lang_code, lang_domains in language_domains.items():
        if (
          current_domain != lang_domains[domain_index_match] and
          lang_code == current_lang and
          current_domain not in lang_domains
        ):
            correct_lang_domain = lang_domains[domain_index_match]
    return (default_scheme, correct_lang_domain)


def _generate_root_path(hostname: str, lang_code: str) -> str:
    root_paths = config.get('ckanext.language_domains.root_paths')
    keep_lang_paths = config.get(
        'ckanext.language_domains.keep_lang_paths', False)
    root_path = root_paths.get(hostname, '').rstrip('/')
    if keep_lang_paths:
        # keeping lang paths, so do replacement in root path
        root_path = re.sub('{{LANG}}', lang_code, root_path)
    else:
        # remove the lang code replacement from the root path
        root_path = re.sub('{{LANG}}', '', root_path).rstrip('/')
    if keep_lang_paths and not root_path:
        # fallback to lang paths if no root path
        root_path = f'/{lang_code}'
    return root_path, keep_lang_paths


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
        keep_lang_paths = config.get(
            'ckanext.language_domains.keep_lang_paths', False)
        current_lang = h.lang()
        _scheme, _host = _get_correct_language_domain()
        root_paths = config.get('ckanext.language_domains.root_paths')
        root_path = root_paths.get(_host, '').rstrip('/')
        if not keep_lang_paths:
            root_path = re.sub('{{LANG}}', '', root_path).rstrip('/')
        else:
            root_path = re.sub('{{LANG}}', current_lang, root_path)
        if not keep_lang_paths and _url.startswith(f'/{current_lang}/'):
            # set the redirect url for non lang paths
            _url = _url[len(f'/{current_lang}'):]
        elif not root_path and not _url.startswith(f'/{current_lang}/'):
            # set the redirect url for non root paths using lang paths
            _url = f'/{current_lang}{_url}'
        elif root_path and not _url.startswith(root_path):
            # set the redirect url for root paths using lang paths
            if _url.startswith(f'/{current_lang}/'):
                _url = _url[len(f'/{current_lang}'):]
            _url = f'{root_path}{_url}'

        _url = str(f'{_scheme}://{_host}{_url}')

    return cast(Response, _flask_redirect(_url, code=status_code))


def get_site_protocol_and_host(locale: Optional[str] = None) -> Union[
        Tuple[str, str], Tuple[None, None]]:
    """
    Overrides and monkey patches the Core helper get_site_protocol_and_host
    to use ckanext.language_domains.domain_map instead of ckan.site_url
    """
    return _get_correct_language_domain(locale=locale)


def local_url(url_to_amend: str, **kw: Any):
    """
    Overrides and monkey patches the Core helper method _local_url
    to use ckanext.language_domains.root_paths instead of ckan.root_path
    """
    locale = kw.pop('locale', None)
    no_root = kw.pop('__ckan_no_root', False)
    allowed_locales = ['default'] + i18n.get_locales()
    if locale and locale not in allowed_locales:
        locale = None

    _auto_flask_context = _get_auto_flask_context()

    if _auto_flask_context:
        _auto_flask_context.push()

    protocol, host = get_site_protocol_and_host(locale)
    try:
        locale = locale or request.environ.get('__LDM__LANG_CODE') or \
              request.environ.get('CKAN_LANG')
        host = request.environ.get('__LDM__CORRECT_DOMAIN') or host
        root_path = request.environ.get('__LDM__ROOT_PATH')
        keep_lang_paths = request.environ.get('__LDM__KEEP_LANG_PATHS')
    except (TypeError, RuntimeError):
        # outside of the Flask request/view context,
        # or does not have a language, use default locale
        locale = config['ckan.locale_default']
        root_path, keep_lang_paths = _generate_root_path(host, locale)

    if locale == 'default':
        locale = config['ckan.locale_default']

    root = ''
    if kw.get('qualified', False) or kw.get('_external', False):
        # if qualified is given we want the full url ie http://...
        parts = urlparse(
            _flask_default_url_for('home.index', _external=True)
        )

        path = parts.path.rstrip('/')
        root = urlunparse(
            (protocol, host, path,
                parts.params, parts.query, parts.fragment))

    if _auto_flask_context:
        _auto_flask_context.pop()

    # root_path domain may be different from url_to_amend domain
    # if a different locale is provided. Just use urlsplit.path
    url_to_amend_parts = urlsplit(url_to_amend)
    url_path = url_to_amend_parts.path

    if keep_lang_paths and not root_path and not url_path.startswith(f'/{locale}/'):
        # add locale if no root path, and if keeping lang paths
        url_path = f'/{locale}{url_path}'

    url = '%s%s%s' % (root, root_path, url_path)

    if url_to_amend_parts.query:
        url += '?' + url_to_amend_parts.query

    if url_to_amend_parts.fragment:
        url += '#' + url_to_amend_parts.fragment

    # stop the root being added twice in redirects
    if no_root and url_to_amend.startswith(root):
        url = url_to_amend[len(root):]
        url = '/%s%s' % (locale, url)

    if url == '/packages':
        error = 'There is a broken url being created %s' % kw
        raise CkanUrlException(error)

    return url
