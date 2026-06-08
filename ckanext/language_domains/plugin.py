from logging import getLogger
from urllib.parse import urlsplit
import re

from typing import Any, Optional, List, Tuple, Callable, Dict
from flask import Blueprint
from ckan.types import CKANApp, Validator
from ckan.common import CKANConfig

import ckan.plugins as plugins
import ckan.lib.helpers as core_helpers

from ckanext.language_domains import helpers, validators
from ckanext.language_domains.blueprint import language_domain_views


log = getLogger(__name__)


@plugins.toolkit.blanket.config_declarations
class LanguageDomainsPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IMiddleware, inherit=True)
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IBlueprint)

    # IMiddleware
    def make_middleware(self, app: CKANApp, config: 'CKANConfig') -> CKANApp:
        return LanguageDomainMiddleware(
            app, config, getattr(app, 'original_flask_app', None))

    # IConfigurer
    def update_config(self, config: 'CKANConfig'):
        # NOTE: monkey patch these core helpers as the other helpers call them directly
        # TODO: fix upstream helpers to always use h object helpers!!!
        core_helpers.redirect_to = helpers.redirect_to
        core_helpers.get_site_protocol_and_host = helpers.get_site_protocol_and_host
        core_helpers._local_url = helpers.local_url

        if plugins.toolkit.config.get('ckanext.language_domains.'
                                      'enable_jwt_login', False):
            plugins.toolkit.add_template_directory(config, 'templates')
            plugins.toolkit.add_resource('assets', 'language_domain_assets')

            config['ckan.auth.route_after_login'] = 'language_domains.login_master'

    # IValidators
    def get_validators(self) -> Dict[str, Validator]:
        return {
            'load_json_string': validators.load_json_string,
        }

    # ITemplateHelpers
    def get_helpers(self) -> Dict[str, Callable[..., Any]]:
        return {'redirect_to': helpers.redirect_to,
                'get_site_protocol_and_host': helpers.get_site_protocol_and_host}

    # IBlueprint
    def get_blueprint(self) -> List[Blueprint]:
        if plugins.toolkit.config.get('ckanext.language_domains.'
                                      'enable_jwt_login', False):
            return [language_domain_views]
        return []


class LanguageDomainMiddleware(object):
    def __init__(self, app: Any, config: 'CKANConfig',
                 flask_app: Optional[Any] = None):
        self.original_flask_app = flask_app or app
        self.app = app
        self.language_domains = config.get('ckanext.language_domains.domain_map')
        default_domain = config.get('ckan.site_url', '')
        uri_parts = urlsplit(default_domain)
        self.default_domain = uri_parts.netloc
        self.domain_scheme = uri_parts.scheme
        self.root_paths = config.get('ckanext.language_domains.root_paths')
        self.redirect_user_sessions = config.get(
            'ckanext.language_domains.redirect_user_sessions', False)
        self.enable_jwt_login = config.get(
            'ckanext.language_domains.enable_jwt_login', False)
        self.keep_lang_paths = config.get(
            'ckanext.language_domains.keep_lang_paths', False)

    def __call__(self, environ: Any, start_response: Any) -> Any:
        extra_response_headers = []
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
        domain_index_match = helpers._get_domain_index(
            current_domain, self.language_domains)
        for lang_code, lang_domains in self.language_domains.items():
            # the language map is configured with the same host for all languages
            using_same_host_per_lang = current_domain == lang_domains[domain_index_match]
            if (
              not using_same_host_per_lang and
              current_domain in lang_domains and
              lang_code != current_lang
            ):
                # current domain is correct but lang code isn't, set correct code
                environ['CKAN_LANG'] = current_lang = lang_code
            if (
              not using_same_host_per_lang and
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
            # a user has navigated to a lang sub dir, move 'em to the domain
            correct_lang_domain = lang_domains[domain_index_match]
            # get configured root paths
            root_path = self.root_paths.get(correct_lang_domain, '').rstrip('/')
            if root_path and self.keep_lang_paths:
                # there is a root path and we are keeping lang paths
                root_path = re.sub('{{LANG}}', lang_code, root_path)
            else:
                # remove the lang code replacement from the root path
                root_path = re.sub('{{LANG}}', '', root_path).rstrip('/')
            if not self.keep_lang_paths and current_uri.startswith(f'/{current_lang}/'):
                # set the Flask url for non lang paths
                environ['REQUEST_URI'] = current_uri = root_path + current_uri[
                    len(f'/{current_lang}'):]
            elif not root_path and not current_uri.startswith(f'/{current_lang}/'):
                # set the Flask url for non root paths using lang paths
                environ['REQUEST_URI'] = current_uri = f'/{current_lang}{current_uri}'
            elif root_path and not current_uri.startswith(root_path):
                # set the Flask url for root paths using lang paths
                current_uri_no_root = current_uri
                if not current_uri_no_root.startswith(f'/{current_lang}/'):
                    current_uri_no_root = f'/{current_lang}{current_uri_no_root}'
                if current_uri.startswith(f'/{current_lang}/'):
                    current_uri = current_uri[len(f'/{current_lang}'):]
                environ['REQUEST_URI'] = current_uri = f'{root_path}{current_uri}'
            if environ['REQUEST_METHOD'] == 'POST':
                # NOTE: cannot re-POST data from Location header redirects
                continue
            if (
              current_domain != correct_lang_domain or
              (
                requesting_uri != current_uri and
                requesting_uri != current_uri_no_root
              )
            ):
                # only redirect if we need to change language domains
                # or add language codes into the requesting URI
                extra_response_headers = [(
                    'Location',
                    f'{self.domain_scheme}://{correct_lang_domain}{current_uri}')]

        def _start_response(status: str,
                            response_headers: List[Tuple[str, str]],
                            exc_info: Optional[Any] = None):
            # TODO: check if there is a user and don't do domain redirects??
            return start_response(
                # browser requires non 200 response for Location header
                status if not extra_response_headers else '301',
                response_headers + extra_response_headers,
                exc_info)

        return self.app(environ, _start_response)
