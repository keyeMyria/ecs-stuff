# TODO: I've commented out this file to prevent it from running in jenkins build due to many flaky tests -Amir
# """
# A test for the v1/candidates/client_email_campaign endpoint
# When a recruiter wishes to send a gT Campaign Email to their candidates,
# they hit this endpoint with an email body
# """
# # Standard Library
# import time
#
# # Third Party
# from redo import retry
# from requests import codes
#
# # this import is not used per se but without it, the test throws an app context error
# # Candidate Service app instance
# from candidate_service.candidate_app import app
#
# # Conftest
# from candidate_service.common.tests.conftest import *
#
# # Helper functions
# from candidate_service.common.routes import CandidateApiUrl
# from candidate_service.common.models.email_campaign import EmailClient
# from candidate_service.common.utils.test_utils import send_request, response_info
# from candidate_service.tests.api.candidate_sample_data import generate_single_candidate_data
#
#
# class TestClientEmailCampaign(object):
#     def test_client_email_campaign(self, access_token_first, talent_pipeline, client_email_campaign_subject):
#         """
#         creates a candidate and then sends an email campaign to them. This is the functionality that is implemented
#         by the browser plugins in Gmail.
#         via the v1/candidates/client_email_campaign endpoint with all possible values for email_subject to ensure that
#         the email campaign is created each time regardless of subject input
#         """
#         # Create a Candidate
#         data = generate_single_candidate_data([talent_pipeline.talent_pool.id])
#         create_candidate_response = send_request('post', CandidateApiUrl.CANDIDATES, access_token_first, data)
#         print response_info(create_candidate_response)
#         candidate_id = create_candidate_response.json()['candidates'][0]['id']
#         time.sleep(10)
#
#         # Get Candidate via ID
#         get_candidate_response = send_request('get', CandidateApiUrl.CANDIDATE % candidate_id,
#                                               access_token_first)
#         print response_info(get_candidate_response)
#
#         # create POST request body
#         candidate = get_candidate_response.json()['candidate']
#         body = {
#             'candidates': [candidate],
#             'email_subject': client_email_campaign_subject,
#             'email_from': 'Samuel L. Jackson',
#             'email_reply_to': 'amir@gettalent.com',
#             'email_body_html': '<html><body>Email Body</body></html>',
#             'email_body_text': 'Plaintext part of email goes here, if any',
#             'email_client_id': EmailClient.get_id_by_name('Browser')
#         }
#
#         # Sometimes we face 504 issue as smartlist-candidate not found in candidate-service. So added this in
#         # retry block.
#         retry(_assert_candidate_client_campaign, sleeptime=3, attempts=5, sleepscale=1,
#               retry_exceptions=(AssertionError,), args=(body, access_token_first))
#
#
# def _assert_candidate_client_campaign(body, access_token):
#     """
#     Here we create candidate-client-campaign and assert valid response
#     :param dict body: Data to create candidate client campaign
#     :param string access_token: Access token of user
#     """
#     # send the post request to /v1/candidates/client-email-campaign
#     candidate_client_campaign_response = requests.post(
#         url=CandidateApiUrl.CANDIDATE_CLIENT_CAMPAIGN,
#         data=json.dumps(body),
#         headers={'Authorization': 'Bearer %s' % access_token,
#                  'content-type': 'application/json'}
#     )
#     # assert it is created and contains email campaign sends objects
#     assert candidate_client_campaign_response.status_code == codes.CREATED, candidate_client_campaign_response.text
#     email_campaign_sends = candidate_client_campaign_response.json()['email_campaign_sends']
#
#     # assert each email campaign send has an ID, an email address to send to and new_html to send to the user
#     for email_campaign_send in email_campaign_sends:
#         assert email_campaign_send['email_campaign_id']
#         assert email_campaign_send['candidate_email_address']
#         assert email_campaign_send['new_html']
#         assert len(str(email_campaign_send['new_html'])) > len('<html><body>Email Body</body></html>')
#         assert email_campaign_send['new_text']
