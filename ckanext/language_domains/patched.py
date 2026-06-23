from flask import (
    redirect as _flask_redirect,
    url_for as _flask_default_url_for
)
from urllib.parse import urlparse, urlunparse, urlsplit, urlencode, parse_qsl

from typing import Any, cast, Union, Tuple, Optional
from ckan.types import Response

from ckan.exceptions import CkanUrlException
from ckan.lib import i18n
from ckan.lib.helpers import _get_auto_flask_context
from ckan.plugins.toolkit import h, request

from ckanext.language_domains.utils import get_url_parts

from logging import getLogger
log = getLogger(__name__)


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
        scheme, lang, domain, root_path, keep_lang_paths = get_url_parts()
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
    scheme, _locale, domain, _root_path, _keep_lang_paths = get_url_parts(locale)
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

    scheme, _lang, domain, root_path, _keep_lang_paths = get_url_parts(locale)

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


def dcat_catalog_uri() -> str:
    """
    Monkey patches the DCAT Plugin catalog_uri util method
    to specify the correct domain and root paths
    """
    scheme, lang, domain, root_path, keep_lang_paths = get_url_parts()
    catalog_uri = str(f'{scheme}://{domain}')

    if not root_path and keep_lang_paths:
        catalog_uri += f'/{lang}'
    elif root_path:
        catalog_uri += f'{root_path}'

    return catalog_uri


def create_atom_id(atom_id: str, resource_path: str,
                   authority_name: Optional[str] = None,
                   date_string: Optional[str] = None) -> str:
    """
    Sets the correct domain and root paths for the Atom feeds IDs
    """
    scheme, lang, domain, root_path, keep_lang_paths = get_url_parts()
    if not keep_lang_paths and resource_path.startswith(f'/{lang}/'):
        # set the id url for non lang paths
        resource_path = root_path + resource_path.rstrip('/')[len(f'/{lang}'):]
    elif not resource_path.startswith(root_path):
        # set the id url for lang paths
        resource_path = f'{root_path}{resource_path}'
    authority_name = str(f'{scheme}://{domain}')
    if date_string:
        tagging_entity = ','.join([authority_name, date_string])
    atom_id = ':'.join(['tag', tagging_entity, resource_path])
    return atom_id


def datastore_insert_links(data_dict: dict[str, Any],
                           limit: int, offset: int):
    data_dict['_links'] = {}

    # get the url from the request
    try:
        urlstring = request.environ['CKAN_CURRENT_URL']
    except (KeyError, TypeError, RuntimeError):
        return  # no links required for local actions

    # change the offset in the url
    parsed = list(urlparse(urlstring))
    query = parsed[4]

    arguments = dict(parse_qsl(query))
    arguments_start = dict(arguments)
    arguments_prev: dict[str, Any] = dict(arguments)
    arguments_next: dict[str, Any] = dict(arguments)
    if 'offset' in arguments_start:
        arguments_start.pop('offset')
    arguments_next['offset'] = int(offset) + int(limit)
    arguments_prev['offset'] = int(offset) - int(limit)

    parsed_start = parsed[:]
    parsed_prev = parsed[:]
    parsed_next = parsed[:]
    parsed_start[4] = urlencode(arguments_start)
    parsed_next[4] = urlencode(arguments_next)
    parsed_prev[4] = urlencode(arguments_prev)

    parsed_start = urlunparse(parsed_start)
    parsed_next = urlunparse(parsed_next)
    parsed_prev = urlunparse(parsed_prev)

    _scheme, lang, _domain, root_path, keep_lang_paths = get_url_parts()
    if not keep_lang_paths:
        # set the api page links for non lang paths
        if not parsed_start.startswith(f'/{lang}/'):
            parsed_start = f'/{lang}{parsed_start}'
        if not parsed_next.startswith(f'/{lang}/'):
            parsed_next = f'/{lang}{parsed_next}'
        if not parsed_prev.startswith(f'/{lang}/'):
            parsed_prev = f'/{lang}{parsed_prev}'
    else:
        # set the api page links for lang paths
        if not parsed_start.startswith(root_path):
            parsed_start = f'{root_path}{parsed_start}'
        if not parsed_next.startswith(root_path):
            parsed_next = f'{root_path}{parsed_next}'
        if not parsed_prev.startswith(root_path):
            parsed_prev = f'{root_path}{parsed_prev}'

    # add the links to the data dict
    data_dict['_links']['start'] = parsed_start
    data_dict['_links']['next'] = parsed_next
    if int(offset) - int(limit) > 0:
        data_dict['_links']['prev'] = parsed_prev
