"""
Author: Hafiz Muhammad Basit, QC-Technologies, <basit.gettalent@gmail.com>

    This module contains pyTests for endpoint /v1/campaigns/:id/blasts/:id/replies of
    SMS Campaign API.
"""
# Third Party
import requests

# Common Utils
from sms_campaign_service.common.routes import SmsCampaignApiUrl
from sms_campaign_service.common.campaign_services.common_tests import CampaignsCommonTests
from sms_campaign_service.common.models.sms_campaign import (SmsCampaign, SmsCampaignBlast)

# Service Specific
from sms_campaign_service.tests.modules.common_functions import assert_ok_response_and_counts


class TestSmsCampaignBlastReplies(object):
    """
    This class contains tests for endpoint /v1/campaigns/:id/blasts/:id/replies
    """
    URL = SmsCampaignApiUrl.BLAST_REPLIES
    METHOD = 'get'
    ENTITY = 'replies'

    def test_get_with_invalid_token(self, sms_campaign_of_current_user, create_sms_campaign_blast):
        """
         User auth token is invalid. It should get Unauthorized error.
        :param sms_campaign_of_current_user: fixture to create SMS campaign for current user
        :return:
        """
        CampaignsCommonTests.request_with_invalid_token(
            self.METHOD, self.URL % (sms_campaign_of_current_user.id, create_sms_campaign_blast.id),
            None)

    def test_get_with_no_replies_on_campaign(self, access_token_first, sms_campaign_of_current_user,
                                             create_sms_campaign_blast):
        """
        Here we are assuming that SMS campaign has been sent to candidates.
        And we didn't receive any reply from candidate. Replies count should be 0.
        :param access_token_first: access token for sample user
        :param sms_campaign_of_current_user: fixture to create SMS campaign for current user
        :return:
        """
        response = requests.get(
            self.URL % (sms_campaign_of_current_user.id, create_sms_campaign_blast.id),
            headers=dict(Authorization='Bearer %s' % access_token_first))
        assert_ok_response_and_counts(response, entity=self.ENTITY)

    def test_get_with_deleted_campaign(self, access_token_first, sms_campaign_of_current_user,
                                       create_sms_campaign_blast):
        """
        It first deletes a campaign from database and try to get its replies for given blast_id.
        It should get ResourceNotFound error.
        :param access_token_first: access token for sample user
        :param sms_campaign_of_current_user: fixture to create SMS campaign for current user
        :return:
        """
        blast_id = create_sms_campaign_blast.id
        CampaignsCommonTests.request_after_deleting_campaign(
            sms_campaign_of_current_user, SmsCampaignApiUrl.CAMPAIGN,
            self.URL % ('%s', blast_id), self.METHOD, access_token_first)

    def test_get_with_one_blast_reply(self, access_token_first, candidate_phone_1,
                                      sms_campaign_of_current_user, create_sms_campaign_blast,
                                      create_campaign_replies):
        """
        This is the case where we assume we have blast saved with one reply.
        We are using fixtures to create campaign blast and blast replies..
        This uses fixture "sms_campaign_of_current_user" to create an SMS campaign and
        "create_campaign_replies" to create an entry in database table "sms_campaign_replies".
        Replies count should be 1.
        :param access_token_first: access token for sample user
        :param sms_campaign_of_current_user: fixture to create SMS campaign for current user
        :return:
        """
        response = requests.get(
            self.URL % (sms_campaign_of_current_user.id, create_sms_campaign_blast.id),
            headers=dict(Authorization='Bearer %s' % access_token_first))
        assert_ok_response_and_counts(response, count=1, entity=self.ENTITY)
        json_resp = response.json()[self.ENTITY][0]
        assert json_resp['blast_id'] == sms_campaign_of_current_user.blasts[0].id
        assert json_resp['candidate_phone_id'] == candidate_phone_1.id

    def test_get_with_not_owned_campaign(self, access_token_first, sms_campaign_of_other_user,
                                         create_sms_campaign_blast):
        """
        This is the case where we try to get blast of a campaign which was created by
        some other user. It should get Forbidden error.
        :return:
        """
        CampaignsCommonTests.request_for_forbidden_error(
            self.METHOD, self.URL % (sms_campaign_of_other_user.id, create_sms_campaign_blast.id),
            access_token_first)

    def test_get_with_blast_id_associated_with_not_owned_campaign(
            self, access_token_first, sms_campaign_of_current_user, create_blast_for_not_owned_campaign):
        """
        Here we assume that requested blast_id is associated with such a campaign for which
        logged-in user is not an owner. It should get Forbidden error.
        :param access_token_first: access token for sample user
        :param sms_campaign_of_current_user: fixture to create SMS campaign for current user
        :return:
        """
        CampaignsCommonTests.request_for_forbidden_error(
            self.METHOD,
            self.URL % (sms_campaign_of_current_user.id, create_blast_for_not_owned_campaign.id),
            access_token_first)

    def test_get_with_invalid_campaign_id(self, access_token_first, create_sms_campaign_blast):
        """
        This is a test to get blasts of a campaign which does not exists in database.
        :return:
        """
        CampaignsCommonTests.request_with_invalid_campaign_id(
            SmsCampaign, self.METHOD, self.URL % ('%s', create_sms_campaign_blast.id), access_token_first,
            None)

    def test_get_with_invalid_blast_id(self, access_token_first, sms_campaign_of_current_user):
        """
        This is a test to get blasts of a campaign using non-existing blast_id
        :return:
        """
        CampaignsCommonTests.request_with_invalid_campaign_id(
            SmsCampaignBlast, self.METHOD, self.URL % (sms_campaign_of_current_user.id, '%s'),
            access_token_first, None)
