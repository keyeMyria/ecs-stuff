"""
Test cases for adding, retrieving, updating, and deleting candidate emails
"""
# Candidate Service app instance
from candidate_service.candidate_app import app

# Conftest
from candidate_service.common.tests.conftest import *

from candidate_service.common.models.candidate import EmailLabel

# Helper functions
from helpers import AddUserRoles
from candidate_service.common.utils.test_utils import send_request, response_info
from candidate_service.common.routes import CandidateApiUrl

# Candidate sample data
from candidate_sample_data import (fake, generate_single_candidate_data, GenerateCandidateData)

# Custom errors
from candidate_service.custom_error_codes import CandidateCustomErrors as custom_error


class TestCreateCandidateEmail(object):
    def test_create_candidate_without_email(self, access_token_first, user_first, talent_pool):
        """
        Test:   Attempt to create a Candidate with no email
        Expect: 201
        """
        # Create Candidate with no email
        AddUserRoles.add_and_get(user_first)
        data = {'candidates': [{'first_name': 'john', 'last_name': 'stark',
                                'talent_pool_ids': {'add': [talent_pool.id]}}]}
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == requests.codes.CREATED

        # Create Candidate
        data = {'candidates': [{'first_name': 'john', 'last_name': 'stark', 'emails': [{}],
                                'talent_pool_ids': {'add': [talent_pool.id]}}]}
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == requests.codes.BAD
        assert create_resp.json()['error']['code'] == custom_error.INVALID_INPUT

    def test_create_candidate_with_bad_email(self, access_token_first, user_first, talent_pool):
        """
        Test:   Attempt to create a Candidate with invalid email format
        Expect: 400
        """
        # Create Candidate
        AddUserRoles.add(user_first)
        data = {'candidates': [{'emails': [{'label': None, 'is_default': True, 'address': 'bad_email.com'}],
                                'talent_pool_ids': {'add': [talent_pool.id]}}]}
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == requests.codes.BAD
        assert create_resp.json()['error']['code'] == custom_error.INVALID_EMAIL

    def test_create_candidate_without_email_label(self, access_token_first, user_first, talent_pool):
        """
        Test:   Create a Candidate without providing email's label
        Expect: 201, email's label must be 'Primary'
        """
        AddUserRoles.add_and_get(user=user_first)

        # Create Candidate without email-label
        data = {'candidates': [
            {'emails': [
                {'label': None, 'is_default': None, 'address': fake.safe_email()},
                {'label': None, 'is_default': None, 'address': fake.safe_email()}
            ], 'talent_pool_ids': {'add': [talent_pool.id]}}
        ]}
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        print response_info(get_resp)
        candidate_dict = get_resp.json()['candidate']
        assert create_resp.status_code == requests.codes.CREATED
        assert candidate_dict['emails'][0]['label'] == EmailLabel.PRIMARY_DESCRIPTION
        assert candidate_dict['emails'][-1]['label'] == EmailLabel.OTHER_DESCRIPTION

    def test_add_email_with_empty_values(self, access_token_first, user_first, talent_pool):
        """
        Test:  Add candidate email with all empty values
        Expect: 400; email address is required
        """
        AddUserRoles.add_and_get(user_first)
        data = {'candidates': [
            {'talent_pool_ids': {'add': [talent_pool.id]}, 'emails': [
                {'label': None, 'address': '  '},
            ]}
        ]}

        # Create candidate email
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == requests.codes.BAD
        assert create_resp.json()['error']['code'] == custom_error.INVALID_EMAIL

    def test_add_emails_with_whitespaced_values(self, access_token_first, user_first, talent_pool):
        """
        Test:  Add candidate emails with values containing whitespaces
        Expect:  201; but whitespaces should be stripped
        """
        AddUserRoles.add_and_get(user_first)
        data = {'candidates': [
            {'talent_pool_ids': {'add': [talent_pool.id]}, 'emails': [
                {'label': ' work', 'address': fake.safe_email() + '   '},
                {'label': 'Primary ', 'address': ' ' + fake.safe_email()}
            ]}
        ]}

        # Create candidate email
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == requests.codes.CREATED

        # Retrieve candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        print response_info(get_resp)
        emails = get_resp.json()['candidate']['emails']
        assert len(emails) == 2
        assert emails[0]['address'] == data['candidates'][0]['emails'][0]['address'].strip()
        assert emails[0]['label'] == data['candidates'][0]['emails'][0]['label'].strip().title()
        assert emails[1]['address'] == data['candidates'][0]['emails'][1]['address'].strip()
        assert emails[1]['label'] == data['candidates'][0]['emails'][1]['label'].strip()

    def test_add_candidate_with_duplicate_emails(self, access_token_first, user_first, talent_pool):
        """
        Test: Add candidate with two identical emails
        Expect: 201, but only one email should be added to db
        """
        AddUserRoles.add_and_get(user_first)

        # Create candidate with two identical emails
        email_address = fake.safe_email()
        data = {'candidates': [
            {'talent_pool_ids': {'add': [talent_pool.id]}, 'emails': [
                {'label': ' work', 'address': email_address},
                {'label': ' work', 'address': email_address}]
             }]
        }
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == requests.codes.BAD
        assert create_resp.json()['error']['code'] == custom_error.INVALID_USAGE

    def test_add_duplicate_candidate_with_same_email(self, access_token_first, user_first, talent_pool):
        """
        Test: Add candidate with an email that is associated with another candidate in the same domain
        """
        AddUserRoles.add_and_get(user_first)

        email_address = fake.safe_email()
        data = {'candidates': [
            {'talent_pool_ids': {'add': [talent_pool.id]}, 'emails': [
                {'label': ' work', 'address': email_address}]
             }]
        }
        send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == requests.codes.BAD
        assert create_resp.json()['error']['code'] == custom_error.CANDIDATE_ALREADY_EXISTS


class TestUpdateCandidateEmails(object):
    def test_add_emails(self, access_token_first, user_first, talent_pool):
        """
        Test:   Add an email to an existing Candidate. Number of candidate's emails must increase by 1.
        Expect: 200
        """
        # Create Candidate
        AddUserRoles.add_get_edit(user_first)
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        emails = get_resp.json()['candidate']['emails']
        emails_count = len(emails)

        # Add new email
        data = GenerateCandidateData.emails(candidate_id=candidate_id)
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        emails = candidate_dict['emails']
        email_from_data = data['candidates'][0]['emails'][0]

        assert candidate_id == candidate_dict['id']
        assert emails[-1]['label'] == email_from_data['label'].capitalize()
        assert emails[-1]['address'] == email_from_data['address']
        assert len(emails) == emails_count + 1

    def test_multiple_is_default_emails(self, access_token_first, user_first, talent_pool):
        """
        Test:   Add more than one CandidateEmail with is_default set to True
        Expect: 200, but only one CandidateEmail must have is_current True, the rest must be False
        """
        # Create Candidate
        AddUserRoles.add_get_edit(user_first)
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Add a new email to the existing Candidate with is_current set to True
        candidate_id = create_resp.json()['candidates'][0]['id']
        send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        updated_candidate_dict = get_resp.json()['candidate']
        updated_can_emails = updated_candidate_dict['emails']

        # Only one of the emails must be default!
        assert sum([1 for email in updated_can_emails if email['is_default']]) == 1

    def test_update_existing_email(self, access_token_first, user_first, talent_pool):
        """
        Test:   Update an existing CandidateEmail. Number of candidate's emails must remain unchanged
        Expect: 200
        """
        # Create Candidate
        AddUserRoles.add_get_edit(user_first)
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        emails_before_update = get_resp.json()['candidate']['emails']
        emails_count_before_update = len(emails_before_update)

        # Update first email
        data = GenerateCandidateData.emails(candidate_id=candidate_id, email_id=emails_before_update[0]['id'])
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        emails_after_update = candidate_dict['emails']

        assert candidate_id == candidate_dict['id']
        assert emails_before_update[0]['id'] == emails_after_update[0]['id']
        assert emails_before_update[0]['address'] != emails_after_update[0]['address']
        assert emails_after_update[0]['address'] == data['candidates'][0]['emails'][0]['address']
        assert emails_count_before_update == len(emails_after_update)

    def test_update_existing_email_with_bad_email_address(self, access_token_first, user_first, talent_pool):
        """
        Test:   Use a bad email address to update and existing CandidateEmail
        Expect: 400
        """
        # Create Candidate
        AddUserRoles.add_get_edit(user_first)
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        emails_before_update = get_resp.json()['candidate']['emails']
        emails_count_before_update = len(emails_before_update)

        # Update first email with an invalid email address
        data = {'candidates': [{'id': candidate_id, 'emails': [
            {'id': emails_before_update[0]['id'], 'label': 'primary', 'address': 'bad_email.com'}
        ]}]}
        updated_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        candidate_dict = get_resp.json()['candidate']

        emails_after_update = candidate_dict['emails']
        assert updated_resp.status_code == requests.codes.BAD
        assert candidate_id == candidate_dict['id']
        assert emails_count_before_update == len(emails_after_update)
        assert emails_before_update[0]['address'] == emails_after_update[0]['address']

    def test_add_forbidden_email_to_candidate(self, access_token_first, user_first, talent_pool):
        """
        Test: Add two candidates. Then add another email to candidate 2 using candidate's 1 email
        """
        AddUserRoles.add_get_edit(user_first)

        # Define email address
        first_candidates_email = fake.safe_email()

        # Create both candidates
        data = {'candidates': [
            {'talent_pool_ids': {'add': [talent_pool.id]}, 'emails': [{'address': first_candidates_email}]},
            {'talent_pool_ids': {'add': [talent_pool.id]}}
        ]}
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        print response_info(create_resp)
        assert create_resp.status_code == requests.codes.CREATED

        # Add a second email to the second candidate using first-candidate's email address
        candidate_2_id = create_resp.json()['candidates'][1]['id']
        update_data = {'candidates': [{'id': candidate_2_id, 'emails': [{'address': first_candidates_email}]}]}
        update_resp = send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, update_data)
        print response_info(update_resp)
        assert update_resp.status_code == requests.codes.FORBIDDEN
        assert update_resp.json()['error']['code'] == custom_error.EMAIL_FORBIDDEN


class TestDeleteCandidateEmail(object):
    def test_non_logged_in_user_delete_can_emails(self):
        """
        Test:   Delete candidate's emails without logging in
        Expect: 401
        """
        # Delete Candidate's emails
        resp = send_request('delete', CandidateApiUrl.EMAILS % '5', None)
        print response_info(resp)
        assert resp.status_code == requests.codes.UNAUTHORIZED

    def test_delete_candidate_email_with_bad_input(self, access_token_first):
        """
        Test:   Attempt to delete candidate email with non integer values for candidate_id & email_id
        Expect: 404
        """
        # Delete Candidate's emails
        resp = send_request('delete', CandidateApiUrl.EMAILS % 'x', access_token_first)
        print response_info(resp)
        assert resp.status_code == requests.codes.NOT_FOUND

        # Delete Candidate's email
        resp = send_request('delete', CandidateApiUrl.EMAIL % (5, 'x'), access_token_first)
        print response_info(resp)
        assert resp.status_code == requests.codes.NOT_FOUND

    def test_delete_email_of_a_candidate_belonging_to_a_diff_user(self, user_first, access_token_first, talent_pool,
                                                                  user_second, access_token_second):
        """
        Test:   Attempt to delete the email of a Candidate that belongs
                to a different user from a different domain
        Expect: 403
        """
        # Create candidate_1 & candidate_2 with sample_user & sample_user_2
        AddUserRoles.add(user_first)
        AddUserRoles.edit(user_second)
        data = generate_single_candidate_data([talent_pool.id])
        create_resp_1 = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
        candidate_1_id = create_resp_1.json()['candidates'][0]['id']

        # Delete candidate_1's email with sample_user_2 logged in
        updated_resp = send_request('delete', CandidateApiUrl.EMAILS % candidate_1_id, access_token_second)
        print response_info(updated_resp)
        assert updated_resp.status_code == requests.codes.FORBIDDEN
        assert updated_resp.json()['error']['code'] == custom_error.CANDIDATE_FORBIDDEN

    def test_delete_email_of_a_different_candidate(self, user_first, access_token_first, talent_pool):
        """
        Test:   Attempt to delete the email of a different Candidate
        Expect: 403
        """
        # Create candidate_1 and candidate_2
        AddUserRoles.all_roles(user_first)
        data_1 = generate_single_candidate_data([talent_pool.id])
        data_2 = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data_1)
        candidate_1_id = create_resp.json()['candidates'][0]['id']
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data_2)
        candidate_2_id = create_resp.json()['candidates'][0]['id']

        # Retrieve candidate_2's emails
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_2_id, access_token_first)
        can_2_emails = get_resp.json()['candidate']['emails']

        # Delete candidate_2's email using candidate_1_id
        url = CandidateApiUrl.EMAIL % (candidate_1_id, can_2_emails[0]['id'])
        updated_resp = send_request('delete', url, access_token_first)
        print response_info(updated_resp)
        assert updated_resp.status_code == requests.codes.FORBIDDEN
        assert updated_resp.json()['error']['code'] == custom_error.EMAIL_FORBIDDEN

    def test_delete_candidate_emails(self, user_first, access_token_first, talent_pool):
        """
        Test:   Remove Candidate's emails from db
        Expect: 204, Candidate must not have any emails left
        """
        # Create Candidate
        AddUserRoles.all_roles(user_first)
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Delete Candidate's emails
        candidate_id = create_resp.json()['candidates'][0]['id']
        updated_resp = send_request('delete', CandidateApiUrl.EMAILS % candidate_id, access_token_first)
        print response_info(updated_resp)

        # Retrieve Candidate after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        can_dict_after_update = get_resp.json()['candidate']
        assert updated_resp.status_code == requests.codes.NO_CONTENT
        assert len(can_dict_after_update['emails']) == 0

    def test_delete_candidate_email(self, user_first, access_token_first, talent_pool):
        """
        Test:   Remove Candidate's email from db
        Expect: 204, Candidate's emails must be less 1
        """
        # Create Candidate
        AddUserRoles.all_roles(user_first)
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate's emails
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        can_emails = get_resp.json()['candidate']['emails']

        # Current number of candidate's emails
        emails_count_before_delete = len(can_emails)

        # Delete Candidate's email
        url = CandidateApiUrl.EMAIL % (candidate_id, can_emails[0]['id'])
        updated_resp = send_request('delete', url, access_token_first)
        print response_info(updated_resp)

        # Retrieve Candidate's emails after update
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        can_emails_after_delete = get_resp.json()['candidate']['emails']
        assert updated_resp.status_code == requests.codes.NO_CONTENT
        assert len(can_emails_after_delete) == emails_count_before_delete - 1


class TestTrackCandidateEmailEdits(object):
    def test_edit_candidate_email(self, access_token_first, user_first, talent_pool):
        """
        Test:   Change Candidate's email record
        Expect: 200
        """
        # Create Candidate
        AddUserRoles.all_roles(user_first)
        data = generate_single_candidate_data([talent_pool.id])
        create_resp = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        candidate_id = create_resp.json()['candidates'][0]['id']
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        old_email_dict = get_resp.json()['candidate']['emails'][0]

        # Update Candidate's email
        data = {'candidates': [
            {'id': candidate_id, 'emails': [{'id': old_email_dict['id'], 'address': 'someone@gettalent.com'}]}
        ]}
        send_request('patch', CandidateApiUrl.CANDIDATES, access_token_first, data)

        # Retrieve Candidate
        get_resp = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id, access_token_first)
        new_email_dict = get_resp.json()['candidate']['emails'][0]

        # Retrieve Candidate Edits
        edit_resp = send_request('get', CandidateApiUrl.CANDIDATE_EDIT % candidate_id, access_token_first)
        print response_info(edit_resp)

        candidate_edits = edit_resp.json()['candidate']['edits']
        assert edit_resp.status_code == requests.codes.OK
        assert old_email_dict['address'] in [edit['old_value'] for edit in candidate_edits]
        assert new_email_dict['address'] in [edit['new_value'] for edit in candidate_edits]
