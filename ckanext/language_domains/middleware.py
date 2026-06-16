from urllib.parse import urlsplit
import re

from typing import Any, Optional, List, Tuple
from ckan.common import CKANConfig

from ckanext.language_domains.helpers import _get_domain_index

from logging import getLogger
log = getLogger(__name__)


class LanguageDomainMiddleware(object):
    """

    """

    def __init__(self, app: Any, config: 'CKANConfig',
                flask_app: Optional[Any] = None):
        """

        """
        self.original_flask_app = flask_app or app
        self.app = app
        self.language_domains = config.get('ckanext.language_domains.domain_map')
        default_domain = config.get('ckan.site_url', '')
        uri_parts = urlsplit(default_domain)
        self.default_domain = uri_parts.netloc
        self.domain_scheme = uri_parts.scheme
        self.root_paths = config.get('ckanext.language_domains.root_paths')
        self.keep_lang_paths = config['ckanext.language_domains.keep_lang_paths']

    def __call__(self, environ: Any, start_response: Any) -> Any:
        """

        """
        self.start_response = start_response
        self.extra_response_headers = []

        if 'HTTP_X_FORWARDED_HOST' in environ and environ['HTTP_X_FORWARDED_HOST']:
            # get the requesting host from reverse proxy headers
            current_domain = environ['HTTP_X_FORWARDED_HOST']
        elif 'HTTP_HOST' in environ and environ['HTTP_HOST']:
            # get the requesting host from reverse proxy headers
            current_domain = environ['HTTP_HOST']
        else:
            # fallback to the ckan.site_url host
            current_domain = self.default_domain
        current_lang = environ['CKAN_LANG']  # current lang code inside Flask
        current_uri = str(environ['REQUEST_URI'])  # current url inside Flask

        current_uri_no_root = None  # var for later checks
        requesting_uri = current_uri  # var for later checks

        correct_lang_domain = self.default_domain  # start with the ckan.site_url host
        domain_index_match = _get_domain_index(current_domain, self.language_domains)

        for lang_code, lang_domains in self.language_domains.items():
            if current_domain == lang_domains[domain_index_match]:
                # the language map is configured with the same host for all languages
                # we can assume that the current Flask language is correct.
                if lang_code != current_lang:
                    continue
                correct_lang_code = lang_code
                correct_lang_domain = lang_domains[domain_index_match]
                break
            if (
                current_domain in lang_domains and
                lang_code != current_lang
            ):
                # current domain is correct but lang code isn't, set correct code
                environ['CKAN_LANG'] = current_lang = lang_code
            if (
                lang_code == environ['CKAN_LANG'] and
                (
                    current_domain not in lang_domains or
                    environ['HTTP_HOST'] not in lang_domains
                )
            ):
                # lang code is correct but domain isn't, set correct domain
                correct_lang_domain = environ['HTTP_HOST'] = \
                    lang_domains[domain_index_match]
            if lang_code != current_lang:
                # at this point, we have "corrected" the host and lang codes
                # so if it does not match, then it is not the one we want
                continue
            # make sure we have the correct lang and domain for further parsing
            correct_lang_code = lang_code
            correct_lang_domain = lang_domains[domain_index_match]
            # we have the correct lang code and domains now, break
            break

        # get configured root paths
        root_path = self.root_paths.get(correct_lang_domain, '').rstrip('/')
        if self.keep_lang_paths:
            # keeping lang paths, so do replacement in root path
            root_path = re.sub('{{LANG}}', correct_lang_code, root_path)
        else:
            # remove the lang code replacement from the root path
            root_path = re.sub('{{LANG}}', '', root_path).rstrip('/')
        if self.keep_lang_paths and not root_path:
            # fallback to lang paths if no root path
            root_path = f'/{correct_lang_code}'

        if not self.keep_lang_paths and current_uri.startswith(f'/{correct_lang_code}/'):
            # set the Flask url for non lang paths
            environ['REQUEST_URI'] = current_uri = root_path + current_uri[
                len(f'/{correct_lang_code}'):]
        elif not current_uri.startswith(root_path):
            # set the Flask url for lang paths
            current_uri_no_root = current_uri
            if not current_uri_no_root.startswith(f'/{correct_lang_code}/'):
                current_uri_no_root = f'/{correct_lang_code}{current_uri_no_root}'
            if current_uri.startswith(f'/{correct_lang_code}/'):
                current_uri = current_uri[len(f'/{correct_lang_code}'):]
            environ['REQUEST_URI'] = current_uri = f'{root_path}{current_uri}'

        # set environ variables for easy use in helpers
        environ['__LDM__CORRECT_DOMAIN'] = correct_lang_domain
        environ['__LDM__LANG_CODE'] = correct_lang_code
        environ['__LDM__ROOT_PATH'] = root_path
        environ['__LDM__KEEP_LANG_PATHS'] = self.keep_lang_paths

        if environ['REQUEST_METHOD'] == 'POST':
            # NOTE: cannot re-POST data from Location header redirects
            return self.app(environ, self._start_response)

        if (
            current_domain != correct_lang_domain or
            (requesting_uri != current_uri and requesting_uri != current_uri_no_root)
        ):
            # only redirect if we need to change language domains
            # or add language codes into the requesting URI
            self.extra_response_headers = [(
                'Location',
                f'{self.domain_scheme}://{correct_lang_domain}{current_uri}')]

        return self.app(environ, self._start_response)

    def _start_response(self, status: str,
                        response_headers: List[Tuple[str, str]],
                        exc_info: Optional[Any] = None):
        """

        """
        return self.start_response(
            # browser requires non 200 response for Location header
            status if not self.extra_response_headers else '301',
            response_headers + self.extra_response_headers,
            exc_info)
