"""
This module contains tests related to Push Campaign RESTful API endpoints.
"""
# Builtin imports
import time

# Application specific imports

from push_campaign_service.tests.test_utilities import *
from push_campaign_service.common.models.push_campaign import *
from push_campaign_service.common.routes import PushCampaignApiUrl

URL = PushCampaignApiUrl.BLAST_SENDS


class TestCampaignBlastSends(object):

    # Test URL: /v1/campaigns/<int:campaign_id>/blasts/<int:blast_id>/sends [GET]
    def test_get_campaign_blast_sends_with_invalid_id(self, campaign_in_db):
            # We are testing 401 here. so campaign and blast ids will not matter.
            unauthorize_test('get',  URL % (campaign_in_db.id, 1),
                             'invalid_token')

    def test_get_campaign_blast_sends(self, token, campaign_in_db, test_smartlist,
                                      campaign_blasts_count):

        # Wait for campaigns to be sent
        time.sleep(SLEEP_TIME)
        invalid_campaign_id = get_non_existing_id(PushCampaign)
        invalid_blast_id = get_non_existing_id(PushCampaignBlast)
        for blast in campaign_in_db.blasts.all():
            # 404 Case, Campaign not found
            # 404 with invalid campaign id and valid blast id
            response = send_request('get', URL
                                    % (invalid_campaign_id, blast.id), token)
            assert response.status_code == NOT_FOUND, 'Resource should not be found'

            # 404 with valid campaign id but invalid blast id
            response = send_request('get', URL
                                    % (campaign_in_db.id,invalid_blast_id), token)
            assert response.status_code == NOT_FOUND, 'Resource should not be found'

            # 200 case: Got Campaign Sends successfully
            response = send_request('get', URL
                                    % (campaign_in_db.id, blast.id), token)
            assert response.status_code == OK, 'Could not get campaign sends info'
            response = response.json()
            # Since each blast have one send, so total sends will be equal to number of blasts
            assert response['count'] == 1
            assert len(response['sends']) == 1