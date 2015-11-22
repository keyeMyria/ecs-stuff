__author__ = 'ufarooqi'
import requests
import json
from candidate_pool_service.candidate_pool_app import db
from candidate_pool_service.common.models.user import DomainRole

USER_SERVICE_ENDPOINT = 'http://127.0.0.1:8004/%s'
USER_ROLES = USER_SERVICE_ENDPOINT % 'users/%s/roles'
USER_ROLES_VERIFY = USER_SERVICE_ENDPOINT % 'roles/verify'
USER_DOMAIN_ROLES = USER_SERVICE_ENDPOINT % 'domain/%s/roles'
DOMAIN_GROUPS = USER_SERVICE_ENDPOINT % 'domain/%s/groups'
USER_GROUPS = USER_SERVICE_ENDPOINT % 'groups/%s/users'
UPDATE_PASSWORD = USER_SERVICE_ENDPOINT % 'users/%s/update_password'

USER_API = USER_SERVICE_ENDPOINT % 'users'
DOMAIN_API = USER_SERVICE_ENDPOINT % 'domains'


def user_scoped_roles(access_token, user_id, test_roles=None, action="GET", false_case=False):
    if test_roles:
        test_role_first = test_roles[0]
        test_role_second = test_roles[1]
    headers = {'Authorization': 'Bearer %s' % access_token}
    if action == "GET":
        response = requests.get(USER_ROLES % user_id, headers=headers)
        if response.status_code == 200:
            response = json.loads(response.text)
            return response.get('roles')
        return response.status_code
    elif action == "POST":
        headers['content-type'] = 'application/json'
        test_role_second = DomainRole.get_by_name(test_role_second)
        if false_case:
            data = {'roles': [int(test_role_second.id) + 1]}
        else:
            data = {'roles': [test_role_first, test_role_second.id]}
        response = requests.post(USER_ROLES % user_id, headers=headers, data=json.dumps(data))
        return response.status_code
    elif action == "DELETE":
        headers['content-type'] = 'application/json'
        data = {'roles': [test_role_first, DomainRole.get_by_name(test_role_second).id]}
        response = requests.delete(USER_ROLES % user_id, headers=headers, data=json.dumps(data))
        return response.status_code


def get_roles_of_domain(access_token, domain_id):
    headers = {'Authorization': 'Bearer %s' % access_token}
    response = requests.get(USER_DOMAIN_ROLES % domain_id, headers=headers)
    if response.status_code == 200:
        response = json.loads(response.text)
        domain_roles = response.get('roles') or []
        return [domain_role.get('name') for domain_role in domain_roles]
    return response.status_code


def verify_user_scoped_role(user, role):
    user_id = user.get_id()
    response = json.loads(requests.get(USER_ROLES_VERIFY, params={"role": role, "user_id": user_id}).text)
    return response.get('success')


def domain_groups(access_token, domain_id, test_groups=None, action='GET'):
    headers = {'Authorization': 'Bearer %s' % access_token}
    if action == "GET":
        response = requests.get(DOMAIN_GROUPS % domain_id, headers=headers, params={'domain_id': domain_id})
        if response.status_code == 200:
            response = json.loads(response.text)
            return [group['name'] for group in response.get('user_groups')]
        return response.status_code
    elif action == "POST":
        headers['content-type'] = 'application/json'
        data = {'groups': [{'name': group, 'description': group} for group in test_groups]}
        response = requests.post(DOMAIN_GROUPS % domain_id, headers=headers, data=json.dumps(data))
        db.session.commit()
        return response.status_code
    elif action == "DELETE":
        headers['content-type'] = 'application/json'
        data = {'groups': [group for group in test_groups]}
        response = requests.delete(DOMAIN_GROUPS % domain_id, headers=headers, data=json.dumps(data))
        return response.status_code


def user_groups(access_token, group_id=None, user_ids=[], action='GET'):
    headers = {'Authorization': 'Bearer %s' % access_token}
    if action == "GET":
        response = requests.get(USER_GROUPS % group_id, headers=headers)
        if response.status_code == 200:
            response = json.loads(response.text)
            return [user['id'] for user in response.get('users')]
        return response.status_code
    elif action == "POST":
        headers['content-type'] = 'application/json'
        data = {'user_ids': user_ids}
        response = requests.post(USER_GROUPS % group_id, headers=headers, data=json.dumps(data))
        return response.status_code


def update_password(access_token, user_id, old_password, new_password):
    headers = {'Authorization': 'Bearer %s' % access_token, 'content-type': 'application/json'}
    data = {"old_password": old_password, "new_password": new_password}
    response = requests.post(url=UPDATE_PASSWORD % user_id, headers=headers, data=json.dumps(data))
    return response.status_code


def user_api(access_token, user_id='', data='', action='GET'):
    headers = {'Authorization': 'Bearer %s' % access_token}
    if action == 'GET':
        if user_id:
            response = requests.get(url=USER_API + '/%s' % user_id, headers=headers)
            if response.ok:
                response = json.loads(response.text)
                return response.get('user').get('id')
            return response.status_code
        else:
            response = requests.get(url=USER_API, headers=headers)
            if response.ok:
                response = json.loads(response.text)
                return response.get('users')
            return response.status_code
    elif action == 'DELETE':
        response = requests.delete(url=USER_API + '/%s' % user_id, headers=headers)
        if response.ok:
            response = json.loads(response.text)
            return response.get('deleted_user').get('id')
        return response.status_code
    elif action == 'PUT':
        headers['content-type'] = 'application/json'
        response = requests.put(url=USER_API + '/%s' % user_id, headers=headers, data=json.dumps(data))
        if response.ok:
            response = json.loads(response.text)
            return response.get('updated_user').get('id')
        return response.status_code
    elif action == 'POST':
        headers['content-type'] = 'application/json'
        response = requests.post(url=USER_API, headers=headers, data=json.dumps(data))
        if response.ok:
            response = json.loads(response.text)
            return response.get('users')
        return response.status_code


def domain_api(access_token, domain_id='', data='', action='GET'):
    headers = {'Authorization': 'Bearer %s' % access_token}
    if action == 'GET':
        url = DOMAIN_API + '/%s' % domain_id if domain_id else DOMAIN_API
        response = requests.get(url=url, headers=headers)
        if response.ok:
            response = json.loads(response.text)
            return response.get('domain')
        return response.status_code
    elif action == 'DELETE':
        url = DOMAIN_API + '/%s' % domain_id if domain_id else DOMAIN_API
        response = requests.delete(url=url, headers=headers)
        if response.ok:
            response = json.loads(response.text)
            return response.get('deleted_domain').get('id')
        return response.status_code
    elif action == 'PUT':
        headers['content-type'] = 'application/json'
        response = requests.put(url=DOMAIN_API + '/%s' % domain_id, headers=headers, data=json.dumps(data))
        if response.ok:
            response = json.loads(response.text)
            return response.get('updated_domain').get('id')
        return response.status_code
    elif action == 'POST':
        headers['content-type'] = 'application/json'
        response = requests.post(url=DOMAIN_API, headers=headers, data=json.dumps(data))
        if response.ok:
            response = json.loads(response.text)
            return response.get('domains')
        return response.status_code
