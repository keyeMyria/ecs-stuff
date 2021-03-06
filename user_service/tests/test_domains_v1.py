__author__ = 'ufarooqi'
from user_service.user_app import app
from user_service.common.tests.conftest import *
from user_service.common.models.user import Role
from common_functions import *


# Test GET operation of Domain API
def test_domain_service_get(access_token_first, user_first, user_second, domain_first, domain_second):

    # Get info of domain when no domain_id is provided
    response, status_code = domain_api(access_token_first)
    assert status_code == 401

    # Logged-in user getting info of a domain which doesn't exist
    response, status_code = domain_api(access_token_first, user_first.domain_id + 1000)
    assert status_code == 404

    # Logged-in user trying to get info of domain which different than its own domain
    response, status_code = domain_api(access_token_first, user_second.domain_id)
    assert status_code == 401

    # Logged-in user getting info of a domain
    response, status_code = domain_api(access_token_first, user_first.domain_id)
    assert status_code == 200
    assert response['domain']['id'] == domain_first.id
    assert response['domain']['name'] == domain_first.name

    user_first.role_id = Role.get_by_name('TALENT_ADMIN').id
    db.session.commit()

    # Logged-in user trying to get info of domain which different than its own domain
    response, status_code = domain_api(access_token_first, domain_second.id)
    assert status_code == 200
    assert response['domain']['id'] == domain_second.id
    assert response['domain']['name'] == domain_second.name

    # Logged-in user trying to get info of all domains
    response, status_code = domain_api(access_token_first)
    assert status_code == 200
    assert len(response['domains']) >= 2


# Test DELETE operation of domain API
def test_domain_service_delete(access_token_first, user_first, domain_first, domain_second):

    # Logged-in user trying to delete a domain
    response, status_code = domain_api(access_token_first, domain_first.id, action='DELETE')
    assert status_code == 401

    user_first.role_id = Role.get_by_name('TALENT_ADMIN').id
    db.session.commit()

    # Logged-in user trying to delete a domain where domain is not provided
    response, status_code = domain_api(access_token_first, action='DELETE')
    assert status_code == 400

    # Logged-in user trying to delete a non-existing domain
    response, status_code = domain_api(access_token_first, domain_first.id + 1000, action='DELETE')
    assert status_code == 404

    # Logged-in user trying to delete a domain
    response, status_code = domain_api(access_token_first, domain_second.id, action='DELETE')
    assert status_code == 200
    assert response['deleted_domain']['id'] == domain_second.id

    # Refresh domain object
    db.session.refresh(domain_second)
    db.session.commit()

    # Check either domain has been deleted/disabled or not
    assert domain_second.is_disabled == 1

    # Check either users of that domain has been disabled or not
    users = User.query.filter(User.domain_id == domain_second.id).all()
    for user in users:
        assert user.is_disabled == 1


# Test PUT operation of domain API
def test_domain_service_put(access_token_first, user_first, domain_first, domain_second):

    data = {'name': gen_salt(6), 'expiration': gen_salt(6)}

    # Logged-in user trying to update a domain
    response, status_code = domain_api(access_token_first, domain_first.id, data=data, action='PUT')
    assert status_code == 401

    user_first.role_id = Role.get_by_name('DOMAIN_ADMIN').id
    db.session.commit()

    # Logged-in user trying to update a non-existing domain
    response, status_code = domain_api(access_token_first, domain_first.id + 1000, data=data, action='PUT')
    assert status_code == 404

    # Logged-in user trying to update a domain with empty request body
    response, status_code = domain_api(access_token_first, domain_first.id, action='PUT')
    assert status_code == 400

    # Logged-in user trying to update a domain with invalid expiration time
    response, status_code = domain_api(access_token_first, domain_first.id, data=data, action='PUT')
    assert status_code == 400

    data['expiration'] = str(datetime.now().replace(microsecond=0))

    # Logged-in user trying to update a domain
    response, status_code = domain_api(access_token_first, domain_first.id, data=data, action='PUT')
    assert status_code == 200
    assert response['updated_domain']['id'] == domain_first.id

    # Refresh domain object
    db.session.refresh(domain_first)
    db.session.commit()

    assert domain_first.name == data['name']
    assert str(domain_first.expiration) == data['expiration']

    # Logged-in user trying to update a domain
    response, status_code = domain_api(access_token_first, domain_second.id, data=data, action='PUT')
    assert status_code == 401

    user_first.role_id = Role.get_by_name('TALENT_ADMIN').id
    db.session.commit()

    data['name'] = gen_salt(6)

    # Logged-in user trying to update a domain
    response, status_code = domain_api(access_token_first, domain_second.id, data=data, action='PUT')
    assert status_code == 200
    assert response['updated_domain']['id'] == domain_second.id

    # Refresh domain object
    db.session.refresh(domain_second)
    db.session.commit()

    assert domain_second.name == data['name']
    assert str(domain_second.expiration) == data['expiration']


# Test POST operation of domain API
def test_domain_service_post(access_token_first, user_first, domain_first):

    first_domain = {
        'name': '',
        'expiration': gen_salt(6),
        'default_culture_id': '1000'
    }

    second_domain = {
        'name': gen_salt(6),
        'expiration': str(datetime.now().replace(microsecond=0)),
        'dice_company_id': 1
    }

    data = {'domains': [first_domain, second_domain]}

    # Logged-in user trying to add new domains
    response, status_code = domain_api(access_token_first, data=data, action='POST')
    assert status_code == 401

    user_first.role_id = Role.get_by_name('TALENT_ADMIN').id
    db.session.commit()

    # Logged-in user trying to add new domains with empty request body
    response, status_code = domain_api(access_token_first, action='POST')
    assert status_code == 400

    # Logged-in user trying to add new domains with empty name
    response, status_code = domain_api(access_token_first, data=data, action='POST')
    assert status_code == 400

    first_domain['name'] = gen_salt(6)

    # Logged-in user trying to add new domains with non-existing culture
    response, status_code = domain_api(access_token_first, data=data, action='POST')
    assert status_code == 400

    del first_domain['default_culture_id']

    # Logged-in user trying to add new domains with invalid expiration time
    response, status_code = domain_api(access_token_first, data=data, action='POST')
    assert status_code == 400

    first_domain['expiration'] = str(datetime.now().replace(microsecond=0))
    first_domain['name'] = domain_first.name

    # Logged-in user trying to add new domains where domain name already exists
    response, status_code = domain_api(access_token_first, data=data, action='POST')
    assert status_code == 400

    first_domain['name'] = gen_salt(6)

    # Logged-in user trying to add new domains with empty request body
    response, status_code = domain_api(access_token_first, data=data, action='POST')
    assert status_code == 200
    assert len(response['domains']) == 2
    db.session.commit()

    first_domain_object = Domain.query.get(response['domains'][0])
    second_domain_object = Domain.query.get(response['domains'][1])

    assert first_domain_object.name == data['domains'][0]['name']
    assert str(first_domain_object.expiration) == data['domains'][0]['expiration']

    assert second_domain_object.name == data['domains'][1]['name']
    assert str(second_domain_object.expiration) == data['domains'][1]['expiration']
    assert second_domain_object.dice_company_id == data['domains'][1]['dice_company_id']

    # Remove these temporary domains from domain table
    first_domain_object.delete()
    second_domain_object.delete()


# Test POST operation of domain API
def test_domain_service_patch(access_token_first, user_first, domain_first, domain_second):
    assert not domain_first.is_test_domain
    data = {'is_test_domain': 1}
    # Logged-in user trying to add new domains without having required role.
    response, status_code = domain_api(access_token_first, domain_id=domain_first.id, data=data, action='PATCH')
    assert status_code == codes.UNAUTHORIZED, response

    # Logged-in user trying to add new domains with required role.
    user_first.role_id = Role.get_by_name('DOMAIN_ADMIN').id
    db.session.commit()

    response, status_code = domain_api(access_token_first, domain_id=domain_first.id, data=data, action='PATCH')
    assert status_code == codes.OK, response

    db.session.commit()
    assert domain_first.is_test_domain

    # Mark is_test_domain as 0
    data = {'is_test_domain': 0}
    response, status_code = domain_api(access_token_first, domain_id=domain_first.id, data=data, action='PATCH')
    assert status_code == codes.OK, response
    db.session.commit()
    assert not domain_first.is_test_domain

    # Test with invalid value
    data = {'is_test_domain': gen_salt(6)}
    response, status_code = domain_api(access_token_first, domain_id=domain_first.id, data=data, action='PATCH')
    assert status_code == codes.BAD, response

    # Test updating domain of some other user without appropriate role
    data = {'is_test_domain': 1}
    response, status_code = domain_api(access_token_first, domain_id=domain_second.id, data=data, action='PATCH')
    assert status_code == codes.UNAUTHORIZED, response

    # Test updating domain of some other user with valid role
    assert not domain_second.is_test_domain
    user_first.role_id = Role.get_by_name('TALENT_ADMIN').id
    db.session.commit()
    data = {'is_test_domain': True}
    response, status_code = domain_api(access_token_first, domain_id=domain_second.id, data=data, action='PATCH')
    assert status_code == codes.OK, response
    db.session.commit()
    assert domain_second.is_test_domain
