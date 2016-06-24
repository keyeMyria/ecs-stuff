"""
Author: Zohaib Ijaz <mzohaib.qc@gmail.com>

This module contains fixtures to be used in tests.

Some fixtures are created twice. First one with 'user_first' as owner and those that
are postfix with  '_second' are owned by 'user_second'. 'user_first' belongs to domain 1 and
'user_second' belongs to another domain say domain 2.

A user can update or delete objects that are owned by a user that is from same domain. so there
are some fixture that are postfixed with '_same_domain', actually belong to domain 1
but user is different.

"""
import pytest
import time
from redo import retry
from requests import codes

from ..test_config_manager import load_test_config
from ..utils.test_utils import (create_candidate, delete_candidate,
                                create_smartlist, delete_smartlist, delete_talent_pool,
                                create_talent_pools, create_talent_pipelines, get_smartlist_candidates, get_talent_pool,
                                search_candidates)


test_config = load_test_config()


@pytest.fixture(scope='session')
def token_first():
    """
    Au Authentication token for user_first.
    """
    return test_config['USER_FIRST']['token']


@pytest.fixture(scope='session')
def token_same_domain():
    """
    Authentication token for user that belongs to same domain as user_first.
    """
    return test_config['USER_SAME_DOMAIN']['token']


@pytest.fixture(scope='session')
def token_second():
    """
     Authentication token for user_second.
    """
    return test_config['USER_SECOND']['token']


@pytest.fixture(scope='session')
def user_first():
    """
    This fixture will be used to get user from UserService using id from config.
    :return: user dictionary object
    """
    user_id = test_config['USER_FIRST']['user_id']
    return {'id': user_id}


@pytest.fixture(scope='session')
def user_second():
    """
    This fixture will be used to get user from UserService using id from config.
    :return: user dictionary object
    """
    user_id = test_config['USER_SECOND']['user_id']
    return {'id': user_id}


@pytest.fixture(scope='session')
def user_same_domain():
    """
    This fixture will be used to get user from UserService using id from config.
    :return: user dictionary object
    """
    user_id = test_config['USER_SAME_DOMAIN']['user_id']
    return {'id': user_id}


@pytest.fixture(scope='function')
def candidate_first(talent_pool, token_first):
    """
    This fixture created a test candidate in domain first and it will be deleted
    after test has run.
    :param request: request object
    :param talent_pool: talent pool dict object associated to user_first
    :param token_first: auth token for  first user
    """
    response = create_candidate(talent_pool['id'], token_first)
    candidate_id = response['candidates'][0]['id']
    response = retry(search_candidates, max_sleeptime=60, retry_exceptions=(AssertionError,),
                     args=([candidate_id], token_first))
    candidate = response['candidates'][0]

    return candidate


@pytest.fixture(scope='function')
def candidate_same_domain(request, talent_pool, token_same_domain):
    """
    This fixture created a candidate in domain first  and it will be deleted
    after test has run.
    :param request: request object
    :param talent_pool: talent pool dict object
    :param token_same_domain: authentication token
    """
    response = create_candidate(talent_pool['id'], token_same_domain)
    candidate_id = response['candidates'][0]['id']
    response = retry(search_candidates, max_sleeptime=60, retry_exceptions=(AssertionError,),
                     args=([candidate_id], token_same_domain))
    candidate = response['candidates'][0]

    def tear_down():
        delete_candidate(candidate_id, token_same_domain,
                         expected_status=(codes.NO_CONTENT, codes.NOT_FOUND))

    request.addfinalizer(tear_down)
    return candidate


@pytest.fixture(scope='function')
def candidate_second(request, token_second, talent_pool_second):
    """
    This fixture creates a test candidate in domain second and it will be deleted
    after test has run.
    :param request: request object
    :param token_second: authentication token for user_second
    :param talent_pool_second: talent pool dict object from domain second
    """
    response = create_candidate(talent_pool_second['id'], token_second)
    candidate_id = response['candidates'][0]['id']
    response = retry(search_candidates, sleeptime=3, retry_exceptions=(AssertionError,),
                     args=([candidate_id], token_second))
    candidate = response['candidates'][0]

    def tear_down():
        delete_candidate(candidate_id, token_second,
                         expected_status=(codes.NO_CONTENT, codes.NOT_FOUND))

    request.addfinalizer(tear_down)
    return candidate


@pytest.fixture(scope='function')
def smartlist_first(request, token_first, candidate_first, talent_pipeline):
    """
    This fixture creates a smartlist that contains a candidate from domain_first.
    :param request: request object
    :param candidate_first: candidate object
    :param token_first: access token for user_first
    :param talent_pipeline: talent_pipeline object for user_first
    :return: smartlist objects (dict)
    """
    candidate_ids = [candidate_first['id']]
    time.sleep(10)
    smartlist = create_smartlist(candidate_ids, talent_pipeline['id'], token_first)['smartlist']
    smartlist_id = smartlist['id']
    retry(get_smartlist_candidates, sleeptime=3, attempts=50, sleepscale=1, retry_exceptions=(AssertionError,),
          args=(smartlist_id, token_first), kwargs={'count': 1})

    def tear_down():
        delete_smartlist(smartlist_id, token_first,
                         expected_status=(codes.OK, codes.NOT_FOUND))

    request.addfinalizer(tear_down)
    return smartlist


@pytest.fixture(scope='function')
def smartlist_second(request, token_second, candidate_second, talent_pipeline_second):
    """
    This fixture creates a smartlist that is associated contains a candidate from domain_second.
    :param request: request object
    :param token_second: access token for user_second
    :param candidate_second: candidate object
    :param talent_pipeline_second: talent_pipeline associated with user_second
    :return: smartlist object
    """
    candidate_ids = [candidate_second['id']]
    time.sleep(10)
    smartlist = create_smartlist(candidate_ids, talent_pipeline_second['id'], token_second)['smartlist']
    smartlist_id = smartlist['id']
    retry(get_smartlist_candidates, sleeptime=3, attempts=50, sleepscale=1, retry_exceptions=(AssertionError,),
          args=(smartlist_id, token_second), kwargs={'count': 1})

    def tear_down():
        delete_smartlist(smartlist_id, token_second,
                         expected_status=(codes.OK, codes.NOT_FOUND))
    request.addfinalizer(tear_down)
    return smartlist


@pytest.fixture(scope='function')
def smartlist_same_domain(request, token_same_domain, candidate_same_domain, talent_pipeline):
    """
    This fixture creates a smartlist that belongs to "user_same_domain"
    :param request: request object
    :param token_same_domain: auth token for user_same_domain from domain_first
    :param candidate_same_domain: candidate from domain as of user_same_domain
    :param talent_pipeline: talent pipeline associated with user_first
    :return: smartlist object
    """
    candidate_ids = [candidate_same_domain['id']]
    time.sleep(10)
    smartlist = create_smartlist(candidate_ids, talent_pipeline['id'], token_same_domain)['smartlist']
    smartlist_id = smartlist['id']
    retry(get_smartlist_candidates, sleeptime=3, attempts=50, sleepscale=1, retry_exceptions=(AssertionError,),
          args=(smartlist_id, token_same_domain), kwargs={'count': 1})

    def tear_down():
        delete_smartlist(smartlist_id, token_same_domain,
                         expected_status=(codes.OK, codes.NOT_FOUND))

    request.addfinalizer(tear_down)
    return smartlist


@pytest.fixture(scope='function')
def talent_pool(request, token_first):
    """
    This fixture created a talent pool that is associated to user_first
    :param request: request object
    :param token_first: authentication token for user_first
    """
    talent_pools = create_talent_pools(token_first)
    talent_pool_id = talent_pools['talent_pools'][0]
    talent_pool_obj = get_talent_pool(talent_pool_id, token_first)['talent_pool']

    def tear_down():
        delete_talent_pool(talent_pool_id, token_first,
                           expected_status=(codes.OK, codes.NOT_FOUND))

    request.addfinalizer(tear_down)
    return talent_pool_obj


@pytest.fixture(scope='function')
def talent_pool_second(request, token_second):
    """
    This fixture created a talent pool that is associated to user_second of domain_second
    :param request: request object
    :param token_second: authentication token for user_second
    """
    talent_pools = create_talent_pools(token_second)
    talent_pool_id = talent_pools['talent_pools'][0]
    talent_pool_obj = get_talent_pool(talent_pool_id, token_second)['talent_pool']

    def tear_down():
        delete_talent_pool(talent_pool_id, token_second,
                           expected_status=(codes.OK, codes.NOT_FOUND))

    request.addfinalizer(tear_down)
    return talent_pool_obj


@pytest.fixture(scope='function')
def talent_pipeline(request, token_first, talent_pool):
    """
    This fixture creates a talent pipeline that is associated to user_first of domain_first
    :param request: request object
    :param token_first: authentication token for user_first
    :param talent_pool: talent_pool associated with user_first
    """
    talent_pipelines = create_talent_pipelines(token_first, talent_pool['id'])
    talent_pipeline_id = talent_pipelines['talent_pipelines'][0]

    return {'id': talent_pipeline_id}


@pytest.fixture(scope='function')
def talent_pipeline_second(request, token_second, talent_pool_second):
    """
    This fixture creates a talent pipeline that is associated to user_second of domain_second
    :param request: request object
    :param token_second: authentication token for user_second
    :param talent_pool_second: talent_pool associated with user_second
    """
    talent_pipelines = create_talent_pipelines(token_second, talent_pool_second['id'])
    talent_pipeline_id = talent_pipelines['talent_pipelines'][0]

    return {'id': talent_pipeline_id}
