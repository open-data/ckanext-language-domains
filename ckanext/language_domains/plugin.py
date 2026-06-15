from logging import getLogger

from typing import Any, Callable, Dict
from ckan.types import CKANApp, Validator
from ckan.common import CKANConfig

import ckan
import ckan.plugins as plugins
import ckan.lib.helpers as core_helpers
import ckan.views as core_views

from ckanext.language_domains import helpers, validators
from ckanext.language_domains.middleware import LanguageDomainMiddleware


log = getLogger(__name__)


@plugins.toolkit.blanket.config_declarations
class LanguageDomainsPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IMiddleware, inherit=True)
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.ITemplateHelpers)

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
        # core_views.set_ckan_current_url = helpers.set_ckan_current_url
        # ckan.views.set_ckan_current_url = helpers.set_ckan_current_url

    # IValidators
    def get_validators(self) -> Dict[str, Validator]:
        return {
            'load_json_string': validators.load_json_string,
        }

    # ITemplateHelpers
    def get_helpers(self) -> Dict[str, Callable[..., Any]]:
        return {'redirect_to': helpers.redirect_to,
                'get_site_protocol_and_host': helpers.get_site_protocol_and_host}
