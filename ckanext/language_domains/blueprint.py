from flask import Blueprint
from urllib.parse import urlsplit
import json

from ckan.plugins.toolkit import request, render, config


language_domain_views = Blueprint('language_domains', __name__)

@language_domain_views.route('/user/language_domain_login', methods=['GET'])
def language_domain_login():
    came_from = request.args.get('came_from', '')

    default_domain = config.get('ckan.site_url', '')
    uri_parts = urlsplit(default_domain)
    domain_scheme = uri_parts.scheme

    language_domains = config.get('ckanext.language_domains.domain_map', '')
    if not language_domains:
        language_domains = {}
    else:
        language_domains = json.loads(language_domains)

    return render('user/language_login.html', {'language_domains': language_domains,
                                               'domain_scheme': domain_scheme})