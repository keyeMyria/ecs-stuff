"""
Author: Hafiz Muhammad Basit, QC-Technologies, <basit.gettalent@gmail.com>

    This module contains pyTests for endpoint /v1/sms-campaigns/:id/send of SMS Campaign API.
"""
# Service Specific
import pytest
from requests import codes

from sms_campaign_service.common.utils.test_utils import get_and_assert_zero
from sms_campaign_service.sms_campaign_app import app
from sms_campaign_service.modules.sms_campaign_base import SmsCampaignBase
from sms_campaign_service.modules.custom_exceptions import (CandidateNotFoundInUserDomain,
                                                            SmsCampaignApiException)
# Common Utils
from sms_campaign_service.common.routes import SmsCampaignApiUrl
from sms_campaign_service.common.error_handling import InvalidUsage
from sms_campaign_service.common.models.sms_campaign import SmsCampaign
from sms_campaign_service.common.campaign_services.tests_helpers import CampaignsTestsHelpers, \
    assest_zero_blasts_and_sends
from sms_campaign_service.common.campaign_services.custom_errors import (CampaignException,
                                                                         MultipleCandidatesFound)


class TestSendSmsCampaign(object):
    """
    This class contains tests for endpoint /sms-campaigns/:id/send
    """
    URL = SmsCampaignApiUrl.SEND
    HTTP_METHOD = 'post'

    def test_post_with_invalid_token(self, sms_campaign_of_user_first):
        """
        User auth token is invalid, it should result in Unauthorized error.
        """
        CampaignsTestsHelpers.request_with_invalid_token(self.HTTP_METHOD,
                                                         self.URL % sms_campaign_of_user_first['id'],
                                                         None)

    def test_post_with_id_of_deleted_record(self, access_token_first,
                                            sms_campaign_of_user_first):
        """
        User auth token is valid. It first deletes the campaign from database and then tries
        to update the record. It should result in ResourceNotFound error.
        """
        CampaignsTestsHelpers.request_after_deleting_campaign(
            sms_campaign_of_user_first, SmsCampaignApiUrl.CAMPAIGN,
            self.URL, self.HTTP_METHOD, access_token_first)

    def test_post_with_campaign_in_some_other_domain(self, access_token_first,
                                                     sms_campaign_in_other_domain):
        """
        User auth token is valid but given SMS campaign does not belong to domain
        of logged-in user. It should result in Forbidden error.
        """
        CampaignsTestsHelpers.request_for_forbidden_error(self.HTTP_METHOD,
                                                          self.URL % sms_campaign_in_other_domain['id'],
                                                          access_token_first)

    @pytest.mark.parametrize("asynchronous", [True, False])
    def test_post_with_no_smartlist_associated(self, access_token_first,
                                               invalid_sms_campaign, asynchronous):
        """
        User auth token is valid but given SMS campaign has no associated smartlist with it. So
        up til this point we only have created a user and SMS campaign of that user (using fixtures
        passed in as params).
        It should result in Invalid usage error in synchronous mode and
        custom error should be NoSmartlistAssociatedWithCampaign but in asynchronous mode, it should return OK
        response.
        """
        CampaignsTestsHelpers.campaign_send_with_no_smartlist(self.URL % invalid_sms_campaign.id,
                                                              access_token_first, asynchronous=asynchronous)

    @pytest.mark.parametrize("asynchronous", [True, False])
    def test_post_with_no_smartlist_candidate(self, access_token_first,
                                              sms_campaign_with_no_candidate,
                                              talent_pipeline, asynchronous):
        """
        User auth token is valid, campaign has one smart list associated. But smartlist has
        no candidate associated with it. It should result in invalid usage error in synchronous mode and
        custom error should be NoCandidateAssociatedWithSmartlist but in asynchronous mode, it should return OK
        response.
        """
        campaign = SmsCampaign.get(sms_campaign_with_no_candidate['id'])
        with app.app_context():
            response_post = CampaignsTestsHelpers.campaign_send_with_no_smartlist_candidate(
                self.URL % campaign.id, access_token_first,
                campaign, talent_pipeline.id, asynchronous=asynchronous)
            if not asynchronous:
                error_resp = CampaignsTestsHelpers.assert_api_response(response_post,
                                                                       expected_status_code=InvalidUsage.http_status_code())
                assert error_resp['code'] == CampaignException.NO_CANDIDATE_ASSOCIATED_WITH_SMARTLIST
                assert error_resp['message']
            else:
                assert response_post.status_code == codes.OK
                get_and_assert_zero(SmsCampaignApiUrl.SENDS % campaign.id, 'sends', access_token_first)

    def test_post_with_invalid_campaign_id(self, access_token_first):
        """
        This is a test to update a campaign which does not exist in database.
        """
        CampaignsTestsHelpers.request_with_invalid_resource_id(SmsCampaign,
                                                               self.HTTP_METHOD,
                                                               self.URL,
                                                               access_token_first)

    @pytest.mark.parametrize("asynchronous", [True, False])
    def test_post_with_one_smartlist_two_candidates_with_no_phone(
            self, access_token_first, sms_campaign_with_no_valid_candidate, asynchronous):
        """
        User auth token is valid, campaign has one smart list associated. Smartlist has two
        candidates. Candidates have no phone number associated. So, total sends should be 0.
        """
        CampaignsTestsHelpers.campaign_test_with_no_valid_candidate(
            self.URL % sms_campaign_with_no_valid_candidate['id'], access_token_first,
            sms_campaign_with_no_valid_candidate['id'], asynchronous= asynchronous,
            campaign_service_urls=SmsCampaignApiUrl)

    def test_pre_process_celery_task_with_two_candidates_having_same_phone(
            self, user_first, sms_campaign_of_user_first, candidates_with_same_phone):
        """
        User auth token is valid, campaign has one smart list associated. Smartlist has two
        candidates. Both candidates have same phone numbers. It should get an empty list which
        shows candidates associated with smartlists of campaign are not valid.
        """
        candidate_1, candidate_2 = candidates_with_same_phone
        with app.app_context():
            obj = SmsCampaignBase(user_first.id, campaign_id=sms_campaign_of_user_first['id'])
            try:
                obj.pre_process_celery_task([candidate_1, candidate_2])
                assert None, 'Invalid usage should occur'
            except InvalidUsage as error:
                assert error.status_code == CampaignException.NO_VALID_CANDIDATE_FOUND

    def test_pre_process_celery_task_with_two_candidates_having_same_phone_in_diff_domain(
            self, user_first, sms_campaign_of_user_first,
            candidates_with_same_phone_in_diff_domains):
        """
        User auth token is valid. Campaign has one smartlist associated. Smartlist has two
        candidates. One candidate exists in more than one domains with same phone. It should
        not result in any error.
        """
        with app.app_context():
            obj = SmsCampaignBase(user_first.id, campaign_id=sms_campaign_of_user_first['id'])
            candidate_1, candidate_2 = candidates_with_same_phone_in_diff_domains
            assert len(obj.pre_process_celery_task([candidate_1, candidate_2])) == 1

    def test_pre_process_celery_task_with_valid_data(self, user_first,
                                                     sms_campaign_of_user_first):
        """
        User auth token is valid, campaign has one smart list associated. Smartlist has two
        candidates. Both candidates have different phone numbers. It should not result in any error.
        """
        with app.app_context():
            obj = SmsCampaignBase(user_first.id, campaign_id=sms_campaign_of_user_first['id'])
            assert len(obj.pre_process_celery_task(
                [user_first.candidates[0], user_first.candidates[1]])) == 2

    def test_does_candidate_have_unique_mobile_phone_with_two_candidates_having_same_phone(
            self, user_first, candidates_with_same_phone, sms_campaign_of_user_first):
        """
        User auth token is valid, campaign has one smart list associated. Smartlist has two
        candidates. Both candidates have same phone numbers. It should raise custom exception
        MultipleCandidatesFound.
        """
        try:
            candidate_1, candidate_2 = candidates_with_same_phone
            obj = SmsCampaignBase(user_first.id)
            obj.does_candidate_have_unique_mobile_phone(candidate_1)
            assert None, 'MultipleCandidatesFound exception should be raised.'
        except MultipleCandidatesFound as error:
            assert error.error_code == CampaignException.MULTIPLE_CANDIDATES_FOUND

    def test_does_candidate_have_unique_mobile_phone_with_candidate_in_other_domain(
            self, user_first, sms_campaign_of_user_first, candidate_phone_in_other_domain):
        """
        User auth token is valid, campaign has one smart list associated. Smartlist has one
        candidate but candidate belongs to some other domain.
        It should raise custom exception CandidateNotFoundInUserDomain.
        """
        try:
            candidate_1 = candidate_phone_in_other_domain.candidate
            obj = SmsCampaignBase(user_first.id)
            obj.does_candidate_have_unique_mobile_phone(candidate_1)
            assert None, 'CandidateNotFoundInUserDomain exception should be raised.'
        except CandidateNotFoundInUserDomain as error:
            assert error.error_code == SmsCampaignApiException.NO_CANDIDATE_IN_USER_DOMAIN
