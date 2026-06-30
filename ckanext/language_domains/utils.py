from urllib.parse import urlsplit
import re

from typing import Tuple, Dict, Optional

from ckan.plugins.toolkit import h, config, request

from logging import getLogger
log = getLogger(__name__)


def get_domain_index(current_domain: str, language_domains: Dict[str, str]) -> int:
    """
    Returns the index position for a given domain in the domain map
    """
    for _lang_code, lang_domains in language_domains.items():
        try:
            return lang_domains.index(current_domain)
        except ValueError:
            continue
    return 0


def get_url_parts(helper_locale: Optional[str] = None) -> Tuple[str, str, str, str, bool]:
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
    default_locale = config['ckan.locale_default']
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
            correct_lang_code = default_locale
        correct_lang_code = helper_locale or default_locale
        requesting_domain = default_domain

    if should_get_from_config:
        keep_lang_paths = config['ckanext.language_domains.keep_lang_paths']
        language_domains = config.get('ckanext.language_domains.domain_map')
        domain_index_match = get_domain_index(requesting_domain, language_domains)
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
        # if correct_lang_code happens to be None, use default
        if correct_lang_code is None:
            correct_lang_code = default_locale
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

    # fallback to defaults in worst cases
    if correct_domain is None:
        correct_domain = default_domain
    if correct_lang_code is None:
        correct_lang_code = default_locale

    return (default_scheme, correct_lang_code, correct_domain, root_path, keep_lang_paths)
