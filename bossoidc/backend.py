# Copyright 2016 The Johns Hopkins University Applied Physics Laboratory
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#    http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import datetime
from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.settings import import_from_string

from django.utils.translation import ugettext as _
from djangooidc.backends import OpenIdConnectBackend as DOIDCBackend

from bossutils.logger import BossLogger
from bossutils.keycloak import KeyCloakClient
import json

LOG = BossLogger().logger

def load_user_roles(user, roles):
    pass

LOAD_USER_ROLES = getattr(settings, 'LOAD_USER_ROLES', None)
if LOAD_USER_ROLES is None:
    # DP NOTE: had issues with import_from_string loading bossoidc.backend.load_user_roles
    LOAD_USER_ROLES_FUNCTION = load_user_roles
else:
    LOAD_USER_ROLES_FUNCTION = import_from_string(LOAD_USER_ROLES, 'LOAD_USER_ROLES')


def resolve_username(username):
    return username[:30] # Django User username is 30 character limited

def update_user_data(user, token):
    pass

def get_user_by_id(request, id_token):
    """ Taken from djangooidc.backends.OpenIdConnectBackend and made common for
    drf-oidc-auth to make use of the same create user functionality
    """
    UserModel = get_user_model()
    username = resolve_username(id_token['preferred_username'])

    # Some OP may actually choose to withhold some information, so we must test if it is present
    openid_data = {'last_login': datetime.datetime.now()}
    if 'first_name' in id_token.keys():
        openid_data['first_name'] = id_token['first_name']
    if 'given_name' in id_token.keys():
        openid_data['first_name'] = id_token['given_name']
    if 'christian_name' in id_token.keys():
        openid_data['first_name'] = id_token['christian_name']
    if 'family_name' in id_token.keys():
        openid_data['last_name'] = id_token['family_name']
    if 'last_name' in id_token.keys():
        openid_data['last_name'] = id_token['last_name']
    if 'email' in id_token.keys():
        openid_data['email'] = id_token['email']

    # Note that this could be accomplished in one try-except clause, but
    # instead we use get_or_create when creating unknown users since it has
    # built-in safeguards for multiple threads.
    if getattr(settings, 'OIDC_CREATE_UNKNOWN_USER', True):
        args = {UserModel.USERNAME_FIELD: username, 'defaults': openid_data, }
        user, created = UserModel.objects.update_or_create(**args)
    else:
        try:
            user = UserModel.objects.get_by_natural_key(username)
        except UserModel.DoesNotExist:
            msg = _('Invalid Authorization header. User not found.')
            raise AuthenticationFailed(msg)

    # PM TODO : Currently getting the roles from the library. Change this to get it from the token instead
    kc = KeyCloakClient('BOSS')
    kc.login()
    resp = kc.get_realm_roles(username)
    roles = [r['name'] for r in resp]

    user.is_staff = 'admin' in roles or 'superuser' in roles
    user.is_superuser = 'superuser' in roles

    LOAD_USER_ROLES_FUNCTION(user, roles)
    update_user_data(user, id_token)

    user.save()
    return user

class OpenIdConnectBackend(DOIDCBackend):
    def authenticate(self, request=None, **kwargs):
        user = None
        if not kwargs or 'sub' not in kwargs.keys():
            return user

        user = get_user_by_id(None, kwargs)
        return user
