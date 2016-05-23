"""
Test cases for candidate CRUD operations
"""
# Candidate Service app instance
from candidate_service.candidate_app import app

import sys
from requests.status_codes import codes as http_status_codes

# Conftest
from candidate_service.common.tests.conftest import *

# Custom Errors
from candidate_service.custom_error_codes import CandidateCustomErrors as custom_errors

# Helper functions
from helpers import AddUserRoles
from candidate_service.tests.api.candidate_sample_data import generate_single_candidate_data
from candidate_service.common.routes import CandidateApiUrl, UserServiceApiUrl
from candidate_service.common.utils.test_utils import send_request, response_info


class TestCreateCandidate(object):
    SOURCE_URL = UserServiceApiUrl.DOMAIN_SOURCES
    CANDIDATE_URL = CandidateApiUrl.CANDIDATE
    CANDIDATES_URL = CandidateApiUrl.CANDIDATES

    def test_add_candidate_with_invalid_source_id(self, user_first, access_token_first, talent_pool):
        """
        Test: Add a candidate using an invalid source ID
        """
        AddUserRoles.add(user_first)

        # Create candidate
        data = {'candidates': [{'source_id': sys.maxint, 'talent_pool_ids': {'add': [talent_pool.id]}}]}
        create_resp = send_request('post', self.CANDIDATES_URL, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == http_status_codes.bad_request
        assert create_resp.json()['error']['code'] == custom_errors.INVALID_SOURCE_ID

    def test_add_candidate_with_source_id_not_belonging_to_domain(self, user_first, access_token_first,
                                                                  talent_pool, access_token_second):
        """
        Test: Add a candidate using an source ID not belonging to candidate's domain
        """
        AddUserRoles.add(user_first)

        # Create source in user_second's domain
        source_data = {"source": {"description": "testing_{}".format(str(uuid.uuid4())[:5])}}
        resp = send_request('post', self.SOURCE_URL, access_token_second, source_data)
        print response_info(resp)

        source_id = resp.json()['source']['id']

        # Create candidate
        data = {'candidates': [{'source_id': source_id, 'talent_pool_ids': {'add': [talent_pool.id]}}]}
        create_resp = send_request('post', self.CANDIDATES_URL, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == http_status_codes.bad_request
        assert create_resp.json()['error']['code'] == custom_errors.INVALID_SOURCE_ID

    def test_add_candidate_with_source_id(self, user_first, access_token_first, talent_pool):
        """
        Test: Add candidate with valid source ID
        """
        AddUserRoles.add_and_get(user_first)

        # Add source to candidate's domain
        source_data = {"source": {"description": "testing_{}".format(str(uuid.uuid4())[:5])}}
        resp = send_request('post', self.SOURCE_URL, access_token_first, source_data)
        print response_info(resp)

        source_id = resp.json()['source']['id']

        # Create candidate
        data = {'candidates': [{'source_id': source_id, 'talent_pool_ids': {'add': [talent_pool.id]}}]}
        create_resp = send_request('post', self.CANDIDATES_URL, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == http_status_codes.CREATED

        candidate_id = create_resp.json()['candidates'][0]['id']

        # Retrieve candidate
        get_resp = send_request('get', self.CANDIDATE_URL % candidate_id, access_token_first)
        print response_info(get_resp)
        assert get_resp.status_code == http_status_codes.ALL_OK
        assert get_resp.json()['candidate']['source_id'] == source_id


class TestUpdateCandidateName(object):
    URL = CandidateApiUrl.CANDIDATES

    def test_update_first_name(self, user_first, access_token_first, talent_pool):
        """
        Test:  Update candidate's first name
        Expect: 200, candidate's full name should also be updated
        """
        # Create candidate
        AddUserRoles.add_get_edit(user_first)
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', self.URL, access_token_first, data)
        candidate_id = create_resp.json()['candidates'][0]['id']

        # Retrieve candidate
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_full_name = get_resp.json()['candidate']['full_name']

        # Update candidate's first name
        data = {'candidates': [{'first_name': fake.first_name()}]}
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first, data)
        print response_info(update_resp)

        # Retrieve candidate
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        updated_full_name = get_resp.json()['candidate']['full_name']
        assert updated_full_name != candidate_full_name
        assert updated_full_name.startswith(data['candidates'][0]['first_name'])

    def test_update_middle_name(self, user_first, access_token_first, talent_pool):
        """
        Test:  Update candidate's middle name
        Expect: 200, candidate's full name should also be updated
        """
        # Create candidate
        AddUserRoles.add_get_edit(user_first)
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', self.URL, access_token_first, data)
        candidate_id = create_resp.json()['candidates'][0]['id']

        # Retrieve candidate
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_full_name = get_resp.json()['candidate']['full_name']

        # Update candidate's middle name
        data = {'candidates': [{'middle_name': fake.first_name()}]}
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first, data)
        print response_info(update_resp)

        # Retrieve candidate
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        updated_full_name = get_resp.json()['candidate']['full_name']
        assert updated_full_name != candidate_full_name
        assert data['candidates'][0]['middle_name'] in updated_full_name

    def test_update_last_name(self, user_first, access_token_first, talent_pool):
        """
        Test:  Update candidate's last name
        Expect: 200, candidate's full name should also be updated
        """
        # Create candidate
        AddUserRoles.add_get_edit(user_first)
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', self.URL, access_token_first, data)
        candidate_id = create_resp.json()['candidates'][0]['id']

        # Retrieve candidate
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_full_name = get_resp.json()['candidate']['full_name']

        # Update candidate's last name
        data = {'candidates': [{'last_name': fake.first_name()}]}
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first, data)
        print response_info(update_resp)

        # Retrieve candidate
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        updated_full_name = get_resp.json()['candidate']['full_name']
        assert updated_full_name != candidate_full_name
        assert updated_full_name.endswith(data['candidates'][0]['last_name'])
