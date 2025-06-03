from logging import getLogger
import json
from urllib.parse import urlsplit
from flask import redirect as _flask_redirect

from typing import Any, Optional, List, Tuple

import ckan.plugins as plugins

from ckan.types import (
    CKANApp
)
from ckan.common import CKANConfig

from ckan.plugins.toolkit import g, h, request


log = getLogger(__name__)


@plugins.toolkit.blanket.config_declarations
class LanguageDomainsPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IMiddleware, inherit=True)

    # IMiddleware
    def make_middleware(self, app: CKANApp, config: 'CKANConfig') -> CKANApp:
        return LanguageDomainMiddleware(app, config)


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
        for lang_code, lang_domain in self.language_domains.items():
            if lang_domain == current_domain and lang_code != current_lang:
                environ['CKAN_LANG'] = lang_code
            if lang_code == environ['CKAN_LANG'] and lang_domain != current_domain:
                environ['HTTP_HOST'] = lang_domain
            if lang_code != current_lang \
              and environ['REQUEST_URI'].startswith(  # type: ignore
              f'/{current_lang}/'):
                environ['REQUEST_URI'] = f'/{lang_code}/' + \
                    environ['REQUEST_URI'][len(f'/{current_lang}/'):]
                extra_response_headers = [('Location', self.domain_scheme + '://' +
                                                       environ['HTTP_HOST'] +
                                                       environ['REQUEST_URI'])]

        def _start_response(status: str,
                            response_headers: List[Tuple[str, str]],
                            exc_info: Optional[Any] = None):
            return start_response(
                status if not extra_response_headers else '302',
                response_headers + extra_response_headers,
                exc_info)

        return self.app(environ, _start_response)