from flask import (
    redirect as _flask_redirect,
    url_for as _flask_default_url_for
)
from urllib.parse import urlparse, urlunparse, urlsplit
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
    """
    Returns the index position for a given domain in the domain map
    """
    for _lang_code, lang_domains in language_domains.items():
        try:
            return lang_domains.index(current_domain)
        except ValueError:
            continue
    return 0


def _get_url_parts(helper_locale: Optional[str] = None) -> Tuple[str, str, str, str, bool]:
    """
    Returns a tuple of
        HTTP scheme,
        locale code,
        mapped domain for the current language,
        parsed root path for the current language,
        bool if keeping locale paths or not;

    At this point, the LanguageDomainMiddleware has already set the
    correct language for the current domain.

    If the helper_locale is the same as the main page request,
    it will just use the request environ values set by the
    LanguageDomainMiddleware. Otherwise, it will parse from the configs.
    """
    should_get_from_config = False
    # default vars
    default_domain = config.get('ckan.site_url', '')
    uri_parts = urlsplit(default_domain)
    default_scheme = uri_parts.scheme
    default_domain = uri_parts.netloc
    # cache vars
    cached_lang_code = None
    cached_domain = None
    cached_root_path = None
    cached_keep_lang_paths = None
    # returning vars
    correct_lang_code = None
    correct_domain = None
    root_path = None
    keep_lang_paths = None

    try:
        # get requesting parts
        requesting_domain = request.url
        uri_parts = urlsplit(requesting_domain)
        requesting_domain = uri_parts.netloc
        if helper_locale == 'default':
            requesting_lang = h.lang()
        else:
            requesting_lang = helper_locale
        # get the variables from the request environ middleware keys
        cached_lang_code = request.environ.get('__LDM__LANG_CODE') or \
            request.environ.get('CKAN_LANG')
        cached_domain = request.environ.get('__LDM__CORRECT_DOMAIN')
        cached_root_path = request.environ.get('__LDM__ROOT_PATH')
        cached_keep_lang_paths = request.environ.get('__LDM__KEEP_LANG_PATHS')
        if not cached_lang_code or (
            helper_locale and cached_lang_code != requesting_lang
        ):
            # there is no request cached locale, or the cached locale is
            # not the same as the helper param
            should_get_from_config = True
            correct_lang_code = requesting_lang
    except (TypeError, RuntimeError):
        # outside of the Flask request/view context,
        # use default domain & language
        should_get_from_config = True
        if helper_locale == 'default':
            correct_lang_code = config['ckan.locale_default']
        correct_lang_code = helper_locale or config['ckan.locale_default']
        requesting_domain = default_domain

    if should_get_from_config:
        keep_lang_paths = config['ckanext.language_domains.keep_lang_paths']
        language_domains = config.get('ckanext.language_domains.domain_map')
        domain_index_match = _get_domain_index(requesting_domain, language_domains)
        for lang_code, lang_domains in language_domains.items():
            if requesting_domain == lang_domains[domain_index_match]:
                # the language map is configured with the same host for all languages
                # we can assume that the current Flask language is correct.
                if lang_code != correct_lang_code:
                    continue
                correct_domain = lang_domains[domain_index_match]
                break
            if (
                requesting_domain != lang_domains[domain_index_match] and
                lang_code == correct_lang_code and
                requesting_domain not in lang_domains
            ):
                # lang code is correct but domain isn't, set correct domain
                correct_domain = lang_domains[domain_index_match]
                break
        # get configured root paths
        root_paths = config.get('ckanext.language_domains.root_paths')
        root_path = root_paths.get(correct_domain, '').rstrip('/')
        if keep_lang_paths:
            # keeping lang paths, so do replacement in root path
            root_path = re.sub('{{LANG}}', correct_lang_code, root_path)
        else:
            # remove the lang code replacement from the root path
            root_path = re.sub('{{LANG}}', '', root_path).rstrip('/')
        if keep_lang_paths and not root_path:
            # fallback to lang paths if no root path
            root_path = f'/{correct_lang_code}'
    else:
        correct_lang_code = cached_lang_code
        correct_domain = cached_domain
        root_path = cached_root_path
        keep_lang_paths = cached_keep_lang_paths

    return (default_scheme, correct_lang_code, correct_domain, root_path, keep_lang_paths)


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
        scheme, lang, domain, root_path, keep_lang_paths = _get_url_parts()
        if not keep_lang_paths and _url.startswith(f'/{lang}/'):
            # set the redirect url for non lang paths
            _url = root_path + _url[len(f'/{lang}'):]
        elif not _url.startswith(root_path):
            # set the redirect url for lang paths
            _url = f'/{root_path}{_url}'

        _url = str(f'{scheme}://{domain}{_url}')

    return cast(Response, _flask_redirect(_url, code=status_code))


def get_site_protocol_and_host(locale: Optional[str] = None) -> Union[
        Tuple[str, str], Tuple[None, None]]:
    """
    Overrides and monkey patches the Core helper get_site_protocol_and_host
    to use ckanext.language_domains.domain_map instead of ckan.site_url
    """
    scheme, _locale, domain, _root_path, _keep_lang_paths = _get_url_parts(locale)
    return (scheme, domain)


def local_url(url_to_amend: str, **kw: Any):
    """
    Overrides and monkey patches the Core helper method _local_url
    to use ckanext.language_domains.root_paths instead of ckan.root_path
    """
    locale = kw.pop('locale', None)
    kw.pop('__ckan_no_root', False)
    allowed_locales = ['default'] + i18n.get_locales()
    if locale and locale not in allowed_locales:
        locale = None
    url_to_amend_parts = urlsplit(url_to_amend)
    url_path = url_to_amend_parts.path

    _auto_flask_context = _get_auto_flask_context()

    if _auto_flask_context:
        _auto_flask_context.push()

    scheme, _lang, domain, root_path, _keep_lang_paths = _get_url_parts(locale)

    root = ''
    if kw.get('qualified', False) or kw.get('_external', False):
        # if qualified is given we want the full url ie http://...
        parts = urlparse(
            _flask_default_url_for('home.index', _external=True)
        )

        path = parts.path.rstrip('/')
        root = urlunparse(
            (scheme, domain, path,
                parts.params, parts.query, parts.fragment))

    if _auto_flask_context:
        _auto_flask_context.pop()

    url = '%s%s%s' % (root, root_path, url_path)

    if url_to_amend_parts.query:
        url += '?' + url_to_amend_parts.query

    if url_to_amend_parts.fragment:
        url += '#' + url_to_amend_parts.fragment

    if url == '/packages':
        error = 'There is a broken url being created %s' % kw
        raise CkanUrlException(error)

    return url
