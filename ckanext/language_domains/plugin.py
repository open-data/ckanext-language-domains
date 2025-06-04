from logging import getLogger
import json
from urllib.parse import urlsplit

from typing import Any, Optional, List, Tuple, Callable, Dict
from ckan.types import CKANApp
from ckan.common import CKANConfig, current_user

import ckan.plugins as plugins
import ckan.lib.helpers as core_helpers
from ckan.plugins.toolkit import request

from ckanext.language_domains import helpers


log = getLogger(__name__)


@plugins.toolkit.blanket.config_declarations
class LanguageDomainsPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IMiddleware, inherit=True)
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IAuthenticator, inherit=True)

    # IMiddleware
    def make_middleware(self, app: CKANApp, config: 'CKANConfig') -> CKANApp:
        return LanguageDomainMiddleware(app, config)

    # IConfigurer
    def update_config(self, config: 'CKANConfig'):
        # NOTE: monkey patch this core helper as the other helpers call it directly
        core_helpers.redirect_to = helpers.redirect_to
        core_helpers.get_site_protocol_and_host = helpers.get_site_protocol_and_host

    # ITemplateHelpers
    def get_helpers(self) -> Dict[str, Callable[..., Any]]:
        return {'redirect_to': helpers.redirect_to,
                'get_site_protocol_and_host': helpers.get_site_protocol_and_host}

    # IAuthenticator
    def identify(self):
        # TODO: read other domain cookies to get sessions??
        if 'links' in request.url:
            log.info('    ')
            log.info('DEBUGGING::')
            log.info('    ')
            log.info(request)
            log.info('    ')
            log.info(request.environ)
            log.info('    ')
            log.info(current_user)
            log.info('    ')
        return


class LanguageDomainMiddleware(object):
    def __init__(self, app: Any, config: 'CKANConfig'):
        self.app = app
        language_domains = config.get('ckanext.language_domains.domain_map', '')
        if not language_domains:
            self.language_domains = {}
        else:
            self.language_domains = json.loads(language_domains)
        default_domain = config.get('ckan.site_url', '')
        uri_parts = urlsplit(default_domain)
        self.default_domain = uri_parts.netloc
        self.domain_scheme = uri_parts.scheme

    def __call__(self, environ: Any, start_response: Any) -> Any:
        extra_response_headers = []
        current_domain = environ['HTTP_X_FORWARDED_HOST'] or \
                         environ['HTTP_HOST'] or \
                         self.default_domain
        current_lang = environ['CKAN_LANG']
        current_uri = str(environ['REQUEST_URI'])
        correct_lang_domain = self.default_domain
        # TODO: set environ['SESSION_COOKIE_DOMAIN'] ??
        # TODO: OR pass over environ['HTTP_COOKIE'] ??
        for lang_code, lang_domains in self.language_domains.items():
            # TODO: figure out lang_domains[0] from current subdomain or not??
            if current_domain in lang_domains and lang_code != current_lang:
                # current domain is correct but lang code isn't, set correct code
                environ['CKAN_LANG'] = current_lang = lang_code
            if lang_code == environ['CKAN_LANG'] and (
              current_domain not in lang_domains or
              environ['HTTP_HOST'] not in lang_domains):
                # lang code is correct but domain isn't, set correct domain
                correct_lang_domain = environ['HTTP_HOST'] = lang_domains[0]
            if current_uri.startswith(f'/{lang_code}'):
                # a user has navigated to a lang sub dir, move 'em to the domain
                correct_lang_domain = lang_domains[0]
                # get rid of lang code
                environ['REQUEST_URI'] = current_uri = current_uri[
                    len(f'/{current_lang}'):]
                extra_response_headers = [('Location', self.domain_scheme + '://' +
                                                       correct_lang_domain +
                                                       current_uri)]

        def _start_response(status: str,
                            response_headers: List[Tuple[str, str]],
                            exc_info: Optional[Any] = None):
            return start_response(
                # browser requires non 200 response for Location header
                status if not extra_response_headers else '302',
                response_headers + extra_response_headers,
                exc_info)

        return self.app(environ, _start_response)