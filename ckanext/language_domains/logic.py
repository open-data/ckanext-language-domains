from urllib.parse import urlparse, urlunparse

from ckan.types import Context, DataDict, Action, ChainedAction

from ckan.plugins.toolkit import (
    chained_action,
    side_effect_free,
)

from ckanext.language_domains.utils import get_url_parts


@chained_action
@side_effect_free
def package_show(up_func: Action,
                 context: Context,
                 data_dict: DataDict) -> ChainedAction:
    """
    Extends the core package_show action method to modify
    the URLs of resources.

    For packages being indexed, we do not want the domain or any root paths.

    For the normal package_show, we want to prepend the configured mapped domain
    along with the root paths etc.
    """
    # store a local var incase another plugin pops it from the context
    for_index = context.get('for_index', False)
    # run parent method with for_index=True so that no domain info
    # is prepended to the resource URLs
    context['for_index'] = True
    pkg_dict = up_func(context, data_dict)

    if pkg_dict.get('resources'):
        # only get the mapped parts if there are resources
        scheme, lang, domain, root_path, _keep_lang_paths = get_url_parts()

    for r in pkg_dict.get('resources', []):
        if r.get('url_type') != 'upload':
            continue
        if not for_index:
            if r.get('url', '').startswith('/'):
                # prepend mapped domain and root path for core url
                # relative uploaded resources.
                res_url = r['url']
                res_url_parts = urlparse(res_url)
                res_url = urlunparse((
                    scheme,
                    domain,
                    root_path + res_url_parts.path.rstrip('/'),
                    res_url_parts.params,
                    res_url_parts.query,
                    res_url_parts.fragment
                ))
                r['url'] = res_url
            if r.get('original_url', '').startswith('/'):
                # prepend mapped domain and root path for XLoader url
                # relative uploaded resources.
                res_url = r['original_url']
                res_url_parts = urlparse(res_url)
                res_url = urlunparse((
                    scheme,
                    domain,
                    root_path + res_url_parts.path.rstrip('/'),
                    res_url_parts.params,
                    res_url_parts.query,
                    res_url_parts.fragment
                ))
                r['original_url'] = res_url
        else:
            # make sure all upload URLs are relative
            # without any root paths
            if r.get('url', '').startswith(root_path):
                # remove the root path
                r['url'] = r['url'][len(root_path):]
            if r.get('url', '').startswith(f'/{lang}/'):
                # remove the lang sub dir path
                r['url'] = r['url'][len(f'/{lang}'):]
            if r.get('original_url', '').startswith(root_path):
                # remove the root path
                r['original_url'] = r['original_url'][len(root_path):]
            if r.get('original_url', '').startswith(f'/{lang}/'):
                # remove the lang sub dir path
                r['original_url'] = r['original_url'][len(f'/{lang}'):]

    return pkg_dict
