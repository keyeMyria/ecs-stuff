"""
 Author: Jitesh Karesia, New Vision Software, <jitesh.karesia@newvisionsoftware.in>
         Um-I-Hani, QC-Technologies, <haniqadri.qc@gmail.com>
         Hafiz Muhammad Basit, QC-Technologies, <basit.gettalent@gmail.com>

This file contains function used by email-campaign-api.
"""
# Standard Imports
import re
import json
import uuid
import getpass
from time import sleep
from datetime import datetime

# Third Party
import boto3
from celery import chord
from requests import codes
from redo import retrier, retry
from sqlalchemy.exc import OperationalError

# Service Specific
from email_campaign_service.modules.email_clients import SMTP
from email_campaign_service.modules import aws_constants as aws
from email_campaign_service.json_schema.test_email import TEST_EMAIL_SCHEMA
from email_campaign_service.modules.validators import get_or_set_valid_value
from email_campaign_service.email_campaign_app import (logger, celery_app, app)
from email_campaign_service.modules.email_campaign_base import EmailCampaignBase
from email_campaign_service.modules.utils import (get_candidates_from_smartlist,
                                                  do_mergetag_replacements, create_email_campaign_url_conversions,
                                                  decrypt_password, get_priority_emails, get_topic_arn_and_region_name)
# Common Utils
from email_campaign_service.common.models.db import db
from email_campaign_service.common.models.user import Domain, User
from email_campaign_service.common.models.misc import (Frequency, Activity)
from email_campaign_service.common.utils.scheduler_utils import SchedulerUtils
from email_campaign_service.common.talent_config_manager import (TalentConfigKeys,
                                                                 TalentEnvs)
from email_campaign_service.common.routes import SchedulerApiUrl, EmailCampaignApiUrl
from email_campaign_service.common.campaign_services.campaign_base import CampaignBase
from email_campaign_service.common.campaign_services.campaign_utils import CampaignUtils
from email_campaign_service.common.campaign_services.custom_errors import CampaignException
from email_campaign_service.common.models.email_campaign import (EmailCampaign,
                                                                 EmailCampaignSmartlist,
                                                                 EmailCampaignBlast,
                                                                 EmailCampaignSend,
                                                                 EmailCampaignSendUrlConversion,
                                                                 TRACKING_URL_TYPE)
from email_campaign_service.common.models.candidate import (Candidate, CandidateEmail,
                                                            CandidateSubscriptionPreference)
from email_campaign_service.common.error_handling import (InvalidUsage, InternalServerError)
from email_campaign_service.common.utils.talent_reporting import email_notification_to_admins
from email_campaign_service.common.campaign_services.validators import validate_smartlist_ids
from email_campaign_service.common.utils.amazon_ses import (send_email, get_default_email_info)
from email_campaign_service.common.utils.handy_functions import (http_request, JSON_CONTENT_TYPE_HEADER)
from email_campaign_service.common.utils.validators import (raise_if_not_instance_of, get_json_data_if_validated,
                                                            raise_if_not_positive_int_or_long)
from email_campaign_service.common.inter_service_calls.candidate_pool_service_calls import get_candidates_of_smartlist
from email_campaign_service.common.inter_service_calls.candidate_service_calls import \
    get_candidate_subscription_preference
from email_campaign_service.common.custom_errors.campaign import (INVALID_REQUEST_BODY, INVALID_INPUT,
                                                                  ERROR_SENDING_EMAIL, SMARTLIST_NOT_FOUND,
                                                                  SMARTLIST_FORBIDDEN)


def create_email_campaign_smartlists(smartlist_ids, email_campaign_id):
    """ Maps smart lists to email campaign
    :param smartlist_ids:
    :type smartlist_ids: list[int | long]
    :param email_campaign_id: id of email campaign to which smart lists will be associated.
    """
    if type(smartlist_ids) in (int, long):
        smartlist_ids = [smartlist_ids]
    for smartlist_id in smartlist_ids:
        email_campaign_smartlist = EmailCampaignSmartlist(smartlist_id=smartlist_id,
                                                          campaign_id=email_campaign_id)
        EmailCampaignSmartlist.save(email_campaign_smartlist)


def create_email_campaign(user_id, oauth_token, name, subject, description, _from, reply_to, body_html,
                          body_text, list_ids, email_client_id=None, frequency_id=None,
                          email_client_credentials_id=None, base_campaign_id=None, start_datetime=None,
                          end_datetime=None):
    """
    Creates a new email campaign.
    Schedules email campaign.

    :return: newly created email_campaign's id
    """
    frequency = Frequency.get_seconds_from_id(frequency_id)
    email_campaign = EmailCampaign(name=name, user_id=user_id, is_hidden=0, subject=subject,
                                   description=description,
                                   _from=get_or_set_valid_value(_from, basestring, '').strip(),
                                   reply_to=get_or_set_valid_value(reply_to, basestring, '').strip(),
                                   body_html=body_html, body_text=body_text, start_datetime=start_datetime,
                                   end_datetime=end_datetime, frequency_id=frequency_id if frequency_id else None,
                                   email_client_id=email_client_id,
                                   email_client_credentials_id=email_client_credentials_id
                                   if email_client_credentials_id else None,
                                   base_campaign_id=base_campaign_id if base_campaign_id else None
                                   )
    EmailCampaign.save(email_campaign)
    user = User.get_by_id(user_id)
    # Create activity in a celery task
    celery_create_activity.delay(user_id, Activity.MessageIds.CAMPAIGN_CREATE, email_campaign,
                                 dict(id=email_campaign.id, name=name, campaign_type=CampaignUtils.get_campaign_type(email_campaign),
                                      username=user.name),
                                 'Error occurred while creating activity for email-campaign creation. User(id:%s)'
                                 % user_id)

    # create email_campaign_smartlist record
    create_email_campaign_smartlists(smartlist_ids=list_ids, email_campaign_id=email_campaign.id)

    # if it's a client from api, we don't schedule campaign sends, we create it on the fly.
    # also we enable tracking by default for the clients.
    if email_client_id:
        # If email is sent via email_client then enable tracking.
        email_campaign.isEmailOpenTracking = 1
        email_campaign.isTrackHtmlClicks = 1
        email_campaign.isTrackTextClicks = 1
        db.session.commit()  # Commit the changes
        # Actual emails are sent from the client. So no need to schedule it
        # TODO: Update campaign status to 'completed'
        return {'id': email_campaign.id}

    headers = {'Authorization': oauth_token}
    headers.update(JSON_CONTENT_TYPE_HEADER)
    send_url = EmailCampaignApiUrl.SEND % email_campaign.id

    if not start_datetime:  # Send campaign immediately
        send_response = http_request('post', send_url, headers=headers, user_id=user_id)
        if send_response.status_code != codes.OK:  # If failed to send the campaign
            raise InternalServerError("Error occurred while sending email-campaign. Status Code: %s, Response: %s"
                                      % (send_response.status_code, send_response.json()),
                                      ERROR_SENDING_EMAIL[1])
        logger.info('Email campaign(id:%s) is being sent immediately.' % email_campaign.id)
    else:  # Schedule the sending of emails & update email_campaign scheduler fields
        schedule_task_params = {"url": send_url}
        schedule_task_params.update(JSON_CONTENT_TYPE_HEADER)
        if frequency:  # It means its a periodic job, because frequency is 0 in case of one time job.
            schedule_task_params["frequency"] = frequency
            schedule_task_params["task_type"] = SchedulerUtils.PERIODIC  # Change task_type to periodic
            schedule_task_params["start_datetime"] = start_datetime
            schedule_task_params["end_datetime"] = end_datetime
        else:  # It means its a one time Job
            schedule_task_params["task_type"] = SchedulerUtils.ONE_TIME
            schedule_task_params["run_datetime"] = start_datetime
        schedule_task_params['is_jwt_request'] = True
        # Schedule email campaign; call Scheduler API
        try:
            scheduler_response = http_request('post', SchedulerApiUrl.TASKS, headers=headers,
                                              data=json.dumps(schedule_task_params), user_id=user_id)
        except Exception as ex:
            logger.exception('Exception occurred while calling scheduler. Exception: %s' % ex)
            raise
        if scheduler_response.status_code != codes.CREATED:
            raise InternalServerError("Error occurred while scheduling email campaign. "
                                      "Status Code: %s, Response: %s"
                                      % (scheduler_response.status_code, scheduler_response.json()))
        scheduler_id = scheduler_response.json()['id']
        # add scheduler task id to email_campaign.
        email_campaign.scheduler_task_id = scheduler_id

    db.session.commit()
    return {'id': email_campaign.id}


def send_email_campaign(current_user, campaign, new_candidates_only=False):
    """
    This function handles the actual sending of email campaign to candidates.
    Emails are sent to new candidates only if new_candidates_only is true. In case campaign has
    email_client_id associated with it (in case request came from browser plugins), we don't send
    actual emails and just send the required fields (new_html, new_text etc) back in response.
    Otherwise we get candidates from smartlists through celery and also send emails to those
    candidates via celery.
    :param User current_user: User object
    :param EmailCampaign campaign: Valid EmailCampaign object.
    :param bool new_candidates_only: True if email needs to be sent to those candidates whom emails were not
                                    sent previously
    """
    if not isinstance(campaign, EmailCampaign):
        raise InternalServerError(error_message='Must provide valid EmailCampaign object.')
    raise_if_not_instance_of(new_candidates_only, bool)
    campaign_id = campaign.id

    # Get smartlists of this campaign
    smartlist_ids = EmailCampaignSmartlist.get_smartlists_of_campaign(campaign_id, smartlist_ids_only=True)
    if not smartlist_ids:
        raise InvalidUsage(EmailCampaignBase.CustomErrors.NO_SMARTLIST_ASSOCIATED_WITH_CAMPAIGN[0],
                           error_code=EmailCampaignBase.CustomErrors.NO_SMARTLIST_ASSOCIATED_WITH_CAMPAIGN[1])
    # Validation for list ids belonging to same domain
    validate_smartlist_ids(smartlist_ids, current_user, error_code=INVALID_INPUT[1],
                           resource_not_found_error_code=SMARTLIST_NOT_FOUND[1],
                           forbidden_error_code=SMARTLIST_FORBIDDEN[1])

    if campaign.email_client_id:  # gt plugin code starts here.

        candidate_ids_and_emails, unsubscribed_candidate_ids = \
            get_email_campaign_candidate_ids_and_emails(campaign, smartlist_ids,
                                                        new_candidates_only=new_candidates_only)

        # Check if the valid candidates are present
        if not candidate_ids_and_emails:
            raise InvalidUsage('No candidates with emails found for email_campaign(id:%s).' % campaign.id,
                               error_code=EmailCampaignBase.CustomErrors.NO_VALID_CANDIDATE_FOUND)

        notify_admins(campaign, new_candidates_only, candidate_ids_and_emails)
        # Create blast for email-campaign
        email_campaign_blast = EmailCampaignBlast(campaign_id=campaign.id)
        EmailCampaignBlast.save(email_campaign_blast)
        _update_blast_unsubscribed_candidates(email_campaign_blast.id, len(unsubscribed_candidate_ids))
        list_of_new_email_html_or_text = []
        # Do not send mail if email_client_id is provided
        # Loop through each candidate and get new_html and new_text
        for candidate_id, candidate_address in candidate_ids_and_emails:
            new_text, new_html = get_new_text_html_subject_and_campaign_send(
                campaign.id, candidate_id, candidate_address, current_user, email_campaign_blast.id)[:2]
            logger.info("Marketing email added through client %s", campaign.email_client_id)
            resp_dict = dict(new_html=new_html, new_text=new_text, email=candidate_address)
            list_of_new_email_html_or_text.append(resp_dict)
        db.session.commit()

        # TODO: This will be needed later
        # update_candidate_document_on_cloud(user, candidate_ids_and_emails,
        #                                    new_candidates_only, campaign,
        #                                    len(list_of_new_email_html_or_text))
        # Update campaign blast with number of sends
        _update_blast_sends(email_campaign_blast.id, len(candidate_ids_and_emails), campaign, new_candidates_only)
        return list_of_new_email_html_or_text
    # For each candidate, create URL conversions and send the email via Celery task
    get_smartlist_candidates_via_celery(current_user.id, campaign_id, smartlist_ids, new_candidates_only)


def send_campaign_to_candidates(user_id, candidate_ids_and_emails, email_campaign_blast_id, campaign,
                                new_candidates_only):
    """
    This creates one Celery task per candidate to send campaign emails asynchronously.
    :param user_id: ID of user
    :param candidate_ids_and_emails: list of tuples containing candidate_ids and email addresses
    :param email_campaign_blast_id: id of email campaign blast object
    :param campaign: EmailCampaign object
    :param new_candidates_only: Identifier if candidates are new
    :type user_id: int | long
    :type candidate_ids_and_emails: list
    :type email_campaign_blast_id: int | long
    :type campaign: EmailCampaign
    :type new_candidates_only: bool
    """
    if not isinstance(campaign, EmailCampaign):
        raise InternalServerError(error_message='Must provide valid EmailCampaign object.')
    if not candidate_ids_and_emails:
        raise InternalServerError(error_message='No candidate data provided.')
    if not email_campaign_blast_id:
        raise InternalServerError(error_message='email_campaign_blast_id must be provided.')
    campaign_type = campaign.__tablename__
    callback = post_processing_campaign_sent.subtask((campaign, new_candidates_only, email_campaign_blast_id,),
                                                     queue=campaign_type)
    # Here we create list of all tasks.
    tasks = [send_email_campaign_to_candidate.subtask((user_id, campaign, candidate_id, candidate_address,
             email_campaign_blast_id), link_error=celery_error_handler(
             campaign_type), queue=campaign_type) for candidate_id, candidate_address in candidate_ids_and_emails]
    # This runs all tasks asynchronously and sets callback function to be hit once all
    # tasks in list finish running without raising any error. Otherwise callback
    # results in failure status.
    chord(tasks)(callback)


@celery_app.task(name='post_processing_campaign_sent')
def post_processing_campaign_sent(celery_result, campaign, new_candidates_only, email_campaign_blast_id):
    """
    Callback for all celery tasks sending campaign emails to candidates. celery_result would contain the return
    values of all the tasks, we would update the sends count with the number of email sending tasks that were
    successful.
    :param celery_result: result af all celery tasks
    :param campaign: Valid EmailCampaign object
    :param new_candidates_only: True if emails sent to new candidates only
    :param email_campaign_blast_id: Id of blast object for specified campaign
    :type celery_result: list
    :type campaign: EmailCampaign
    :type new_candidates_only: bool
    :type email_campaign_blast_id: int | long
    """
    with app.app_context():
        if not celery_result:
            logger.error('Celery task sending campaign(id;%s) emails failed' % campaign.id)
            return
        if not isinstance(campaign, EmailCampaign):
            logger.error('Campaign object is not valid')
            return
        if not isinstance(new_candidates_only, bool):
            logger.error('new_candidates_only must be bool')
            return
        if not isinstance(email_campaign_blast_id, (int, long)) or email_campaign_blast_id <= 0:
            logger.error('email_campaign_blast_id must be positive int or long')
            return
        sends = celery_result.count(True)
        logger.info('Campaigns sends:%s, celery_result: %s' % (sends, celery_result))
        _update_blast_sends(email_campaign_blast_id, sends, campaign,  new_candidates_only)


@celery_app.task(name='process_campaign_send')
def process_campaign_send(celery_result, user_id, campaign_id, list_ids, new_candidates_only=False):
    """
     Callback after getting candidate data of all smartlists. Results from all the smartlists
     are present in celery_result and we use that for further processing of the campaign. That includes
     filtering the results sending actual campaign emails.
     :param celery_result: Combined result of all celery tasks.
     :param user_id: Id of user.
     :param campaign_id: Campaign Id.
     :param list_ids: Ids of all smartlists associated with the campaigns.
     :param new_candidates_only: True if only new candidates need to be fetched.
     :type celery_result: list
     :type user_id: int | long
     :type campaign_id: int | long
     :type list_ids: list
     :type new_candidates_only: bool
    """
    all_candidate_ids = []
    with app.app_context():
        if not celery_result:
            logger.error('No candidate(s) found for smartlist_ids %s, campaign_id: %s'
                         'user_id: %s.' % list_ids, campaign_id, user_id)
            return
        if not isinstance(user_id, (int, long)) or user_id <= 0:
            logger.error('user_id must be positive int of long')
        if not isinstance(campaign_id, (int, long)) or campaign_id <= 0:
            logger.error('campaign_id must be positive int of long')
            return
        if not isinstance(list_ids, list) or len(list_ids) < 0:
            logger.error('list_ids are mandatory')
            return
        if not isinstance(new_candidates_only, bool):
            logger.error('new_candidates_only must be bool')
            return

    # gather all candidates from various smartlists
    for candidate_list in celery_result:
        all_candidate_ids.extend(candidate_list)
    all_candidate_ids = list(set(all_candidate_ids))  # Unique candidates
    logger.info('candidates count:%s, email_campaign_id:%s, candidate_ids: %s'
                % (len(all_candidate_ids), campaign_id, all_candidate_ids))
    campaign = EmailCampaign.get_by_id(campaign_id)
    # Filter valid candidate ids
    all_candidate_ids = CampaignBase.filter_existing_candidate_ids(all_candidate_ids, user_id)

    # Create blast for email-campaign
    email_campaign_blast = EmailCampaignBlast(campaign_id=campaign.id)
    EmailCampaignBlast.save(email_campaign_blast)
    blast_id = email_campaign_blast.id

    # Get subscribed and un-subscribed candidate ids
    subscribed_candidate_ids, unsubscribed_candidate_ids = \
        get_subscribed_and_unsubscribed_candidate_ids(campaign, all_candidate_ids, new_candidates_only)
    candidate_ids_and_emails = get_priority_emails(campaign.user, subscribed_candidate_ids)
    logger.info("subscribed_candidates_count:%s, filtered_candidates_count:%s, campaign_name=%s, "
                "campaign_id=%s, user=%s" % (len(subscribed_candidate_ids), len(candidate_ids_and_emails),
                                             campaign.name, campaign.id, campaign.user.email))
    if candidate_ids_and_emails:
        max_candidates_in_one_lambda = 50
        notify_admins(campaign, new_candidates_only, candidate_ids_and_emails)
        if app.config[TalentConfigKeys.ENV_KEY] in [TalentEnvs.QA]:
            # Get AWS region name
            _, region_name = get_topic_arn_and_region_name()
            try:
                _lambda = boto3.client('lambda', region_name=region_name)
            except Exception as error:
                logger.error("Couldn't get boto3 lambda client Error: %s" % error.message)
                return
            chunks_of_candidate_ids_list = (candidate_ids_and_emails[x:x + max_candidates_in_one_lambda] for x in
                                            xrange(0, len(candidate_ids_and_emails), max_candidates_in_one_lambda))
            number_of_lambda_invocations = 0
            for chunk in chunks_of_candidate_ids_list:
                chunk_of_candidate_ids_and_address = []
                for candidate_id_and_email in chunk:
                    candidate_id, candidate_address = candidate_id_and_email
                    chunk_of_candidate_ids_and_address.append({"candidate_id": candidate_id,
                                                               "candidate_address": candidate_address})
                event_data = {"blast_id": blast_id,
                              "candidates_data": chunk_of_candidate_ids_and_address}
                try:
                    invoke_lambda_sender(_lambda, event_data)
                    number_of_lambda_invocations += 1
                    # If email-campaign occupies all the Lambdas as specified by limit of concurrent Lambdas, and
                    # someone tries to invoke some Lambda, it will get Throttle error. Our intention here is to avoid
                    # Throttling. So, we are invoking specific number of Lambda's for email-campaign and then we wait
                    #  for some time so that all of them finish working and we can invoke next chunk of Lambdas.
                    if number_of_lambda_invocations % max_candidates_in_one_lambda == 0:
                        logger.info("Delaying Lambda invoker at %d" % number_of_lambda_invocations)
                        sleep(max_candidates_in_one_lambda)
                except Exception as error:
                    logger.error('Could not invoke Lambda. Error:%s, blast_id:%s, candidate_ids:%s'
                                 % (error.message, blast_id, chunk_of_candidate_ids_and_address))

            _update_blast_unsubscribed_candidates(email_campaign_blast.id, len(unsubscribed_candidate_ids))
            _update_blast_sends(blast_id=blast_id, new_sends=len(candidate_ids_and_emails), campaign=campaign,
                                new_candidates_only=new_candidates_only, update_blast_sends=False)
        else:  # TODO: Cutting off Celery for now and sending campaigns via Lambda on staging
            _update_blast_unsubscribed_candidates(email_campaign_blast.id, len(unsubscribed_candidate_ids))
            with app.app_context():
                logger.info('Emails for email campaign (id:%d) are being sent using Celery. Blast ID is %d' %
                            (campaign.id, email_campaign_blast.id))
            send_campaign_to_candidates(user_id, candidate_ids_and_emails, blast_id, campaign, new_candidates_only)


# This will be used in later version
# def update_candidate_document_on_cloud(user, candidate_ids_and_emails):
#     """
#     Once campaign has been sent to candidates, here we update their documents on cloud search.
#     :param user:
#     :param candidate_ids_and_emails:
#     :return:
#     """
#     try:
#         # Update Candidate Documents in Amazon Cloud Search
#         headers = CampaignBase.get_authorization_header(user.id)
#         headers.update(JSON_CONTENT_TYPE_HEADER)
#         with app.app_context():
#             response = requests.post(CandidateApiUrl.CANDIDATES_DOCUMENTS_URI, headers=headers,
#                                      data=json.dumps({'candidate_ids': map(itemgetter(0),
#                                                                            candidate_ids_and_emails)}))
#
#         if response.status_code != 204:
#             raise Exception("Status Code: %s Response: %s"
#                             % (response.status_code, response.json()))
#     except Exception as e:
#         error_message = "Couldn't update Candidate Documents in Amazon Cloud Search because: %s" \
#                         % e.message
#         logger.exception(error_message)
#         raise InvalidUsage(error_message)

def get_lambda_prefix():
    """
    Returns 'prod' if environment is Prod else returns 'staging'.
    :rtype: str
    """
    return 'prod' if app.config[TalentConfigKeys.ENV_KEY] == TalentEnvs.PROD else 'staging'


def invoke_lambda_sender(_lambda, event_data):
    """
    Here we invoke Lambda email sender
    """
    response = _lambda.invoke(FunctionName='%s-emailCampaignToCandidates:%s'
                                           % (get_lambda_prefix(), app.config[TalentConfigKeys.ENV_KEY].upper()),
                              InvocationType='Event',
                              Payload=json.dumps(event_data))
    logger.info("Invoked `emailCampaignToCandidates` Lambda for event:{}.\nResponse:{}".format(event_data, response))


def get_email_campaign_candidate_ids_and_emails(campaign, smartlist_ids, new_candidates_only=False):
    """
    Get candidate ids and email addresses for an email campaign
    :param campaign: EmailCampaign object
    :param smartlist_ids: List of ids of smartlists associated with given campaign
    :param new_candidates_only: True if campaign is to be sent only to new candidates.
    :type campaign: EmailCampaign
    :type smartlist_ids: list
    :type new_candidates_only: bool
    :return: Returns dict of unique candidate IDs in the campaign's smartlists.
    :rtype list
    """
    if not isinstance(campaign, EmailCampaign):
        raise InternalServerError(error_message='Must provide valid EmailCampaign object.')
    raise_if_not_instance_of(new_candidates_only, bool)
    all_candidate_ids = get_candidates_from_smartlist_for_email_client_id(campaign, smartlist_ids)
    if not all_candidate_ids:
        raise InternalServerError('No candidate(s) found for smartlist_ids %s.' % smartlist_ids,
                                  error_code=CampaignException.NO_CANDIDATE_ASSOCIATED_WITH_SMARTLIST)
    subscribed_candidate_ids, unsubscribed_candidate_ids = get_subscribed_and_unsubscribed_candidate_ids(campaign, all_candidate_ids, new_candidates_only)
    return get_priority_emails(campaign.user, subscribed_candidate_ids), unsubscribed_candidate_ids


def send_campaign_emails_to_candidate(user_id, campaign_id, candidate_id, candidate_address, email_campaign_blast_id):
    """
    This function sends the email to candidate. If working environment is prod, it sends the
    email campaigns to candidates' email addresses, otherwise it sends the email campaign to
    'gettalentmailtest@gmail.com' or email id of user.
    :param user_id: user object
    :param campaign_id: email campaign id
    :param candidate_id: candidate id
    :param candidate_address: candidate email address
    :param email_campaign_blast_id: id of email campaign blast object
    :type user_id: int | long
    :type campaign_id: int | long
    :type candidate_id: int | long
    :type candidate_address: str
    :type email_campaign_blast_id: int|long
    """
    raise_if_not_positive_int_or_long(user_id)
    raise_if_not_positive_int_or_long(campaign_id)
    raise_if_not_positive_int_or_long(candidate_id)
    raise_if_not_positive_int_or_long(email_campaign_blast_id)
    raise_if_not_instance_of(candidate_address, basestring)

    campaign = EmailCampaign.get_by_id(campaign_id)
    candidate = Candidate.get_by_id(candidate_id)
    current_user = User.get_by_id(user_id)
    new_text, new_html, subject, email_campaign_send = \
        get_new_text_html_subject_and_campaign_send(campaign.id, candidate_id, candidate_address,
                                                    current_user,
                                                    email_campaign_blast_id=email_campaign_blast_id)
    domain = Domain.get_by_id(campaign.user.domain_id)
    is_prod = not CampaignUtils.IS_DEV
    # Only in case of production we should send mails to candidate address else mails will
    # go to test account. To avoid spamming actual email addresses, while testing.
    to_address = app.config[TalentConfigKeys.GT_GMAIL_ID]
    if is_prod:
        # In case environment is Production and domain is test domain, send campaign to user's email address.
        if domain.is_test_domain:
            to_address = campaign.user.email
        # In case environment is Production and domain is not test domain, only then send campaign to candidates.
        else:
            to_address = candidate_address
    else:
        # In dev/staging, only send emails to getTalent users, in case we're impersonating a customer.
        domain_name = domain.name.lower()
        if domain.is_test_domain or any([name in domain_name for name in ['gettalent', 'bluth', 'dice']]):
            to_address = campaign.user.email
    logger.info("sending email-campaign(id:%s) to candidate(id:%s)'s email_address:%s"
                % (campaign_id, candidate_id, to_address))
    email_client_credentials_id = campaign.email_client_credentials_id
    if email_client_credentials_id:  # In case user wants to send email-campaign via added SMTP server.
        try:
            email_client_credentials = campaign.email_client_credentials
            decrypted_password = decrypt_password(email_client_credentials.password)
            client = SMTP(email_client_credentials.host, email_client_credentials.port,
                          email_client_credentials.email, decrypted_password)
            client.send_email(to_address, subject, new_text)
        except Exception as error:
            logger.exception('Error occurred while sending campaign via SMTP server. Error:%s' % error.message)
            return False
    else:
        try:
            default_email = get_default_email_info()['email']
            email_response = send_email(source='"%s" <%s>' % (campaign._from, default_email),
                                        # Emails will be sent from verified email by Amazon SES for respective
                                        #  environment.
                                        subject=subject,
                                        html_body=new_html or None,
                                        # Can't be '', otherwise, text_body will not show in email
                                        text_body=new_text,
                                        to_addresses=to_address,
                                        reply_address=campaign.reply_to.strip(),
                                        # BOTO doesn't seem to work with an array as to_addresses
                                        body=None,
                                        email_format='html' if campaign.body_html else 'text')
        except Exception as error:
            # Mark email as bounced
            _handle_email_sending_error(email_campaign_send, candidate.id, to_address, error)
            return False

        username = getpass.getuser()
        # Save SES message ID & request ID
        logger.info('''Marketing email(id:%s) sent successfully.
                       Recipients    : %s,
                       UserId        : %s,
                       System User Name: %s,
                       Environment   : %s,
                       Email Response: %s
                    ''', campaign_id, to_address, user_id, username, app.config[TalentConfigKeys.ENV_KEY],
                    email_response)
        request_id = email_response[u"SendEmailResponse"][u"ResponseMetadata"][u"RequestId"]
        message_id = email_response[u"SendEmailResponse"][u"SendEmailResult"][u"MessageId"]
        email_campaign_send.update(ses_message_id=message_id, ses_request_id=request_id)

    # Create activity in a celery task
    activity_message_id = CampaignUtils.get_campaign_activity_type_id(campaign, 'SEND')

    celery_create_activity.delay(campaign.user.id,
                                 activity_message_id,
                                 email_campaign_send,
                                 dict(campaign_name=campaign.name, candidate_name=candidate.name),
                                 'Could not add `campaign send activity` for email-campaign(id:%s) and User(id:%s)' %
                                 (campaign.id, campaign.user.id))
    return True


@celery_app.task(name='send_email_campaign_to_candidate')
def send_email_campaign_to_candidate(user_id, campaign, candidate_id, candidate_address, email_campaign_blast_id):
    """
    For each candidate, this function is called to send email campaign to candidate.
    :param user_id: Id of user
    :param campaign: EmailCampaign object
    :param candidate_id: candidate id
    :param candidate_address: candidate email address
    :param email_campaign_blast_id: email campaign blast object id.
    :type campaign: EmailCampaign
    :type candidate_id: int | long
    :type candidate_address: str
    :type email_campaign_blast_id: int|long
    :rtype bool
    """
    raise_if_not_positive_int_or_long(user_id)
    raise_if_not_instance_of(campaign, EmailCampaign)
    raise_if_not_positive_int_or_long(candidate_id)
    raise_if_not_instance_of(candidate_address, basestring)
    raise_if_not_positive_int_or_long(email_campaign_blast_id)

    with app.app_context():
        try:
            result_sent = send_campaign_emails_to_candidate(
                user_id=user_id,
                campaign_id=campaign.id,
                candidate_id=candidate_id,
                # candidates.find(lambda row: row.id == candidate_id).first(),
                candidate_address=candidate_address,
                email_campaign_blast_id=email_campaign_blast_id,
            )
            return result_sent
        except Exception as error:
            logger.exception('Error while sending email campaign(id:%s) to candidate(id:%s). Error is: %s'
                             % (campaign.id, candidate_id, error.message))
            db.session.rollback()
            return False


def get_new_text_html_subject_and_campaign_send(campaign_id, candidate_id, candidate_address, current_user,
                                                email_campaign_blast_id=None):
    """
    This gets new_html and new_text by URL conversion method and returns
        new_html, new_text, subject, email_campaign_send.
    :param campaign_id: EmailCampaign object id
    :param candidate_id: id of candidate
    :param candidate_address: Address of Candidate
    :param current_user: User object
    :param email_campaign_blast_id:  email campaign blast id
    :type campaign_id: int | long
    :type candidate_id: int | long
    :type candidate_address: basestring
    :type current_user: User
    :type email_campaign_blast_id: int | long | None
    """
    raise_if_not_positive_int_or_long(campaign_id)
    raise_if_not_positive_int_or_long(candidate_id)

    if email_campaign_blast_id:
        raise_if_not_positive_int_or_long(email_campaign_blast_id)

    # TODO: We should solve that detached instance issue more gracefully.
    candidate = Candidate.get_by_id(candidate_id)
    campaign = EmailCampaign.get_by_id(campaign_id)

    EmailCampaign.session.commit()
    email_campaign_send = EmailCampaignSend(campaign_id=campaign_id, candidate_id=candidate.id,
                                            blast_id=email_campaign_blast_id, ses_message_id=str(uuid.uuid4()))
    EmailCampaignSend.save(email_campaign_send)
    # If the campaign is a subscription campaign, its body & subject are
    # candidate-specific and will be set here
    if campaign.is_subscription:
        pass
    # from TalentJobAlerts import get_email_campaign_fields TODO: Job Alerts?
    #             campaign_fields = get_email_campaign_fields(candidate.id,
    #             do_email_business=do_email_business)
    #             If candidate has no matching job openings, don't send the email
    #             if campaign_fields['total_openings'] < 1:
    #                 return 0
    #             for campaign_field_name, campaign_field_value in campaign_fields.items():
    #                 campaign[campaign_field_name] = campaign_field_value
    new_html, new_text = campaign.body_html or "", campaign.body_text or ""
    logger.info('get_new_text_html_subject_and_campaign_send: campaign_id:%s, candidate_id: %s'
                % (campaign_id, candidate.id))

    # Perform MERGETAG replacements
    [new_html, new_text, subject] = do_mergetag_replacements([new_html, new_text, campaign.subject],
                                                             current_user, requested_object=candidate,
                                                             candidate_address=candidate_address)
    # Perform URL conversions and add in the custom HTML
    logger.info('get_new_text_html_subject_and_campaign_send: campaign_id:%s, email_campaign_send_id: %s'
                % (campaign_id, email_campaign_send.id))
    new_text, new_html = create_email_campaign_url_conversions(new_html=new_html,
                                                               new_text=new_text,
                                                               is_track_text_clicks=campaign.is_track_text_clicks,
                                                               is_track_html_clicks=campaign.is_track_html_clicks,
                                                               custom_url_params_json=campaign.custom_url_params_json,
                                                               is_email_open_tracking=campaign.is_email_open_tracking,
                                                               custom_html=campaign.custom_html,
                                                               email_campaign_send_id=email_campaign_send.id)
    return new_text, new_html, subject, email_campaign_send


def _handle_email_sending_error(email_campaign_send, candidate_id, to_addresses, exception):
    """
        If failed to send email; set the ses-request-id extracted from SES exception in email-campaign-send.
    """
    # If failed to send email, still try to get request id from XML response.
    # Unfortunately XML response is malformed so must manually parse out request id
    try:
        request_id_search = re.search('<RequestId>(.*)</RequestId>', exception.__str__(), re.IGNORECASE)
        request_id = request_id_search.group(1) if request_id_search else None
        email_campaign_send.update(ses_request_id=request_id)
    except Exception:
        # Log thee exception message
        logger.exception("Failed to send marketing email to candidate_id=%s, to_addresses=%s"
                         % (candidate_id, to_addresses))


def update_hit_count(url_conversion):
    try:
        # Increment hit count for email marketing
        new_hit_count = (url_conversion.hit_count or 0) + 1
        url_conversion.update(hit_count=new_hit_count, last_hit_time=datetime.utcnow())
        email_campaign_send_url_conversion = EmailCampaignSendUrlConversion.get_by_url_conversion_id(url_conversion.id)
        email_campaign_send = email_campaign_send_url_conversion.email_campaign_send
        candidate = Candidate.get_by_id(email_campaign_send.candidate_id)
        is_open = email_campaign_send_url_conversion.type == TRACKING_URL_TYPE
        # If candidate has been deleted, don't make the activity
        if not candidate or candidate.is_archived:
            logger.info("Tried performing URL redirect for nonexistent candidate: %s. "
                        "email_campaign_send: %s",
                        email_campaign_send.candidate_id, email_campaign_send.id)
        else:
            # Create activity in a celery task
            activity_open_message_id = CampaignUtils.get_campaign_activity_type_id(email_campaign_send.email_campaign,
                                                                                   'OPEN')
            activity_click_message_id = CampaignUtils.get_campaign_activity_type_id(email_campaign_send.email_campaign,
                                                                                    'CLICK')
            celery_create_activity.delay(candidate.user_id,
                                         activity_open_message_id if is_open
                                         else activity_click_message_id,
                                         email_campaign_send,
                                         dict(candidateId=candidate.id,
                                              campaign_name=email_campaign_send.email_campaign.name,
                                              candidate_name=candidate.formatted_name),
                                         'Error occurred while creating activity for email-campaign(id:%s) '
                                         'open/click.' % email_campaign_send.campaign_id)
            logger.info("Activity is being added for URL redirect for candidate(id:%s). "
                        "email_campaign_send(id:%s)",
                        email_campaign_send.candidate_id, email_campaign_send.id)

        # Update email_campaign_blast entry only if it's a new hit
        if new_hit_count == 1:
            retry(_assert_opens_or_clicks_updated, sleeptime=3, attempts=5, sleepscale=1,
                  args=(is_open, email_campaign_send), retry_exceptions=(AssertionError, OperationalError))
    except Exception:
        logger.exception("Received exception doing url_redirect (url_conversion_id=%s)",
                         url_conversion.id)


def _assert_opens_or_clicks_updated(is_open, email_campaign_send):
    """
    This asserts that opens/clicks count has been incremented for the blast object of given send object.
    :param bool is_open: Identifier if we need to update `opens` or `clicks`
    :param EmailCampaignSend email_campaign_send: EmailCampaignSend record
    """
    db.session.commit()  # To get the latest updates in database
    email_campaign_blast = EmailCampaignBlast.query.with_for_update(read=True).\
        filter_by(id=email_campaign_send.blast_id).first()
    count_updated = False
    if email_campaign_blast:
        if is_open:
            email_campaign_blast.update(opens=email_campaign_blast.opens + 1)
        else:
            email_campaign_blast.update(html_clicks=email_campaign_blast.html_clicks + 1)
        count_updated = True
    else:
        logger.error("Email campaign URL redirect: No email_campaign_blast found matching "
                     "email_campaign_send.sent_datetime %s, campaign_id=%s"
                     % (email_campaign_send.sent_datetime,
                        email_campaign_send.campaign_id))
    assert count_updated, \
        'There was an error updating opens/clicks count for email_campaign_blast(id:%s)' % email_campaign_blast.id


def get_subscription_preference(candidate_id):
    """
    If there are multiple subscription preferences (due to legacy reasons),
    if any one is 1-6, keep it and delete the rest.
    Otherwise, if any one is NULL, keep it and delete the rest.
    Otherwise, if any one is 7, delete all of them.
    :param candidate_id: id of candidate.
    :type candidate_id: bool
    :rtype int | None
    """
    raise_if_not_positive_int_or_long(candidate_id)
    # Not used but keeping it because same function was somewhere else in other service but using hardcoded ids.
    # So this one can be used to replace the old function.
    email_prefs = db.session.query(CandidateSubscriptionPreference).filter_by(
        candidate_id=candidate_id)
    non_custom_frequencies = db.session.query(Frequency.id).filter(
        Frequency.name.in_(Frequency.standard_frequencies().keys())).all()
    non_custom_frequency_ids = [non_custom_frequency[0] for non_custom_frequency in
                                non_custom_frequencies]
    non_custom_pref = email_prefs.filter(
        CandidateSubscriptionPreference.frequency_id.in_(
            non_custom_frequency_ids)).first()  # Other freqs.
    null_pref = email_prefs.filter(CandidateSubscriptionPreference.frequency_id == None).first()
    custom_frequency = Frequency.get_seconds_from_id(Frequency.CUSTOM)
    custom_pref = email_prefs.filter(
        CandidateSubscriptionPreference.frequency_id == custom_frequency.id).first()  # Custom freq.
    if non_custom_pref:
        all_other_prefs = email_prefs.filter(
            CandidateSubscriptionPreference.id != non_custom_pref.id)
        all_other_prefs_ids = [row.id for row in all_other_prefs]
        logger.info("get_subscription_preference: Deleting non-custom prefs for candidate %s: %s",
                    candidate_id, all_other_prefs_ids)
        db.session.query(CandidateSubscriptionPreference) \
            .filter(CandidateSubscriptionPreference.id.in_(all_other_prefs_ids)).delete(
            synchronize_session='fetch')
        return non_custom_pref
    elif null_pref:
        non_null_prefs = email_prefs.filter(CandidateSubscriptionPreference.id != null_pref.id)
        non_null_prefs_ids = [row.id for row in non_null_prefs]
        logger.info("get_subscription_preference: Deleting non-null prefs for candidate %s: %s",
                    candidate_id, non_null_prefs_ids)
        db.session.query(CandidateSubscriptionPreference).filter(
            CandidateSubscriptionPreference.id.in_(non_null_prefs_ids)).delete(
            synchronize_session='fetch')
        return null_pref
    elif custom_pref:
        email_prefs_ids = [row.id for row in email_prefs]
        logger.info("get_subscription_preference: Deleting all prefs for candidate %s: %s",
                    candidate_id,
                    email_prefs_ids)
        db.session.query(CandidateSubscriptionPreference).filter(
            CandidateSubscriptionPreference.id.in_(email_prefs_ids)).delete(
            synchronize_session='fetch')
        return None


def _update_blast_sends(blast_id, new_sends, campaign, new_candidates_only, update_blast_sends=True):
    """
    This updates the email campaign blast object with number of sends and logs that
    Marketing email batch completed.
    :param blast_id: Id of blast object.
    :param new_sends: Number of new sends.
    :param campaign: Email Campaign.
    :param new_candidates_only: True if campaign is to be sent to new candidates only.
    :type blast_id: int | long
    :type new_sends: int
    :type campaign: EmailCampaign
    :type new_candidates_only: bool
    """
    raise_if_not_positive_int_or_long(blast_id)
    raise_if_not_instance_of(new_sends, int)
    raise_if_not_instance_of(new_candidates_only, bool)
    if not isinstance(campaign, EmailCampaign):
        raise InternalServerError(error_message='Valid campaign object must be provided')

    blast_obj = EmailCampaignBlast.get_by_id(blast_id)
    if update_blast_sends:
        blast_obj.update(sends=new_sends)
    # This will be needed later
    # update_candidate_document_on_cloud(user, candidate_ids_and_emails)
    logger.info("Marketing email batch completed, emails sent=%s, "
                "campaign_name=%s, campaign_id=%s, user=%s, new_candidates_only=%s",
                new_sends, campaign.name, campaign.id, campaign.user.email, new_candidates_only)
    # Create activity in a celery task
    campaign_type = CampaignUtils.get_campaign_type(campaign)
    # Converting campaign type string to Title case string
    campaign_type = campaign_type.title()
    celery_create_activity.delay(campaign.user.id, Activity.MessageIds.CAMPAIGN_SEND, campaign,
                                 dict(id=campaign.id, name=campaign.name,
                                      num_candidates=new_sends, campaign_type=campaign_type),
                                 'Error occurred while creating activity for email-campaign(id:%s) batch send.'
                                 % campaign.id)


def _update_blast_unsubscribed_candidates(blast_id, unsubscribed_candidate_count):
    """
    This updates the email campaign blast object with number of unsubscribed candidates.
    :param blast_id: Id of blast object.
    :param unsubscribed_candidate_count: Number of unsubscribed candidates.
    :type blast_id: int | long
    :type unsubscribed_candidate_count: int
    """
    raise_if_not_positive_int_or_long(blast_id)
    raise_if_not_instance_of(unsubscribed_candidate_count, int)

    blast_obj = EmailCampaignBlast.get_by_id(blast_id)
    blast_obj.update(unsubscribed_candidates=unsubscribed_candidate_count)


def handle_email_bounce(message_id, bounce, emails):
    """
    This function handles email bounces. When an email is bounced, email address is marked as bounced so
    no further emails will be sent to this email address.
    It also updates email campaign bounces in respective blast.
    :param str message_id: message id associated with email send
    :param dict bounce: JSON bounce message body
    :param list[str] emails: list of bounced emails
    """
    assert isinstance(message_id, basestring) and message_id, "message_id should not be empty"
    assert isinstance(bounce, dict) and bounce, "bounce param should be a valid dict"
    assert isinstance(emails, list) and all(emails), "emails param should be a non empty list of email addresses"
    logger.info('Bounce Detected: %s', bounce)

    send_obj = None
    # get the corresponding EmailCampaignSend object that is associated with given AWS message id
    for _ in retrier(sleeptime=2, sleepscale=1, attempts=15):
        EmailCampaignSend.session.commit()
        send_obj = EmailCampaignSend.get_by_amazon_ses_message_id(message_id)
        if send_obj:  # found email campaign send, no need to retry
            break

    if not send_obj:
        logger.info("""Unable to find email campaign send for this email bounce.
                       MessageId: %s
                       Emails: %s
                       Bounce: %s""", message_id, emails, bounce)

    # Mark the send object as bounced.
    else:
        send_obj.update(is_ses_bounce=True)
        blast = EmailCampaignBlast.get_by_send(send_obj)

        if not blast:
            logger.error('Unable to find email campaign blast associated with email campaign send (id:%s).'
                         '\nBounce Message: %s', send_obj.id, bounce)
        # increase number of bounces by one for associated campaign blast.
        else:
            blast.update(bounces=(blast.bounces + 1))

    """
    There are two types of Bounces:
        1. Permanent Bounces: Bounces that are caused by invalid email address or an email that is
        in suppressed list.
        2. Temporary Bounces: Bounces that can be retried, caused by:
            - MailboxFull
            - MessageTooLarge
            - ContentRejected
            - AttachmentRejected
    """
    if bounce['bounceType'] == aws.PERMANENT_BOUNCE:
        # Mark the matching emails as bounced in all domains because an email that is invalid
        # would be invalid in all domains.
        CandidateEmail.mark_emails_bounced(emails)
        logger.info('Marked %s email addresses as bounced' % emails)
    elif bounce['bounceType'] == aws.TEMPORARY_BOUNCE:
        logger.info('Email was bounced as Transient. '
                    'We will not mark it bounced because it is a temporary problem')


def get_candidates_from_smartlist_for_email_client_id(campaign, list_ids):
    """
    Get candidates from smartlist in case client id is provided. It is a separate function
    because in case client id is provided, the candidate retrieving process needs not to
    be sent on celery.
    :param campaign: Valid EmailCampaign object.
    :param list_ids: List of smartlist ids associated with campaign.
    :type campaign: EmailCampaign
    :type list_ids: list
    :return: List of candidate ids.
    :rtype list
    """
    if not isinstance(campaign, EmailCampaign):
        raise InternalServerError("Valid email campaign must be provided.")
    if not isinstance(list_ids, list) or len(list_ids) <= 0:
        raise InternalServerError("Please provide list of smartlist ids.")
    all_candidate_ids = []
    for list_id in list_ids:
        # Get candidates present in smartlist
        try:
            smartlist_candidate_ids = get_candidates_of_smartlist(list_id, candidate_ids_only=True)
            # gather all candidates from various smartlists
            all_candidate_ids.extend(smartlist_candidate_ids)
        except Exception as error:
            logger.exception('Error occurred while getting candidates of smartlist(id:%s).'
                             'EmailCampaign(id:%s) User(id:%s). Reason: %s'
                             % (list_id, campaign.id, campaign.user.id, error.message))
    all_candidate_ids = list(set(all_candidate_ids))  # Unique candidates
    all_candidate_ids = CampaignBase.filter_existing_candidate_ids(all_candidate_ids, campaign.user.id)
    return all_candidate_ids


def get_subscribed_and_unsubscribed_candidate_ids(campaign, all_candidate_ids, new_candidates_only=False):
    """
    Takes campaign and all candidate ids as arguments and process them to return
    the ids of subscribed and unsubscribed candidates.
    :param campaign: email campaign
    :param all_candidate_ids: ids of all candidates to whom we are going to send campaign
    :param new_candidates_only: if campaign is to be sent only to new candidates
    :type campaign: EmailCampaign
    :type all_candidate_ids: list
    :type new_candidates_only: bool
    :return ids of subscribed and unsubscribed candidates
    :rtype tuple
    """
    if not isinstance(campaign, EmailCampaign):
        raise InternalServerError(error_message='Valid EmailCampaign object must be provided.')
    if not isinstance(all_candidate_ids, list) or len(all_candidate_ids) < 0:
        raise InternalServerError(error_message='all_candidates_ids must be provided')
    if not isinstance(new_candidates_only, bool):
        raise InternalServerError(error_message='new_candidates_only must be bool')
    unsubscribed_candidate_ids = []
    if campaign.is_subscription:
        # A subscription campaign is a campaign which needs candidates
        # to be subscribed to it in order to receive notifications regarding the campaign.
        # If the campaign is a subscription campaign,
        # only get candidates subscribed to the campaign's frequency.
        subscribed_candidate_ids = CandidateSubscriptionPreference.get_subscribed_candidate_ids(campaign,
                                                                                                all_candidate_ids)
        unsubscribed_candidate_ids = list(set(all_candidate_ids) - set(subscribed_candidate_ids))
        if not subscribed_candidate_ids:
            logger.error("No candidates in subscription campaign %s", campaign)

    else:
        # Otherwise, just filter out unsubscribed candidates:
        # their subscription preference's frequencyId is NULL, which means 'Never'
        logger.info('Getting subscription preference for candidates of email-campaign(id:{})'.format(campaign.id))
        for candidate_id in all_candidate_ids:
            subscription_preference = {}
            try:
                # Call candidate API to get candidate's subscription preference.
                subscription_preference = get_candidate_subscription_preference(candidate_id, campaign.user.id, app=app)
                # campaign_subscription_preference = get_subscription_preference(candidate_id)
            except Exception as error:
                logger.error('Could not get subscription preference for candidate(id:%s). '
                             'email-campaign(id:%s). Error:%s' % (candidate_id, campaign.id, error.message))
            if subscription_preference and not subscription_preference.get('frequency_id'):
                unsubscribed_candidate_ids.append(candidate_id)

        # Remove un-subscribed candidates
        subscribed_candidate_ids = list(set(all_candidate_ids) - set(unsubscribed_candidate_ids))
    # If only getting candidates that haven't been emailed before...
    if new_candidates_only:
        emailed_candidate_ids = EmailCampaignSend.get_already_emailed_candidates(campaign)

        # Filter out already emailed candidates from subscribed_candidate_ids, so we have new candidate_ids only
        new_candidate_ids = list(set(subscribed_candidate_ids) - set(emailed_candidate_ids))
        # assign it to subscribed_candidate_ids (doing it explicit just to make it clear)
        subscribed_candidate_ids = new_candidate_ids
    # Logging info of unsubscribed candidates.
    logger.info("Email campaign(id:%s). Subscribed candidates:%s, Unsubscribed candidates:%s. "
                "Unsubscribed candidate's ids are: %s" % (campaign.id, len(subscribed_candidate_ids),
                                                          len(unsubscribed_candidate_ids), unsubscribed_candidate_ids))
    return subscribed_candidate_ids, unsubscribed_candidate_ids


def get_smartlist_candidates_via_celery(user_id, campaign_id, smartlist_ids, new_candidates_only=False):
    """
    Get candidates of given smartlist by creating celery task for each smartlist.
    :param user_id: ID of user
    :param campaign_id: Email Campaign ID
    :param smartlist_ids: List of smartlist ids associated with given campaign
    :param new_candidates_only: True if only new candidates are to be returned.
    :type user_id: int | long
    :type campaign_id: int | long
    :type new_candidates_only: bool
    :type smartlist_ids: list
    :returns list of smartlist candidates
    :rtype list
    """
    raise_if_not_positive_int_or_long(user_id)
    raise_if_not_positive_int_or_long(campaign_id)
    raise_if_not_instance_of(new_candidates_only, bool)

    campaign = EmailCampaign.get_by_id(campaign_id)
    campaign_type = campaign.__tablename__

    # Get candidates present in each smartlist
    tasks = [get_candidates_from_smartlist.subtask((list_id, True, user_id),
                                                   link_error=celery_error_handler(campaign_type),
                                                   queue=campaign_type) for list_id in smartlist_ids]

    # Register function to be called after all candidates are fetched from smartlists
    callback = process_campaign_send.subtask((user_id, campaign_id, smartlist_ids, new_candidates_only,),
                                             queue=campaign_type)
    # This runs all tasks asynchronously and sets callback function to be hit once all
    # tasks in list finish running without raising any error. Otherwise callback
    # results in failure status.
    chord(tasks)(callback)


def notify_admins(campaign, new_candidates_only, candidate_ids_and_emails):
    """
    Notifies admins that email campaign is about to be sent shortly. Also returns blast params
    for the intended campaign.
    :param campaign: Email Campaign
    :param new_candidates_only: True if campaign needs to be sent to new candidates only.
    :param candidate_ids_and_emails: Ids and email addresses of candidates.
    :type campaign: EmailCampaign
    :type new_candidates_only: bool
    :type candidate_ids_and_emails: list
    """
    if not isinstance(campaign, EmailCampaign):
        raise InternalServerError('Valid EmailCampaign object must be provided.')
    if not candidate_ids_and_emails:
        raise InternalServerError(error_message='Candidate data not provided')
    logger.info("Marketing email batch about to send, campaign.name=%s, campaign.id=%s, user=%s, "
                "new_candidates_only=%s, address list size=%s"
                % (campaign.name, campaign.id, campaign.user.email, new_candidates_only,
                    len(candidate_ids_and_emails)))
    if not CampaignUtils.IS_DEV:  # Notify admins only if it is Production
        with app.app_context():
            email_notification_to_admins(
                subject='Marketing batch about to send',
                body="Marketing email batch about to send, campaign.name=%s, campaign.id=%s, user=%s, "
                     "new_candidates_only=%s, address list size=%s"
                     % (campaign.name, campaign.id, campaign.user.email, new_candidates_only,
                        len(candidate_ids_and_emails))
                    )


@celery_app.task(name='celery_error_handler')
def celery_error_handler(uuid):
    """
    This method is invoked whenever some error occurs.
    It rollbacks the transaction otherwise it will cause other transactions (if any) to fail.
    :param uuid:
    """
    db.session.rollback()


@celery_app.task(name='create_activity')
def celery_create_activity(user_id, _type, source, params, error_message="Error occurred while creating activity"):
    """
    This method creates activity for campaign create, delete, schedule etc. in a celery task.
    :param int | long user_id: id of user
    :param int _type: type of activity
    :param db.Model source: source object. Basically it will be Model object.
    :param dict params: activity params
    :param string error_message: error message to show in case of any exception
    """
    try:
        # Add activity
        CampaignBase.create_activity(user_id, _type, source, params)
    except Exception as e:
        logger.exception('%s\nError: %s' % (error_message, e.message))


def send_test_email(user, request):
    """
    This function sends a test email to given email addresses. Email sender depends on environment:
        - local-no-reply@gettalent.com for dev
        - staging-no-rely@gettalent.com for staging
        - no-reply@gettalent.com for Prod
    :param user: User model object (current user)
    :param request: Flask request object
    """
    # Get and validate request data
    try:
        data = get_json_data_if_validated(request, TEST_EMAIL_SCHEMA, custom_error_code=INVALID_INPUT[1])
    except InvalidUsage as error:
        raise InvalidUsage(error.message,
                           error_code=error.status_code if error.status_code else INVALID_REQUEST_BODY[1])

    body_text = data.get('body_text', '')
    reply_address = data.get('reply_to', '')
    [new_html, new_text, subject] = do_mergetag_replacements([data['body_html'], body_text, data['subject']],
                                                             request.user, requested_object=request.user)
    try:
        default_email = get_default_email_info()['email']
        send_email(source='"%s" <%s>' % (data['from'], default_email),
                   subject=subject,
                   html_body=new_html or None,
                   # Can't be '', otherwise, text_body will not show in email
                   text_body=new_text,
                   to_addresses=data['email_address_list'],
                   reply_address=reply_address or user.email,
                   body=None,
                   email_format='html')
        logger.info('Test email has been sent to %s addresses. User(id:%s)'
                    % (data['email_address_list'], request.user.id))
    except Exception as e:
        logger.error('Error occurred while sending test email. Error: %s', e)
        raise InternalServerError('Unable to send emails to test email addresses:%s.' % data['email_address_list'],
                                  error_code=ERROR_SENDING_EMAIL[1])
