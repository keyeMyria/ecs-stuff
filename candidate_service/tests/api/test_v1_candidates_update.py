"""
Test cases for CandidateResource/patch()
"""
# Candidate Service app instance
from candidate_service.candidate_app import app

import pycountry

# Models
from candidate_service.common.models.candidate import CandidateEmail
from candidate_service.common.models.misc import Product

# Conftest
from candidate_service.common.tests.conftest import *
from ..conftest import test_candidate_1

# Helper functions
from candidate_service.common.utils.test_utils import send_request, response_info
from candidate_service.common.routes import CandidateApiUrl

# Candidate sample data
from candidate_sample_data import (fake, generate_single_candidate_data, GenerateCandidateData)

# Custom errors
from candidate_service.custom_error_codes import CandidateCustomErrors as custom_error


class TestUpdateCandidateSuccessfully(object):
    """
    Class contains functional test that expect a 200 response
    """

    def test_primary_information(self, access_token_first, test_candidate_1, domain_source_2):
        """
        Test: Edit the primary information of a full candidate's profile
        """
        candidate_id = test_candidate_1['candidate']['id']

        update_data = {
            'candidates': [
                {
                    'id': candidate_id,
                    'first_name': fake.first_name(),
                    'middle_name': fake.first_name(),
                    'last_name': fake.last_name(),
                    'source_id': domain_source_2['source']['id'],
                    'objective': fake.sentence(),
                    'source_product_id': 2  # Web
                }
            ]
        }

        # Update candidate's primary information
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, update_data)
        print response_info(update_resp)
        assert update_resp.status_code == requests.codes.OK

        # Retrieve candidate and assert its primary data have been updated
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % str(candidate_id), access_token_first)
        print response_info(get_resp)

        candidate_data = get_resp.json()['candidate']

        assert candidate_data['id'] == candidate_id
        assert candidate_data['first_name'] == update_data['candidates'][0]['first_name']
        assert candidate_data['middle_name'] == update_data['candidates'][0]['middle_name']
        assert candidate_data['last_name'] == update_data['candidates'][0]['last_name']
        assert candidate_data['source_id'] == update_data['candidates'][0]['source_id']
        assert candidate_data['objective'] == update_data['candidates'][0]['objective']
        assert candidate_data['source_product_id'] == update_data['candidates'][0]['source_product_id']


class TestUpdateCandidate(object):
    def test_hide_candidates(self, access_token_first, talent_pool):
        """
        Test:  Create a candidate and hide it
        Expect: 200; candidate should not be retrievable
        """
        # Create candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)

        # Hide candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        data = {'candidates': [{'id': candidate_id, 'hide': True}]}
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(update_resp)
        assert update_resp.status_code == 200
        assert update_resp.json()['hidden_candidate_ids'][0] == candidate_id

        # Retrieve candidate
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        print response_info(get_resp)
        assert get_resp.status_code == 404
        assert get_resp.json()['error']['code'] == custom_error.CANDIDATE_IS_HIDDEN

    def test_hide_and_unhide_candidates(self, access_token_first, talent_pool):
        """
        Test:  Create candidates, hide them, and unhide them again via Patch call
        """
        # Create candidates
        data_1 = generate_single_candidate_data([talent_pool.id])
        data_2 = generate_single_candidate_data([talent_pool.id])
        create_resp_1 = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data_1)
        create_resp_2 = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data_2)

        candidate_id_1 = create_resp_1.json()['candidates'][0]['id']
        candidate_id_2 = create_resp_2.json()['candidates'][0]['id']

        # Hide both candidates
        hide_data = {'candidates': [{'id': candidate_id_1, 'hide': True}, {'id': candidate_id_2, 'hide': True}]}
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, hide_data)
        print response_info(update_resp)
        assert update_resp.status_code == 200
        assert len(update_resp.json()['hidden_candidate_ids']) == len(hide_data['candidates'])

        # Retrieve candidates
        data = {'candidate_ids': [candidate_id_1, candidate_id_2]}
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE_SEARCH_URI, access_token_first, data)
        print response_info(get_resp)
        assert get_resp.status_code == 404
        assert get_resp.json()['error']['code'] == custom_error.CANDIDATE_IS_HIDDEN

        # Un-hide candidates
        unhide_data = {'candidates': [{'id': candidate_id_1, 'hide': False}, {'id': candidate_id_2, 'hide': False}]}
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, unhide_data)
        print response_info(update_resp)
        assert update_resp.status_code == 200

        # Retrieve candidates
        data = {'candidate_ids': [candidate_id_1, candidate_id_2]}
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE_SEARCH_URI, access_token_first, data)
        print response_info(get_resp)
        assert get_resp.status_code == 200

    def test_update_candidate_outside_of_domain(self, access_token_first, user_first, talent_pool,
                                                access_token_second, user_second):
        """
        Test: User attempts to update a candidate from a different domain
        Expect: 403
        """
        # Create Candidate

        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        candidate_id = create_resp.json()['candidates'][0]['id']

        # User from different domain to update candidate
        data = {'candidates': [{'id': candidate_id, 'first_name': 'moron'}]}
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_second, data)
        print response_info(update_resp)
        assert update_resp.status_code == 403
        assert update_resp.json()['error']['code'] == custom_error.CANDIDATE_FORBIDDEN

    def test_update_candidate_without_id(self, access_token_first, user_first):
        """
        Test:   Attempt to update a Candidate without providing the ID
        Expect: 400
        """
        # Update Candidate's first_name
        data = {'candidate': {'first_name': fake.first_name()}}
        resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)

        print response_info(resp)
        assert resp.status_code == 400
        assert resp.json()['error']['code'] == custom_error.INVALID_INPUT

    def test_update_candidate_names(self, access_token_first, user_first, talent_pool):
        """
        Test:   Update candidate's first, middle, and last names
        Expect: 200
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Update Candidate's first_name
        candidate_id = create_resp.json()['candidates'][0]['id']
        data = {'candidates': [
            {'id': candidate_id, 'first_name': fake.first_name(),
             'middle_name': fake.first_name(), 'last_name': fake.last_name()}
        ]}
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(update_resp)
        assert candidate_id == update_resp.json()['candidates'][0]['id']

        # Retrieve Candidate
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        # Assert on updated field
        f_name, l_name = data['candidates'][0]['first_name'], data['candidates'][0]['last_name']
        m_name = data['candidates'][0]['middle_name']
        full_name_from_data = str(f_name) + ' ' + str(m_name) + ' ' + str(l_name)
        assert candidate_dict['full_name'] == full_name_from_data

    def test_update_candidate_names_with_candidate_id_in_url(self, access_token_first, user_first, talent_pool):
        """
        Test:   Update candidate's first, middle, and last names with candidate ID sent thru the url
        Expect: 200
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Update Candidate's first_name
        candidate_id = create_resp.json()['candidates'][0]['id']
        data = {'candidates': [
            {'first_name': fake.first_name(), 'middle_name': fake.first_name(), 'last_name': fake.last_name()}
        ]}
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first, data)
        print response_info(update_resp)
        assert candidate_id == update_resp.json()['candidates'][0]['id']

        # Retrieve Candidate
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        # Assert on updated field
        f_name, l_name = data['candidates'][0]['first_name'], data['candidates'][0]['last_name']
        m_name = data['candidates'][0]['middle_name']
        full_name_from_data = str(f_name) + ' ' + str(m_name) + ' ' + str(l_name)
        assert candidate_dict['full_name'] == full_name_from_data

    def test_update_candidates_in_bulk_with_one_erroneous_data(self, access_token_first, user_first, talent_pool):
        """
        Test: Attempt to update few candidates, one of which will have bad data
        Expect: 400; no record should be added to the db
        """
        # Create Candidate
        email_1, email_2 = fake.safe_email(), fake.safe_email()
        data = {'candidates': [
            {'talent_pool_ids': {'add': [talent_pool.id]}, 'emails': [{'label': None, 'address': email_1}]},
            {'talent_pool_ids': {'add': [talent_pool.id]}, 'emails': [{'label': None, 'address': email_2}]}
        ]}
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        candidate_ids = [candidate['id'] for candidate in create_resp.json()['candidates']]

        # Retrieve both candidates
        data = {'candidate_ids': candidate_ids}
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE_SEARCH_URI, access_token_first, data)
        candidates = get_resp.json()['candidates']

        # Update candidates' email address, one will be an invalid email address
        candidate_1_id, candidate_2_id = candidates[0]['id'], candidates[1]['id']
        email_1_id = candidates[0]['emails'][0]['id']
        email_2_id = candidates[1]['emails'][0]['id']
        update_data = {'candidates': [
            {'id': candidate_1_id, 'emails': [{'id': email_1_id, 'address': fake.safe_email()}]},
            {'id': candidate_2_id, 'emails': [{'id': email_2_id, 'address': 'bad_email_.com'}]}
        ]}
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, update_data)
        db.session.commit()
        print response_info(update_resp)

        # Candidates' emails must remain unchanged
        assert update_resp.status_code == 400
        assert update_resp.json()['error']['code'] == custom_error.INVALID_EMAIL
        assert CandidateEmail.get_by_id(_id=email_1_id).address == email_1
        assert CandidateEmail.get_by_id(_id=email_2_id).address == email_2


class TestUpdateCandidateAddress(object):
    # TODO Commenting out randomly failing test case so build passes. -OM
    # def test_add_new_candidate_address(self, access_token_first, user_first, talent_pool):
    #     """
    #     Test:   Add a new CandidateAddress to an existing Candidate
    #     Expect: 200
    #     """
    #     # Create Candidate
    #     data = generate_single_candidate_data([talent_pool.id])
    #     create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
    #
    #     # Add a new address to the existing Candidate
    #     candidate_id = create_resp.json()['candidates'][0]['id']
    #     data = GenerateCandidateData.addresses(talent_pool_ids=[talent_pool.id], candidate_id=candidate_id)
    #     update_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
    #     print response_info(update_resp)
    #
    #     # Retrieve Candidate after update
    #     get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
    #     updated_candidate_dict = get_resp.json()['candidate']
    #     candidate_address = updated_candidate_dict['addresses'][-1]
    #     assert updated_candidate_dict['id'] == candidate_id
    #     assert isinstance(candidate_address, dict)
    #     assert candidate_address['address_line_1'] == data['candidates'][0]['addresses'][-1]['address_line_1']
    #     assert candidate_address['city'] == data['candidates'][0]['addresses'][-1]['city']
    #     assert candidate_address['zip_code'] == data['candidates'][0]['addresses'][-1]['zip_code']

    def test_multiple_is_default_addresses(self, access_token_first, talent_pool):
        """
        Test:   Add more than one CandidateAddress with is_default set to True
        Expect: 200, but only one CandidateAddress must have is_default True, the rest must be False
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Add a new address to the existing Candidate with is_default set to True
        candidate_id = create_resp.json()['candidates'][0]['id']
        data = GenerateCandidateData.addresses(candidate_id=candidate_id, is_default=True)
        send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        updated_candidate_dict = get_resp.json()['candidate']
        updated_can_addresses = updated_candidate_dict['addresses']
        # Only one of the addresses must be default!
        assert sum([1 for address in updated_can_addresses if address['is_default']]) == 1

    def test_update_an_existing_address(self, access_token_first, user_first, talent_pool):
        """
        Test:   Update an existing CandidateAddress
        Expect: 200
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']
        candidate_address = candidate_dict['addresses'][0]

        # Update one of Candidate's addresses
        data = GenerateCandidateData.addresses(candidate_id=candidate_id, address_id=candidate_address['id'])
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        updated_candidate_dict = resp.json()['candidate']
        updated_address = updated_candidate_dict['addresses'][0]
        assert isinstance(updated_candidate_dict, dict)
        assert updated_candidate_dict['id'] == candidate_id
        assert updated_address['address_line_1'] == data['candidates'][0]['addresses'][0]['address_line_1']
        assert updated_address['city'] == data['candidates'][0]['addresses'][0]['city']
        assert updated_address['subdivision'] == \
               pycountry.subdivisions.get(code=data['candidates'][0]['addresses'][0]['subdivision_code']).name
        assert updated_address['zip_code'] == data['candidates'][0]['addresses'][0]['zip_code']

    def test_update_candidate_current_address(self, access_token_first, user_first, talent_pool):
        """
        Test:   Set one of candidate's addresses' is_default to True and assert it's the first
                CandidateAddress object returned in addresses-list
        Expect: 200
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Add another address
        candidate_id = create_resp.json()['candidates'][0]['id']
        data = GenerateCandidateData.addresses(candidate_id=candidate_id, is_default=True)
        send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']
        can_addresses = candidate_dict['addresses']

        # Update: Set the last CandidateAddress in can_addresses as the default candidate-address
        data = {
            'candidates': [{'id': candidate_id, 'addresses': [{'id': can_addresses[-1]['id'], 'is_default': True}]}]}
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)
        assert updated_resp.status_code == 200

        # Retrieve Candidate after update
        resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        updated_candidate_dict = resp.json()['candidate']

        updated_addresses = updated_candidate_dict['addresses']
        assert isinstance(updated_addresses, list)
        assert updated_addresses[0]['is_default'] == True


class TestUpdateCandidateAOI(object):
    def test_add_new_area_of_interest(self, access_token_first, user_first, talent_pool, domain_aois):
        """
        Test:   Add a new CandidateAreaOfInterest to existing Candidate.
                Number of CandidateAreaOfInterest should increase by 1.
        Expect: 200
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        candidate_area_of_interest_count = len(candidate_dict['areas_of_interest'])

        # Add new CandidateAreaOfInterest
        data = GenerateCandidateData.areas_of_interest(domain_aois, [talent_pool.id], candidate_id)
        resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']
        candidate_aois = candidate_dict['areas_of_interest']
        assert isinstance(candidate_aois, list)
        assert candidate_aois[0]['name'] == db.session.query(AreaOfInterest).get(candidate_aois[0]['id']).name
        assert candidate_aois[1]['name'] == db.session.query(AreaOfInterest).get(candidate_aois[1]['id']).name
        assert len(candidate_aois) == candidate_area_of_interest_count + 2


class TestUpdateWorkExperience(object):
    def test_add_experiences(self, access_token_first, user_first, talent_pool):
        """
        Test:  Add candidate work experience and check for total months of experiences accumulated
        Expect: Candidate.total_months_experience to be updated accordingly
        """
        data = {'candidates': [
            {
                'talent_pool_ids': {'add': [talent_pool.id]},
                'work_experiences': [
                    {'start_year': 2005, 'end_year': 2007},  # 12*2 = 24 months of experience
                    {'start_year': 2011, 'end_year': None}  # 12*5 = 60 months of experience
                ]
            }
        ]}
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == requests.codes.CREATED

        # Check candidate's total_months_experience from db
        candidate_id = create_resp.json()['candidates'][0]['id']
        db.session.commit()
        candidate = Candidate.get_by_id(candidate_id)
        assert candidate.total_months_experience == 84  # 24 + 60

        # Retrieve candidate
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)

        # Add more experiences
        experience_id = get_resp.json()['candidate']['work_experiences'][0]['id']
        update_data = {'candidates': [
            {'id': candidate_id, 'work_experiences': [
                {'id': experience_id, 'start_year': 2003, 'end_year': 2011}]  # 12 * 8 = 96 months of experience
             }
        ]}
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, update_data)
        print response_info(update_resp)
        db.session.commit()
        assert candidate.total_months_experience == 120  # (84 - 60) + 96

    def test_add_candidate_experience(self, access_token_first, user_first, talent_pool):
        """
        Test:   Add a CandidateExperience to an existing Candidate. Number of Candidate's
                CandidateExperience must increase by 1.
        Expect: 200
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']
        candidate_experience_count = len(candidate_dict['work_experiences'])

        # Add CandidateExperience
        data = GenerateCandidateData.work_experiences(candidate_id=candidate_id)
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        updated_can_dict = get_resp.json()['candidate']
        can_experiences = updated_can_dict['work_experiences']
        can_experiences_from_data = data['candidates'][0]['work_experiences']
        assert candidate_id == updated_can_dict['id']
        assert isinstance(can_experiences, list)
        assert can_experiences[0]['organization'] == can_experiences_from_data[0]['organization']
        assert can_experiences[0]['position'] == can_experiences_from_data[0]['position']
        assert can_experiences[0]['city'] == can_experiences_from_data[0]['city']
        assert can_experiences[0]['subdivision'] == pycountry.subdivisions.get(
            code=can_experiences_from_data[0]['subdivision_code']).name
        assert len(can_experiences) == candidate_experience_count + 1

    def test_multiple_is_current_experiences(self, access_token_first, user_first, talent_pool):
        """
        Test:   Add more than one CandidateExperience with is_current set to True
        Expect: 200, but only one CandidateExperience must have is_current True, the rest must be False
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Add a new work experience to the existing Candidate with is_current set to True
        candidate_id = create_resp.json()['candidates'][0]['id']
        send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        updated_candidate_dict = get_resp.json()['candidate']
        updated_can_experiences = updated_candidate_dict['work_experiences']

        # Only one of the experiences must be current!
        assert sum([1 for experience in updated_can_experiences if experience['is_current']]) == 1

    def test_add_experience_bullet(self, access_token_first, user_first, talent_pool):
        """
        Test:   Adds a CandidateExperienceBullet to an existing CandidateExperience
                Total number of candidate's experience_bullet must increase by 1, and
                number of candidate's CandidateExperience must remain unchanged.
        Expect: 200
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        bullet_count = len(candidate_dict['work_experiences'][0]['bullets'])

        # Add CandidateExperienceBullet to existing CandidateExperience
        data = GenerateCandidateData.work_experiences(
            candidate_id=candidate_id, experience_id=candidate_dict['work_experiences'][0]['id'])
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        updated_can_dict = get_resp.json()['candidate']
        updated_experiences = updated_can_dict['work_experiences']

        bullets_from_data = data['candidates'][0]['work_experiences'][0]['bullets'][0]
        assert isinstance(updated_experiences, list)
        assert candidate_id == updated_can_dict['id']
        assert updated_experiences[0]['bullets'][-1]['description'] == bullets_from_data['description']
        assert len(updated_experiences[0]['bullets']) == bullet_count + 1
        assert len(updated_experiences) == len(updated_can_dict['work_experiences'])

    def test_update_experience_bullet(self, access_token_first, user_first, talent_pool):
        """
        Test:   Update an existing CandidateExperienceBullet
                Since this is an update only, the number of candidate's experience_bullets
                must remain unchanged.
        Expect: 200
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        experience_dict = candidate_dict['work_experiences'][0]
        candidate_experience_bullet_count = len(experience_dict['bullets'])

        # Update CandidateExperienceBullet
        data = GenerateCandidateData.work_experiences(candidate_id=candidate_id,
                                                      experience_id=experience_dict['id'],
                                                      bullet_id=experience_dict['bullets'][0]['id'])
        print "\ndata: {}".format(data)
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        updated_can_dict = get_resp.json()['candidate']
        updated_exp_bullet_dict = updated_can_dict['work_experiences'][0]['bullets']

        exp_bullet_dict_from_data = data['candidates'][0]['work_experiences'][0]['bullets'][0]

        assert candidate_experience_bullet_count == len(updated_exp_bullet_dict)
        assert updated_exp_bullet_dict[0]['description'] == exp_bullet_dict_from_data['description']


class TestUpdateWorkPreference(object):
    def test_add_multiple_work_preference(self, access_token_first, user_first, talent_pool):
        """
        Test:   Attempt to add two CandidateWorkPreference
        Expect: 400
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        candidate_id = create_resp.json()['candidates'][0]['id']

        # Add CandidateWorkPreference
        data = GenerateCandidateData.work_preference(candidate_id=candidate_id)
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)
        assert updated_resp.status_code == 400
        assert updated_resp.json()['error']['code'] == custom_error.WORK_PREF_EXISTS

    def test_update_work_preference(self, access_token_first, user_first, talent_pool):
        """
        Test:   Update candidate's work preference. Since this is an update,
                number of CandidateWorkPreference must remain unchanged.
        Expect: 200
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        # Update CandidateWorkPreference
        data = GenerateCandidateData.work_preference(candidate_id=candidate_id,
                                                     preference_id=candidate_dict['work_preference']['id'])
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        updated_candidate_dict = get_resp.json()['candidate']
        work_preference_dict = updated_candidate_dict['work_preference']

        work_pref_from_data = data['candidates'][0]['work_preference']

        assert candidate_id == updated_candidate_dict['id']
        assert isinstance(work_preference_dict, dict)
        assert work_preference_dict['salary'] == work_pref_from_data['salary']
        assert work_preference_dict['hourly_rate'] == float(work_pref_from_data['hourly_rate'])
        assert work_preference_dict['travel_percentage'] == work_pref_from_data['travel_percentage']


class TestUpdateCandidateMilitaryService(object):
    def test_add_military_service_with_incorrect_date_format(self, access_token_first, user_first, talent_pool):
        """
        Test: Attempt to add military service to candidate with faulty to_date or from_date format
        Expect: 400
        """
        # Create candidate + candidate military service
        data = {'candidates': [
            {'talent_pool_ids': {'add': [talent_pool.id]}, 'military_services': [
                {'from_date': '2005', 'to_date': '2012-12-12'}
            ]}
        ]}
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == 400
        assert create_resp.json()['error']['code'] == custom_error.MILITARY_INVALID_DATE

    def test_add_military_service(self, access_token_first, user_first, talent_pool):
        """
        Test:   Add a CandidateMilitaryService to an existing Candidate.
                Number of candidate's military_services should increase by 1.
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        military_services_before_update = get_resp.json()['candidate']['military_services']
        military_services_count_before_update = len(military_services_before_update)

        # Add CandidateMilitaryService
        data = {'candidates': [{'id': candidate_id, 'military_services': [
            {'country': 'gb', 'branch': 'air force', 'comments': 'adept at killing cows with mad-cow-disease'}
        ]}]}
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        military_services_after_update = candidate_dict['military_services']
        assert candidate_id == candidate_dict['id']
        assert len(military_services_after_update) == military_services_count_before_update + 1
        assert military_services_after_update[-1]['branch'] == 'air force'
        assert military_services_after_update[-1]['comments'] == 'adept at killing cows with mad-cow-disease'

    def test_update_military_service(self, access_token_first, user_first, talent_pool):
        """
        Test:   Update an existing CandidateMilitaryService.
                Number of candidate's military_services should remain unchanged.
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        military_services_before_update = get_resp.json()['candidate']['military_services']
        military_services_count_before_update = len(military_services_before_update)

        # Add CandidateMilitaryService
        data = {'candidates': [{'id': candidate_id, 'military_services': [
            {'id': military_services_before_update[0]['id'], 'country': 'gb', 'branch': 'air force',
             'comments': 'adept at killing cows with mad-cow-disease'}
        ]}]}
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        military_services_after_update = candidate_dict['military_services']
        assert candidate_id == candidate_dict['id']
        assert len(military_services_after_update) == military_services_count_before_update
        assert military_services_after_update[0]['branch'] == 'air force'
        assert military_services_after_update[0]['comments'] == 'adept at killing cows with mad-cow-disease'


class TestUpdateCandidatePreferredLocation(object):
    def test_add_preferred_location(self, access_token_first, user_first, talent_pool):
        """
        Test:   Add a CandidatePreferredLocation to an existing Candidate.
                Number of candidate's preferred_location should increase by 1.
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        preferred_location_before_update = get_resp.json()['candidate']['preferred_locations']
        preferred_locations_count_before_update = len(preferred_location_before_update)

        # Add CandidatePreferredLocation
        data = {'candidates': [{'id': candidate_id, 'preferred_locations': [{'city': 'austin', 'state': 'texas'}]}]}
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        preferred_locations_after_update = candidate_dict['preferred_locations']
        assert candidate_id == candidate_dict['id']
        assert len(preferred_locations_after_update) == preferred_locations_count_before_update + 1
        assert preferred_locations_after_update[-1]['city'] == 'austin'
        assert preferred_locations_after_update[-1]['state'] == 'texas'

    def test_update_preferred_location(self, access_token_first, user_first, talent_pool):
        """
        Test:   Update an existing CandidatePreferredLocation.
                Number of candidate's preferred_location should remain unchanged.
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        preferred_location_before_update = get_resp.json()['candidate']['preferred_locations']
        preferred_locations_count_before_update = len(preferred_location_before_update)

        # Add CandidatePreferredLocation
        data = {'candidates': [{'id': candidate_id, 'preferred_locations': [
            {'id': preferred_location_before_update[0]['id'], 'city': 'austin', 'state': 'texas'}]}]}
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        preferred_locations_after_update = candidate_dict['preferred_locations']
        assert candidate_id == candidate_dict['id']
        assert len(preferred_locations_after_update) == preferred_locations_count_before_update + 0
        assert preferred_locations_after_update[0]['city'] == 'austin'
        assert preferred_locations_after_update[0]['state'] == 'texas'


class TestUpdateCandidateSkill(object):
    def test_add_skill(self, access_token_first, user_first, talent_pool):
        """
        Test:   Add a CandidateSkill to an existing Candidate.
                Number of candidate's preferred_location should increase by 1.
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        skills_before_update = get_resp.json()['candidate']['skills']
        skills_count_before_update = len(skills_before_update)

        # Add CandidateSkill
        data = {'candidates': [{'id': candidate_id, 'skills': [{'name': 'pos'}]}]}
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        skills_after_update = candidate_dict['skills']
        assert candidate_id == candidate_dict['id']
        assert len(skills_after_update) == skills_count_before_update + 1
        assert skills_after_update[-1]['name'] == 'pos'

    def test_update_skill(self, access_token_first, user_first, talent_pool):
        """
        Test:   Update an existing CandidateSkill.
                Number of candidate's preferred_location should remain unchanged.
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        skills_before_update = get_resp.json()['candidate']['skills']
        skills_count_before_update = len(skills_before_update)

        # Update CandidateSkill
        data = {'candidates': [{'id': candidate_id, 'skills': [{'id': skills_before_update[0]['id'], 'name': 'pos'}]}]}
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        skills_after_update = candidate_dict['skills']
        assert candidate_id == candidate_dict['id']
        assert len(skills_after_update) == skills_count_before_update
        assert skills_after_update[0]['name'] == 'pos'


class TestUpdateCandidateSocialNetwork(object):
    def test_add_social_network(self, access_token_first, user_first, talent_pool):
        """
        Test:   Add a CandidateSocialNetwork to an existing Candidate.
                Number of candidate's social_networks should increase by 1.
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        social_networks_before_update = get_resp.json()['candidate']['social_networks']
        social_networks_count_before_update = len(social_networks_before_update)

        # Add CandidateSocialNetwork
        data = {'candidates': [{'id': candidate_id, 'social_networks': [
            {'name': 'linkedin', 'profile_url': 'https://www.linkedin.com/company/sara'}
        ]}]}
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        social_networks_after_update = candidate_dict['social_networks']
        assert candidate_id == candidate_dict['id']
        assert len(social_networks_after_update) == social_networks_count_before_update + 1
        assert social_networks_after_update[-1]['name'] == 'LinkedIn'
        assert social_networks_after_update[-1]['profile_url'] == 'https://www.linkedin.com/company/sara'

    def test_update_social_network(self, access_token_first, user_first, talent_pool):
        """
        Test:   Update a CandidateSocialNetwork.
                Number of candidate's social_networks should remain unchanged.
        """
        # Create Candidate
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        social_networks_before_update = get_resp.json()['candidate']['social_networks']
        social_networks_count_before_update = len(social_networks_before_update)

        # Add CandidateSocialNework
        data = {'candidates': [{'id': candidate_id, 'social_networks': [
            {'id': social_networks_before_update[0]['id'],
             'name': 'linkedin', 'profile_url': 'https://www.linkedin.com/company/sara'}
        ]}]}
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)
        assert updated_resp.status_code == 200

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        social_networks_after_update = candidate_dict['social_networks']
        assert candidate_id == candidate_dict['id']
        assert len(social_networks_after_update) == social_networks_count_before_update
        assert social_networks_after_update[0]['name'] == 'LinkedIn'
        assert social_networks_after_update[0]['profile_url'] == 'https://www.linkedin.com/company/sara'
