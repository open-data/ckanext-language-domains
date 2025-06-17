from flask import Blueprint
from functools import wraps
from werkzeug.datastructures import ImmutableMultiDict
from urllib.parse import urlsplit
from logging import getLogger
import json
import jwt
import datetime

from typing import Callable, Any

from ckan.logic import parse_params
from ckan.model import User
from ckan.plugins.toolkit import (
    request,
    render,
    config,
    g,
    h,
    _,
    login_user,
    logout_user
)
from ckan.views.api import _finish_ok, _finish
from ckan.views.user import login as core_login

from ckanext.language_domains.helpers import _get_domain_index


log = getLogger(__name__)
language_domain_views = Blueprint('language_domains', __name__)


def forced_came_from(_func: Callable[..., Any]) -> Callable[..., Any]:
    @wraps(_func)
    def _decorator_function(*args: Any, **kwargs: Any):
        http_args = request.args.to_dict()
        http_args['_came_from'] = http_args.pop(
            'next', http_args.pop('came_from', ''))

        # type_ignore_reason: incomplete typing
        request.args = ImmutableMultiDict(http_args)  # type: ignore

        return _func(*args, **kwargs)
    return _decorator_function


@language_domain_views.route('/user/login', methods=['GET', 'POST'])
@forced_came_from
def login_core():
    return core_login()


@language_domain_views.route('/user/domain_login', methods=['GET'])
def login_master():
    if not g.user:
        return h.redirect_to('user.login')

    came_from = request.args.get('_came_from', '')

    default_domain = config.get('ckan.site_url', '')
    uri_parts = urlsplit(default_domain)
    domain_scheme = uri_parts.scheme

    language_domains = config.get('ckanext.language_domains.domain_map', '')
    if not language_domains:
        language_domains = {}
    else:
        language_domains = json.loads(language_domains)

    current_domain = request.url
    uri_parts = urlsplit(current_domain)
    current_domain = uri_parts.netloc
    domain_index_match = _get_domain_index(current_domain, language_domains)

    trusted_domains = []
    if language_domains:
        for _lang_code, lang_domains in language_domains.items():
            trusted_domains.append(
                f'{domain_scheme}://{lang_domains[domain_index_match]}')

    del language_domains[h.lang()]

    jwt_secret = config.get('ckanext.language_domains.secret')
    token = None
    if jwt_secret:
        token_data = {
            'user_id': g.userobj.id,
            'exp': datetime.datetime.now(datetime.timezone.utc) +
            datetime.timedelta(minutes=10),
            "iat": datetime.datetime.now(datetime.timezone.utc)
        }
        token = jwt.encode(token_data, jwt_secret, algorithm='HS256')

    return render('user/language_login_sender.html',
                  {'language_domains': language_domains,
                   'domain_scheme': domain_scheme,
                   'trusted_domains': trusted_domains,
                   'token': token,
                   'redirect': came_from or '/'})


@language_domain_views.route('/user/language_domain_login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':

        default_domain = config.get('ckan.site_url', '')
        uri_parts = urlsplit(default_domain)
        domain_scheme = uri_parts.scheme

        language_domains = config.get('ckanext.language_domains.domain_map', '')
        trusted_domains = []
        if language_domains:
            language_domains = json.loads(language_domains)

            current_domain = request.url
            uri_parts = urlsplit(current_domain)
            current_domain = uri_parts.netloc
            domain_index_match = _get_domain_index(current_domain, language_domains)

            for _lang_code, lang_domains in language_domains.items():
                trusted_domains.append(
                    f'{domain_scheme}://{lang_domains[domain_index_match]}')

        return render('user/language_login_receiver.html',
                      {'trusted_domains': trusted_domains})

    else:

        post_data = parse_params(request.form)

        if (
          not post_data.get('session_user') or
          not post_data.get('session_token') or
          not post_data.get('target_domain') or
          not post_data.get('target_language')
        ):
            return _finish(400,
                           {'error': _('Invalid request'),
                            'success': False},
                           content_type='json')

        if (
            not str(request.url).startswith(
                # type_ignore_reason: incomplete typing
                post_data['target_domain']) or  # type: ignore
            post_data['target_language'] != h.lang()
        ):
            return _finish(400,
                           {'error': _('Invalid request for language domain'),
                            'success': False},
                           content_type='json')

        jwt_secret = config.get('ckanext.language_domains.secret')
        if not jwt_secret:
            return _finish(500,
                           {'error': _('Cannot decipher token'),
                            'success': False},
                           content_type='json')

        token = post_data['session_token']
        token_data = {}

        try:
            # type_ignore_reason: incomplete typing
            token_data = jwt.decode(
                token, jwt_secret, algorithms=['HS256'])  # type: ignore
        except jwt.ExpiredSignatureError:
            return _finish(400,
                           {'error': _('Expired token'),
                            'success': False},
                           content_type='json')
        except jwt.InvalidTokenError:
            return _finish(400,
                           {'error': _('Invalid token'),
                            'success': False},
                           content_type='json')

        userobj = User.get(token_data.get('user_id'))

        if not userobj or userobj.name != post_data['session_user']:
            return _finish(404,
                           {'error': _('User not found'),
                            'success': False},
                           content_type='json')

        g.user = userobj.name
        g.userobj = userobj
        login_user(userobj, force=True, fresh=True)

        return _finish_ok({'success': True})


@language_domain_views.route('/user/_logout', methods=['GET'])
@forced_came_from
def logout_core():
    return h.redirect_to('language_domains.logout_master')


@language_domain_views.route('/user/domain_logout', methods=['GET', 'POST'])
def logout_master():
    if request.method == 'GET':
        if not g.user:
            return h.redirect_to('user.login')

        came_from = request.args.get('_came_from', '')

        default_domain = config.get('ckan.site_url', '')
        uri_parts = urlsplit(default_domain)
        domain_scheme = uri_parts.scheme

        language_domains = config.get('ckanext.language_domains.domain_map', '')
        if not language_domains:
            language_domains = {}
        else:
            language_domains = json.loads(language_domains)

        current_domain = request.url
        uri_parts = urlsplit(current_domain)
        current_domain = uri_parts.netloc
        domain_index_match = _get_domain_index(current_domain, language_domains)

        trusted_domains = []
        if language_domains:
            for _lang_code, lang_domains in language_domains.items():
                trusted_domains.append(
                    f'{domain_scheme}://{lang_domains[domain_index_match]}')

        del language_domains[h.lang()]

        jwt_secret = config.get('ckanext.language_domains.secret')
        token = None
        if jwt_secret:
            token_data = {
                'user_id': g.userobj.id,
                'exp': datetime.datetime.now(datetime.timezone.utc) +
                datetime.timedelta(minutes=10),
                "iat": datetime.datetime.now(datetime.timezone.utc)
            }
            token = jwt.encode(token_data, jwt_secret, algorithm='HS256')

        return render('user/language_logout_sender.html',
                      {'language_domains': language_domains,
                       'domain_scheme': domain_scheme,
                       'trusted_domains': trusted_domains,
                       'token': token,
                       'redirect': came_from or h.url_for('user.logged_out_page')})

    post_data = parse_params(request.form)

    if not g.user:
        logout_user()
        return _finish_ok({'success': True})

    if (
        not post_data.get('session_user') or
        not post_data.get('session_token')
    ):
        return _finish(400, {'error': _('Invalid request'),
                             'success': False}, content_type='json')

    jwt_secret = config.get('ckanext.language_domains.secret')
    if not jwt_secret:
        return _finish(500, {'error': _('Cannot decipher token'),
                             'success': False}, content_type='json')

    token = post_data['session_token']
    token_data = {}

    try:
        # type_ignore_reason: incomplete typing
        token_data = jwt.decode(
            token, jwt_secret, algorithms=['HS256'])  # type: ignore
    except jwt.ExpiredSignatureError:
        return _finish(400, {'error': _('Expired token'),
                             'success': False}, content_type='json')
    except jwt.InvalidTokenError:
        return _finish(400, {'error': _('Invalid token'),
                             'success': False}, content_type='json')

    userobj = User.get(token_data.get('user_id'))

    if not userobj or userobj.name != post_data['session_user']:
        return _finish(404, {'error': _('User not found'),
                             'success': False}, content_type='json')

    g.user = None
    g.userobj = None
    logout_user()

    return _finish_ok({'success': True})


@language_domain_views.route('/user/language_domain_logout', methods=['GET', 'POST'])
def logout():
    if request.method == 'GET':

        default_domain = config.get('ckan.site_url', '')
        uri_parts = urlsplit(default_domain)
        domain_scheme = uri_parts.scheme

        language_domains = config.get('ckanext.language_domains.domain_map', '')
        trusted_domains = []
        if language_domains:
            language_domains = json.loads(language_domains)

            current_domain = request.url
            uri_parts = urlsplit(current_domain)
            current_domain = uri_parts.netloc
            domain_index_match = _get_domain_index(current_domain, language_domains)

            for _lang_code, lang_domains in language_domains.items():
                trusted_domains.append(
                    f'{domain_scheme}://{lang_domains[domain_index_match]}')

        return render('user/language_logout_receiver.html',
                      {'trusted_domains': trusted_domains})

    post_data = parse_params(request.form)

    if not g.user:
        logout_user()
        return _finish_ok({'success': True})

    if (
        not post_data.get('session_user') or
        not post_data.get('session_token') or
        not post_data.get('target_domain') or
        not post_data.get('target_language')
    ):
        return _finish(400, {'error': _('Invalid request'),
                             'success': False}, content_type='json')

    if (
        not str(request.url).startswith(
            # type_ignore_reason: incomplete typing
            post_data['target_domain']) or  # type: ignore
        post_data['target_language'] != h.lang()
    ):
        return _finish(400, {'error': _('Invalid request for language domain'),
                             'success': False}, content_type='json')

    jwt_secret = config.get('ckanext.language_domains.secret')
    if not jwt_secret:
        return _finish(500, {'error': _('Cannot decipher token'),
                             'success': False}, content_type='json')

    token = post_data['session_token']
    token_data = {}

    try:
        # type_ignore_reason: incomplete typing
        token_data = jwt.decode(
            token, jwt_secret, algorithms=['HS256'])  # type: ignore
    except jwt.ExpiredSignatureError:
        return _finish(400, {'error': _('Expired token'),
                             'success': False}, content_type='json')
    except jwt.InvalidTokenError:
        return _finish(400, {'error': _('Invalid token'),
                             'success': False}, content_type='json')

    userobj = User.get(token_data.get('user_id'))

    if not userobj or userobj.name != post_data['session_user']:
        return _finish(404, {'error': _('User not found'),
                             'success': False}, content_type='json')

    g.user = None
    g.userobj = None
    logout_user()

    return _finish_ok({'success': True})
