# Standard Imports
import json
import time
import uuid
import imaplib
import datetime

# Third Party
import requests

# Application Specific
from __init__ import ALL_EMAIL_CAMPAIGN_FIELDS
from email_campaign_service.common.models.db import db
from email_campaign_service.email_campaign_app import app
from email_campaign_service.common.tests.conftest import fake
from email_campaign_service.common.models.user import DomainRole
from email_campaign_service.common.models.misc import (Activity,
                                                       UrlConversion, Frequency)
from email_campaign_service.common.routes import (EmailCampaignUrl,
                                                  CandidatePoolApiUrl)
from email_campaign_service.common.models.email_campaign import EmailCampaign
from email_campaign_service.common.utils.validators import raise_if_not_instance_of
from email_campaign_service.common.utils.handy_functions import (add_role_to_test_user,
                                                                 define_and_send_request)
from email_campaign_service.modules.email_marketing import create_email_campaign_smartlists
from email_campaign_service.common.tests.fake_testing_data_generator import FakeCandidatesData
from email_campaign_service.common.inter_service_calls.candidate_pool_service_calls import \
    create_smartlist_from_api
from email_campaign_service.common.utils.candidate_service_calls import \
    create_candidates_from_candidate_api
from email_campaign_service.common.campaign_services.tests_helpers import CampaignsTestsHelpers

__author__ = 'basit'


def create_email_campaign(user):
    """
    This creates an email campaign for given user
    """
    email_campaign = EmailCampaign(name=fake.name(),
                                   user_id=user.id,
                                   is_hidden=0,
                                   subject=uuid.uuid4().__str__()[0:8] + ' Its a test campaign',
                                   _from=fake.safe_email(),
                                   reply_to=fake.email(),
                                   body_html="<html><body>Email campaign test</body></html>",
                                   body_text="Email campaign test"
                                   )
    EmailCampaign.save(email_campaign)
    return email_campaign


def assign_roles(user):
    """
    This assign required permission to given user
    :param user:
    :return:
    """
    add_role_to_test_user(user, [DomainRole.Roles.CAN_ADD_CANDIDATES,
                                 DomainRole.Roles.CAN_GET_CANDIDATES])


def create_email_campaign_smartlist(access_token, talent_pipeline, campaign,
                                    emails_list=True, count=1):
    """
    This associates smartlist ids with given campaign
    """
    # create candidate
    smartlist_id, _ = create_smartlist_with_candidate(access_token, talent_pipeline,
                                                      emails_list=emails_list,
                                                      count=count)

    create_email_campaign_smartlists(smartlist_ids=[smartlist_id],
                                     email_campaign_id=campaign.id)
    return campaign


def create_smartlist_with_candidate(access_token, talent_pipeline, emails_list=True, count=1, data=None):
    """
    This creates candidate(s) as specified by the count,  and assign it to a smartlist.
    Finally it returns smartlist_id and candidate_ids.
    """
    if not data:
        # create candidate
        data = FakeCandidatesData.create(talent_pool=talent_pipeline.talent_pool,
                                         emails_list=emails_list, count=count)

    candidate_ids = create_candidates_from_candidate_api(access_token, data,
                                                         return_candidate_ids_only=True)
    time.sleep(25)  # added due to uploading candidates on CS
    smartlist_data = {'name': fake.word(),
                      'candidate_ids': candidate_ids,
                      'talent_pipeline_id': talent_pipeline.id}

    smartlists = create_smartlist_from_api(data=smartlist_data, access_token=access_token)
    time.sleep(25)  # added due to new field dumb_list_ids in CS
    smartlist_id = smartlists['smartlist']['id']
    return smartlist_id, candidate_ids


def create_smartlist_with_given_email_candidate(access_token, campaign,
                                                talent_pipeline, emails_list=True,
                                                count=1, emails=None):
    """
    This creates candidate(s) as specified by the count, using the email list provided by the user
    and assign it to a smartlist.
    Finally it returns campaign object
    """
    # create candidates data
    data = FakeCandidatesData.create(talent_pool=talent_pipeline.talent_pool,
                                     emails_list=emails_list, count=count)

    if emails and emails_list:
        for index, candidate in enumerate(data['candidates']):
            candidate['emails'] = emails[index]

    smartlist_id, _ = create_smartlist_with_candidate(access_token, talent_pipeline, data=data)
    create_email_campaign_smartlists(smartlist_ids=[smartlist_id],
                                     email_campaign_id=campaign.id)

    return campaign


def delete_campaign(campaign):
    """
    This deletes the campaign created during tests from database
    :param campaign: Email campaign object
    """
    try:
        with app.app_context():
            if isinstance(campaign, dict):
                EmailCampaign.delete(campaign['id'])
            else:
                EmailCampaign.delete(campaign.id)
    except Exception:
        pass


def send_campaign(campaign, access_token, sleep_time=20):
    """
    This function sends the campaign via /v1/email-campaigns/:id/send
    sleep_time is set to be 20s here. One can modify this by passing required value.
    :param campaign: Email campaign obj
    :param access_token: Auth token to make HTTP request
    :param sleep_time: time in seconds to wait for the task to be run on Celery.
    """
    raise_if_not_instance_of(campaign, EmailCampaign)
    raise_if_not_instance_of(access_token, basestring)
    # send campaign
    response = requests.post(EmailCampaignUrl.SEND % campaign.id,
                             headers=dict(Authorization='Bearer %s' % access_token))
    assert response.ok
    time.sleep(sleep_time)
    db.session.commit()
    return response


def assert_valid_campaign_get(email_campaign_dict, referenced_campaign, fields=None):
    """
    This asserts that the campaign we get from GET call has valid values as we have for
    referenced email-campaign.
    :param dict email_campaign_dict: EmailCampaign object as received by GET call
    :param referenced_campaign: EmailCampaign object by which we compare the campaign
            we GET in response
    :param list[str] fields: List of fields that the campaign should have, or all of them if None
    """

    # Assert the fields are correct
    expected_email_campaign_fields_set = set(fields or ALL_EMAIL_CAMPAIGN_FIELDS)
    actual_email_campaign_fields_set = set(email_campaign_dict.keys())
    assert expected_email_campaign_fields_set == actual_email_campaign_fields_set, \
        "Response's email campaign fields (%s) should match the expected email campaign fields (%s)" % (
            actual_email_campaign_fields_set, expected_email_campaign_fields_set
        )

    # Assert id is correct, if returned by API
    if 'id' in expected_email_campaign_fields_set:
        assert email_campaign_dict['id'] == referenced_campaign.id


def get_campaign_or_campaigns(access_token, campaign_id=None, fields=None, pagination_query=None):
    """
    This makes HTTP GET call on /v1/email-campaigns with given access_token to get
    1) all the campaigns of logged-in user if campaign_id is None
    2) Get campaign object for given campaign_id
    :param list[str] fields: List of EmailCampaign fields to retrieve
    """
    if campaign_id:
        url = EmailCampaignUrl.CAMPAIGN % campaign_id
        entity = 'email_campaign'
    else:
        url = EmailCampaignUrl.CAMPAIGNS
        entity = 'email_campaigns'
    if pagination_query:
        url = url + pagination_query

    params = {'fields': ','.join(fields)} if fields else {}
    response = requests.get(url=url,
                            params=params,
                            headers={'Authorization': 'Bearer %s' % access_token})
    assert response.status_code == requests.codes.OK
    resp = response.json()
    assert entity in resp
    return resp[entity]


def assert_talent_pipeline_response(talent_pipeline, access_token, fields=None):
    """
    This makes HTTP GET call on candidate_pool_service to get response for given
    talent_pipeline and then asserts if we get an OK response.
    :param list[str] fields:  List of fields each EmailCampaign should have.  If None, will assert on all fields.
    """
    params = {'fields': ','.join(fields)} if fields else {}
    response = requests.get(
        url=CandidatePoolApiUrl.TALENT_PIPELINE_CAMPAIGN % talent_pipeline.id,
        params=params,
        headers={'Authorization': 'Bearer %s' % access_token})
    assert response.status_code == requests.codes.OK
    resp = response.json()
    print "Response JSON: %s" % json.dumps(resp)
    assert 'email_campaigns' in resp, "Response dict should have email_campaigns key"

    # Assert on the existence of email campaign fields
    for email_campaign_dict in resp['email_campaigns']:
        expected_email_campaign_fields_set = set(fields or ALL_EMAIL_CAMPAIGN_FIELDS)
        actual_email_campaign_fields_set = set(email_campaign_dict.keys())
        assert expected_email_campaign_fields_set == actual_email_campaign_fields_set, \
            "Response's email campaign fields should match the expected email campaign fields"


def assert_and_delete_email(subject):
    """
    Asserts that the user received the email in his inbox which has the given subject.
    It then deletes the email from the inbox.
    :param subject:       Email subject
    """
    mail_connection = imaplib.IMAP4_SSL('imap.gmail.com')
    try:
        mail_connection.login('gettalentmailtest@gmail.com', 'GetTalent@1234')
    except Exception:
        pass # Maybe already login when running on Jenkins on multiple cores
    print "Checking for Email with subject: %s" % subject
    mail_connection.select("inbox")  # connect to inbox.
    # search the inbox for given email-subject
    result, [msg_ids] = mail_connection.search(None, '(SUBJECT "%s")' % subject)
    assert msg_ids, "Email with subject %s was not found." % subject
    print "Email(s) found with subject: %s" % subject
    msg_ids = ','.join(msg_ids.split(' '))
    # Change the Deleted flag to delete the email from Inbox
    mail_connection.store(msg_ids, '+FLAGS', r'(\Deleted)')
    status, response = mail_connection.expunge()
    assert status == 'OK'
    print "Email(s) deleted with subject: %s" % subject


def assert_campaign_send(response, campaign, user, expected_count=1, email_client=False,
                         expected_status=200):
    """
    This assert that campaign has successfully been sent to candidates and campaign blasts and
    sends have been updated as expected. It then checks the source URL is correctly formed or
    in database table "url_conversion".
    """
    assert response.status_code == expected_status
    assert response.json()
    if not email_client:
        json_resp = response.json()
        assert str(campaign.id) in json_resp['message']
    # Need to add this as processing of POST request runs on Celery
    time.sleep(40)
    db.session.commit()
    assert len(campaign.blasts.all()) == 1
    campaign_blast = campaign.blasts[0]
    assert campaign_blast.sends == expected_count
    # assert on sends
    campaign_sends = campaign.sends.all()
    assert len(campaign_sends) == expected_count
    sends_url_conversions = []
    # assert on activity of individual campaign sends
    for campaign_send in campaign_sends:
        # Get "email_campaign_send_url_conversion" records
        sends_url_conversions.extend(campaign_send.url_conversions)
        if not email_client:
            CampaignsTestsHelpers.assert_for_activity(user.id,
                                                      Activity.MessageIds.CAMPAIGN_EMAIL_SEND,
                                                      campaign_send.id)
    if campaign_sends:
        # assert on activity for whole campaign send
        CampaignsTestsHelpers.assert_for_activity(user.id,
                                                  Activity.MessageIds.CAMPAIGN_SEND,
                                                  campaign.id)

    # For each url_conversion record we assert that source_url is saved correctly
    for send_url_conversion in sends_url_conversions:
        # get URL conversion record from database table 'url_conversion' and delete it
        # delete url_conversion record
        assert str(
            send_url_conversion.url_conversion.id) in send_url_conversion.url_conversion.source_url
        UrlConversion.delete(send_url_conversion.url_conversion)


def post_to_email_template_resource(access_token, data):
    """
    Function sends a post request to email-templates,
    i.e. EmailTemplate/post()
    """
    response = requests.post(url=EmailCampaignUrl.TEMPLATES,
                             data=json.dumps(data),
                             headers={'Authorization': 'Bearer %s' % access_token,
                                      'Content-type': 'application/json'}
                             )
    return response


def request_to_email_template_resource(access_token, request, email_template_id, data=None):
    """
    Function sends a request to email template resource
    :param access_token: Token for user authorization
    :param request: get, post, patch, delete
    :param email_template_id: Id of email template
    :param data: data in form of dictionary
    """
    url = EmailCampaignUrl.TEMPLATES + '/' + str(email_template_id)
    return define_and_send_request(access_token, request, url, data)


def get_template_folder(token):
    """
    Function will create and retrieve template folder
    :param token:
    :return: template_folder_id, template_folder_name
    """
    template_folder_name = 'test_template_folder_%i' % datetime.datetime.now().microsecond

    data = {'name': template_folder_name}
    response = requests.post(url=EmailCampaignUrl.TEMPLATES_FOLDER, data=json.dumps(data),
                             headers={'Authorization': 'Bearer %s' % token,
                             'Content-type': 'application/json'})
    assert response.status_code == requests.codes.CREATED
    response_obj = response.json()
    template_folder_id = response_obj["template_folder_id"][0]
    return template_folder_id['id'], template_folder_name


def create_email_template(token, user_id, template_name, body_html, body_text, is_immutable=1,
                          folder_id=None):
    """
    Creates a email campaign template with params provided

    :param token
    :param user_id:                 User id
    :param template_name:           Template name
    :param body_html:               Body html
    :param body_text:               Body text
    :param is_immutable:            1 if immutable, otherwise 0
    :param folder_id:               folder id
    """
    data = dict(
            name=template_name,
            template_folder_id=folder_id,
            user_id=user_id,
            type=0,
            body_html=body_html,
            body_text=body_text,
            is_immutable=is_immutable
    )

    create_resp = post_to_email_template_resource(token, data=data)
    return create_resp


def update_email_template(email_template_id, request, token, user_id, template_name, body_html, body_text='',
                          folder_id=None, is_immutable=1):
    """
        Update existing email template fields using values provided by user.
        :param email_template_id: id of email template
        :param request: request object
        :param token: token for authentication
        :param user_id: user's id
        :param template_name: Name of template
        :param body_html: HTML body for email template
        :param body_text: HTML text for email template
        :param folder_id: ID of email template folder
        :param is_immutable: Specify whether the email template is mutable or not
    """
    data = dict(
            name=template_name,
            template_folder_id=folder_id,
            user_id=user_id,
            type=0,
            body_html=body_html,
            body_text=body_text,
            is_immutable=is_immutable
    )

    create_resp = request_to_email_template_resource(token, request, email_template_id, data)
    return create_resp


def add_email_template(token, template_owner, template_body):
    """
    This function will create email template
    """
    domain_id = template_owner.domain_id

    # Add 'CAN_CREATE_EMAIL_TEMPLATE' to template_owner
    add_role_to_test_user(template_owner, [DomainRole.Roles.CAN_CREATE_EMAIL_TEMPLATE,
                                           DomainRole.Roles.CAN_CREATE_EMAIL_TEMPLATE_FOLDER])

    # Get Template Folder Id
    template_folder_id, template_folder_name = get_template_folder(token)

    template_name = 'test_email_template%i' % datetime.datetime.now().microsecond
    is_immutable = 1
    resp = create_email_template(token, template_owner.id, template_name, template_body, '', is_immutable,
                                 folder_id=template_folder_id)
    db.session.commit()
    resp_obj = resp.json()
    resp_dict = resp_obj['template_id'][0]

    return {"template_id": resp_dict['id'],
            "template_folder_id": template_folder_id,
            "template_folder_name": template_folder_name,
            "template_name": template_name,
            "is_immutable": is_immutable,
            "domain_id": domain_id}


def template_body():
    return '<!DOCTYPE html PUBLIC "-//W3C//DTD XHTML 1.0 Transitional//EN" ' \
           '"http://www.w3.org/TR/xhtml1/DTD/xhtml1-transitional.dtd">\r\n<html>\r\n<head>' \
           '\r\n\t<title></title>\r\n</head>\r\n<body>\r\n<p>test campaign mail testing through script</p>' \
           '\r\n</body>\r\n</html>\r\n'


def create_email_campaign_via_api(access_token, data, is_json=True):
    """
    This function makes HTTP POST call on /v1/email-campaigns to create
    an email-campaign. It then returns the response from email-campaigns API.
    :param access_token: access token of user
    :param data: data required for creation of campaign
    :param is_json: If True, it will take dumps of data to be sent in POST call. Otherwise it
                    will send data as it is.
    :return: response of API call
    """
    if is_json:
        data = json.dumps(data)
    response = requests.post(
        url=EmailCampaignUrl.CAMPAIGNS,
        data=data,
        headers={'Authorization': 'Bearer %s' % access_token,
                 'content-type': 'application/json'}
    )
    return response


def create_data_for_campaign_creation(access_token, talent_pipeline, subject, campaign_name=fake.name()):
    """
    This function returns the required data to create an email campaign
    :param access_token: access token of user
    :param talent_pipeline: talent_pipeline of user
    :param subject: Subject of campaign
    :param campaign_name: Name of campaign
    """
    email_from = 'no-reply@gettalent.com'
    reply_to = fake.safe_email()
    body_text = fake.sentence()
    body_html = "<html><body><h1>%s</h1></body></html>" % body_text
    smartlist_id, _ = create_smartlist_with_candidate(access_token, talent_pipeline)
    return {'name': campaign_name,
            'subject': subject,
            'from': email_from,
            'reply_to': reply_to,
            'body_html': body_html,
            'body_text': body_text,
            'frequency_id': Frequency.ONCE,
            'list_ids': [smartlist_id]
            }
