"""
Author: Hafiz Muhammad Basit, QC-Technologies,
        Lahore, Punjab, Pakistan <basit.gettalent@gmail.com>

    This module contains pyTests for endpoint /campaigns/:id/send of SMS Campaign API.
"""
# Standard Imports
import requests

# Application Specific
from sms_campaign_service.custom_exceptions import SmsCampaignApiException
from sms_campaign_service.common.utils.app_rest_urls import SmsCampaignApiUrl
from sms_campaign_service.tests.conftest import assert_on_blasts_sends_url_conversion_and_activity
from sms_campaign_service.common.error_handling import (MethodNotAllowed, UnauthorizedError,
                                                        ResourceNotFound, ForbiddenError,
                                                        InternalServerError)


class TestSendSmsCampaign:
    """
    This class contains tests for endpoint /campaigns/:id/send
    """

    def test_for_get_request(self, auth_token, sms_campaign_of_current_user):
        """
        POST method is not allowed on this endpoint, should get 405 (Method not allowed)
        :param auth_token: access token for sample user
        :param sms_campaign_of_current_user: fixture to create SMS campaign for current user
        :return:
        """
        response = requests.get(
            SmsCampaignApiUrl.CAMPAIGN_SEND_PROCESS % sms_campaign_of_current_user.id,
            headers=dict(Authorization='Bearer %s' % auth_token))
        assert response.status_code == MethodNotAllowed.http_status_code(), \
            'POST method should not be allowed (405)'

    def test_for_delete_request(self, auth_token, sms_campaign_of_current_user):
        """
        DELETE method is not allowed on this endpoint, should get 405 (Method not allowed)
        :param auth_token: access token for sample user
        :param sms_campaign_of_current_user: fixture to create SMS campaign for current user
        :return:
        """
        response = requests.delete(
            SmsCampaignApiUrl.CAMPAIGN_SEND_PROCESS % sms_campaign_of_current_user.id,
            headers=dict(Authorization='Bearer %s' % auth_token))
        assert response.status_code == MethodNotAllowed.http_status_code(), \
            'DELETE method should not be allowed (405)'

    def test_post_with_invalid_token(self, sms_campaign_of_current_user):
        """
        User auth token is invalid, it should get Unauthorized.
        :return:
        """
        response = requests.post(
            SmsCampaignApiUrl.CAMPAIGN_SEND_PROCESS % sms_campaign_of_current_user.id,
            headers=dict(Authorization='Bearer %s' % 'invalid_token'))
        assert response.status_code == UnauthorizedError.http_status_code(), \
            'It should be unauthorized (401)'

    def test_post_with_valid_header_and_id_of_deleted_record(self, auth_token, valid_header,
                                                             sms_campaign_of_current_user):
        """
        User auth token is valid. It deletes the campaign from database and then tries
        to update the record. It should get Not Found error.
        :return:
        """
        response_delete = requests.delete(
            SmsCampaignApiUrl.CAMPAIGN % sms_campaign_of_current_user.id, headers=valid_header)
        assert response_delete.status_code == 200, 'should get ok response (200)'
        response_post = requests.post(
            SmsCampaignApiUrl.CAMPAIGN_SEND_PROCESS % sms_campaign_of_current_user.id,
            headers=dict(Authorization='Bearer %s' % auth_token))
        assert response_post.status_code == ResourceNotFound.http_status_code(), \
            'Record should not be found (404)'

    def test_post_with_valid_token_and_not_owned_campaign(self, auth_token,
                                                          sms_campaign_of_other_user):
        """
        User auth token is valid but user is not owner of given sms campaign.
        It should raise Forbidden error.
        :return:
        """
        response_post = requests.post(
            SmsCampaignApiUrl.CAMPAIGN_SEND_PROCESS % sms_campaign_of_other_user.id,
            headers=dict(Authorization='Bearer %s' % auth_token))
        assert response_post.status_code == ForbiddenError.http_status_code(), \
            'It should get forbidden error (403)'
        assert 'not the owner'.lower() in response_post.json()['error']['message'].lower()

    def test_post_with_valid_token_and_no_smartlist_associated(self, auth_token,
                                                               sms_campaign_of_current_user):
        """
        User auth token is valid but given sms campaign has no associated smart list with it.
        It should raise Forbidden error
        :return:
        """
        response_post = requests.post(
            SmsCampaignApiUrl.CAMPAIGN_SEND_PROCESS % sms_campaign_of_current_user.id,
            headers=dict(Authorization='Bearer %s' % auth_token))
        assert response_post.status_code == InternalServerError.http_status_code(), \
            'It should be internal server error (500)'
        assert response_post.json()['error'][
                   'code'] == SmsCampaignApiException.NO_SMARTLIST_ASSOCIATED
        assert 'No Smartlist'.lower() in response_post.json()['error']['message'].lower()

    def test_post_with_valid_token_and_no_smartlist_candidate(self, auth_token,
                                                              sms_campaign_of_current_user,
                                                              sms_campaign_smartlist):
        """
        User auth token is valid, campaign has one smart list associated. But smartlist has
        no candidate associated with it.
        :return:
        """
        response_post = requests.post(
            SmsCampaignApiUrl.CAMPAIGN_SEND_PROCESS % sms_campaign_of_current_user.id,
            headers=dict(Authorization='Bearer %s' % auth_token))
        assert response_post.status_code == InternalServerError.http_status_code(), \
            'It should be internal server error (500)'
        assert response_post.json()['error'][
                   'code'] == SmsCampaignApiException.NO_CANDIDATE_ASSOCIATED
        assert 'No Candidate'.lower() in response_post.json()['error']['message'].lower()

    def test_post_with_valid_token_one_smartlist_two_candidates_with_no_phone(
            self, auth_token, sample_user, sms_campaign_of_current_user, sms_campaign_smartlist,
            sample_sms_campaign_candidates):
        """
        User auth token is valid, campaign has one smart list associated. Smartlist has two
        candidates. Candidates have no phone number associated. So, total sends should be 0.
        :return:
        """
        response_post = requests.post(
            SmsCampaignApiUrl.CAMPAIGN_SEND_PROCESS % sms_campaign_of_current_user.id,
            headers=dict(Authorization='Bearer %s' % auth_token))
        assert response_post.status_code == 200, 'Response should be ok (200)'
        assert response_post.json()['total_sends'] == 0
        assert str(sms_campaign_of_current_user.id) in response_post.json()['message']
        assert_on_blasts_sends_url_conversion_and_activity(sample_user.id,
                                                            response_post,
                                                            str(sms_campaign_of_current_user.id))

    def test_post_with_valid_token_and_multiple_smartlists(
            self, auth_token, sample_user, sms_campaign_of_current_user, sms_campaign_smartlist,
            sms_campaign_smartlist_2, sample_sms_campaign_candidates, candidate_phone_1):
        """
        User auth token is valid, campaign has one smart list associated. Smartlist has two
        candidates. One candidate have no phone number associated. So, total sends should be 1.
        :return:
        """
        response_post = requests.post(
            SmsCampaignApiUrl.CAMPAIGN_SEND_PROCESS % sms_campaign_of_current_user.id,
            headers=dict(Authorization='Bearer %s' % auth_token))
        assert response_post.status_code == 200, 'Response should be ok (200)'
        assert response_post.json()['total_sends'] == 1
        assert str(sms_campaign_of_current_user.id) in response_post.json()['message']
        assert_on_blasts_sends_url_conversion_and_activity(sample_user.id, response_post,
                                                            str(sms_campaign_of_current_user.id))

    def valid_headertest_post_with_valid_token_one_smartlist_two_candidates_with_same_phone(
            self, auth_token, sms_campaign_of_current_user, sms_campaign_smartlist,
            sample_sms_campaign_candidates, candidates_with_same_phone):
        """
        User auth token is valid, campaign has one smart list associated. Smartlist has two
        candidates. Both candidates have same phone numbers. It should return Internal server error.
        Error code should be 5008 (MultipleCandidatesFound)
        :return:
        """
        response_post = requests.post(
            SmsCampaignApiUrl.CAMPAIGN_SEND_PROCESS % sms_campaign_of_current_user.id,
            headers=dict(Authorization='Bearer %s' % auth_token))
        assert response_post.status_code == InternalServerError.http_status_code(), \
            'It should be internal server error (500)'
        assert response_post.json()['error']['code'] == SmsCampaignApiException.MULTIPLE_CANDIDATES_FOUND
