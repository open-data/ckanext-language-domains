from logging import getLogger
import json
from urllib.parse import urlsplit

from typing import Any, Optional, List, Tuple, Callable, Dict
from flask import Blueprint
from ckan.types import CKANApp
from ckan.common import CKANConfig

import ckan.plugins as plugins
import ckan.lib.helpers as core_helpers

from ckanext.language_domains import helpers
from ckanext.language_domains.blueprint import language_domain_views


log = getLogger(__name__)


@plugins.toolkit.blanket.config_declarations
class LanguageDomainsPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IMiddleware, inherit=True)
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IBlueprint)
    plugins.implements(plugins.IResourceController, inherit=True)

    # IMiddleware
    def make_middleware(self, app: CKANApp, config: 'CKANConfig') -> CKANApp:
        return LanguageDomainMiddleware(app, config)

    # IConfigurer
    def update_config(self, config: 'CKANConfig'):
        # NOTE: monkey patch these core helpers as the other helpers call them directly
        core_helpers.redirect_to = helpers.redirect_to
        core_helpers.get_site_protocol_and_host = helpers.get_site_protocol_and_host
        core_helpers._local_url = helpers.local_url

        plugins.toolkit.add_template_directory(config, 'templates')
        plugins.toolkit.add_resource('assets', 'language_domain_assets')

        config['ckan.auth.route_after_login'] = 'language_domains.login_master'

    # ITemplateHelpers
    def get_helpers(self) -> Dict[str, Callable[..., Any]]:
        return {'redirect_to': helpers.redirect_to,
                'get_site_protocol_and_host': helpers.get_site_protocol_and_host}

    # IBlueprint
    def get_blueprint(self) -> List[Blueprint]:
        return [language_domain_views]

    # IResourceController
    def before_resource_show(self, resource_dict: Dict[str, Any]) -> Dict[str, Any]:
        # FIXME: is there a better way to store res_url in SOLR to prevent this
        #        for everytime a Resource is shown???
        language_domains = plugins.toolkit.config.get(
            'ckanext.language_domains.domain_map', '')
        if not language_domains:
            language_domains = {}
        else:
            language_domains = json.loads(language_domains)

        try:
            current_language = plugins.toolkit.h.lang()
            current_domain = plugins.toolkit.request.url
            uri_parts = urlsplit(current_domain)
            current_domain = uri_parts.netloc
            _scheme, _host = helpers._get_correct_language_domain()
        except RuntimeError:
            current_language = 'en'
            default_domain = plugins.toolkit.config.get('ckan.site_url', '')
            uri_parts = urlsplit(default_domain)
            current_domain = _host = uri_parts.netloc
            _scheme = uri_parts.scheme

        domain_index_match = helpers._get_domain_index(
            current_domain, language_domains)

        for lang_code, lang_domains in language_domains.items():
            if (
              resource_dict.get('url', '').startswith(
                  f'{_scheme}://{lang_domains[domain_index_match]}') and
              _host != lang_domains[domain_index_match]
            ):
                uri_parts = urlsplit(resource_dict['url'])
                path = str(uri_parts.path)
                if path.startswith(f'/{lang_code}/'):
                    path = path[len(f'/{lang_code}'):]
                elif path.startswith(f'/{current_language}/'):
                    path = path[len(f'/{current_language}'):]
                resource_dict['url'] = uri_parts._replace(
                    netloc=_host, path=path).geturl()
                break

        return resource_dict


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
        root_paths = config.get('ckanext.language_domains.root_paths', '')
        if not root_paths:
            self.root_paths = {}
        else:
            self.root_paths = json.loads(root_paths)

    def __call__(self, environ: Any, start_response: Any) -> Any:
        extra_response_headers = []
        current_domain = environ['HTTP_X_FORWARDED_HOST'] or \
            environ['HTTP_HOST'] or \
            self.default_domain
        current_lang = environ['CKAN_LANG']
        current_uri = str(environ['REQUEST_URI'])
        correct_lang_domain = self.default_domain
        domain_index_match = helpers._get_domain_index(
            current_domain, self.language_domains)
        for lang_code, lang_domains in self.language_domains.items():
            if current_domain in lang_domains and lang_code != current_lang:
                # current domain is correct but lang code isn't, set correct code
                environ['CKAN_LANG'] = current_lang = lang_code
            if lang_code == environ['CKAN_LANG'] and (
              current_domain not in lang_domains or
              environ['HTTP_HOST'] not in lang_domains):
                # lang code is correct but domain isn't, set correct domain
                correct_lang_domain = environ['HTTP_HOST'] = \
                    lang_domains[domain_index_match]
            if (
              current_uri.startswith(f'/{lang_code}/') or
              current_uri == f'/{lang_code}'
            ):
                # a user has navigated to a lang sub dir, move 'em to the domain
                correct_lang_domain = lang_domains[domain_index_match]
                # get rid of lang code
                root_path = self.root_paths.get(correct_lang_domain, '').rstrip('/')
                root_path.replace('/{{LANG}}', '')
                environ['REQUEST_URI'] = current_uri = root_path + current_uri[
                    len(f'/{current_lang}'):]
                extra_response_headers = [(
                    'Location',
                    f'{self.domain_scheme}://{correct_lang_domain}{current_uri}')]

        def _start_response(status: str,
                            response_headers: List[Tuple[str, str]],
                            exc_info: Optional[Any] = None):
            return start_response(
                # browser requires non 200 response for Location header
                status if not extra_response_headers else '301',
                response_headers + extra_response_headers,
                exc_info)

        return self.app(environ, _start_response)
