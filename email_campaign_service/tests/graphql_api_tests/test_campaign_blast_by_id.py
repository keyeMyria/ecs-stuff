"""
Here we have tests for getting particular blast of an email-campaign
"""
# Third Party
import pytest
import requests

# Application Specific
from ..conftest import GRAPHQL_BASE_URL
from email_campaign_service.common.utils.handy_functions import send_request
from email_campaign_service.common.tests.fake_testing_data_generator import fake
from email_campaign_service.common.campaign_services.tests_helpers import CampaignsTestsHelpers
from email_campaign_service.common.models.email_campaign import (EmailCampaignBlast, EmailCampaign)

__author__ = 'basit'


@pytest.mark.skipif(True, reason='graphQL has low priority for now')
class TestCampaignBlast(object):
    """
    This contains tests to get particular blast of an email-campaign
    """
    expected_fields_list = EmailCampaignBlast.get_fields()
    query_string = "query{email_campaign_query{blast(campaign_id:%s id:%s){%s}}}" \
                   % ('%d', '%d', ' '.join(expected_fields_list))

    def test_get_blast_without_auth_header(self):
        """
        Test to get campaign blast without auth header. It should get 'error' in JSON response.
        """
        query = {'query': self.query_string % (fake.random_int(), fake.random_int())}
        response = requests.get(GRAPHQL_BASE_URL, data=query)
        assert response.status_code == requests.codes.ok
        assert response.json()['errors']

    def test_get_blast_with_auth_header(self, access_token_first, sent_campaign):
        """
        Test to get blast of an email-campaign created by logged-in user with auth header. It should not get any
        error.
        """
        blast_id = sent_campaign.blasts[0].id
        query = {'query': self.query_string % (sent_campaign.id, blast_id)}
        response = send_request('get', GRAPHQL_BASE_URL, access_token_first, data=query)
        assert response.status_code == requests.codes.ok
        assert 'errors' not in response.json()
        blast = response.json()['data']['email_campaign_query']['blast']
        for expected_field in self.expected_fields_list:
            assert expected_field in blast, '%s not present in response' % expected_field

    def test_get_blast_in_same_domain(self, access_token_same, sent_campaign):
        """
        Test to get blast of a campaign created by some other user of same domain. It should not get any error.
        """
        blast_id = sent_campaign.blasts[0].id
        query = {'query': self.query_string % (sent_campaign.id, blast_id)}
        response = send_request('get', GRAPHQL_BASE_URL, access_token_same, data=query)
        assert response.status_code == requests.codes.ok
        assert 'errors' not in response.json()
        blast = response.json()['data']['email_campaign_query']['blast']
        for expected_field in self.expected_fields_list:
            assert expected_field in blast, '%s not present in response' % expected_field

    def test_get_blast_from_other_domain(self, access_token_other, sent_campaign):
        """
        Test to get campaign by user of some other domain. It should not get any blast.
        """
        blast_id = sent_campaign.blasts[0].id
        query = {'query': self.query_string % (sent_campaign.id, blast_id)}
        response = send_request('get', GRAPHQL_BASE_URL, access_token_other, data=query)
        assert response.status_code == requests.codes.ok
        assert 'errors' in response.json()
        assert response.json()['data']['email_campaign_query']['blast'] is None

    def test_get_non_existing_campaign(self, access_token_first):
        """
        Test to get blast of non-existing email-campaign. It should not get any blast object.
        """
        query = {'query': self.query_string % (CampaignsTestsHelpers.get_non_existing_id(EmailCampaign),
                                               fake.random_int())}
        response = send_request('get', GRAPHQL_BASE_URL, access_token_first, data=query)
        assert response.status_code == requests.codes.ok
        assert 'errors' in response.json()
        assert response.json()['data']['email_campaign_query']['blast'] is None

    def test_get_non_existing_blast(self, access_token_first, email_campaign_user1_domain1_in_db):
        """
        Test to get blast of non-existing blast. It should not get any blast.
        """
        query = {'query': self.query_string % (email_campaign_user1_domain1_in_db.id,
                                               CampaignsTestsHelpers.get_non_existing_id(EmailCampaignBlast),
                                               )}
        response = send_request('get', GRAPHQL_BASE_URL, access_token_first, data=query)
        assert response.status_code == requests.codes.ok
        assert 'errors' in response.json()
        assert response.json()['data']['email_campaign_query']['blast'] is None
