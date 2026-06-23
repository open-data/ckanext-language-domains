from typing import Any, Callable, Dict
from ckan.types import CKANApp, Validator, Optional
from ckan.common import CKANConfig

import ckan.plugins as plugins
import ckan.lib.helpers as core_helpers
import ckanext.datastore.backend.postgres as core_ds_psql
import ckanext.dcat.utils as dcat_utils

from ckanext.language_domains import patched, validators, logic
from ckanext.language_domains.middleware import LanguageDomainMiddleware

from logging import getLogger
log = getLogger(__name__)


@plugins.toolkit.blanket.config_declarations
class LanguageDomainsPlugin(plugins.SingletonPlugin):
    plugins.implements(plugins.IMiddleware, inherit=True)
    plugins.implements(plugins.IConfigurer)
    plugins.implements(plugins.IValidators)
    plugins.implements(plugins.ITemplateHelpers)
    plugins.implements(plugins.IActions)
    plugins.implements(plugins.IFeed, inherit=True)

    # IMiddleware
    def make_middleware(self, app: CKANApp, config: 'CKANConfig') -> CKANApp:
        return LanguageDomainMiddleware(
            app, config, getattr(app, 'original_flask_app', None))

    # IConfigurer
    def update_config(self, config: 'CKANConfig'):
        # NOTE: monkey patch these core helpers as the other helpers call them directly
        #       and other plugins may import them directly
        core_helpers.redirect_to = patched.redirect_to
        core_helpers.get_site_protocol_and_host = patched.get_site_protocol_and_host
        core_helpers._local_url = patched.local_url

        # NOTE: monkey patch these dcat methods to set the @id generations
        dcat_utils.catalog_uri = patched.dcat_catalog_uri

        # NOTE: monkey patch these datastore methods to set the API paging URIs
        core_ds_psql._insert_links = patched.datastore_insert_links

    # IFeed
    def create_atom_id(self, atom_id: str, resource_path: str,
                       authority_name: Optional[str] = None,
                       date_string: Optional[str] = None) -> str:
        return patched.create_atom_id(
            atom_id, resource_path, authority_name, date_string)

    # IValidators
    def get_validators(self) -> Dict[str, Validator]:
        return {
            'load_json_string': validators.load_json_string,
        }

    # ITemplateHelpers
    def get_helpers(self) -> Dict[str, Callable[..., Any]]:
        return {'redirect_to': patched.redirect_to,
                'get_site_protocol_and_host': patched.get_site_protocol_and_host}

    # IActions
    def get_actions(self) -> Dict[str, Callable[..., Any]]:
        return {'package_show': logic.package_show}
