"""
Author: Hafiz Muhammad Basit, QC-Technologies, <basit.gettalent@gmail.com>

This module contains CampaignBase class which provides common methods for
all campaigns. Methods are
- schedule()
- get_smartlist_candidates()
- create_or_update_url_conversion()
- create_activity()
- get_campaign_data()
- save()
- process_send() etc.
Any service can inherit from this class to implement functionality accordingly.
"""

# Standard Library
import json
from abc import ABCMeta
from datetime import datetime
from abc import abstractmethod

# Third Party
from celery import chord
from flask import current_app

# Application Specific
from ..models.user import Token
from ..models.misc import UrlConversion
from ..models.candidate import Candidate
from ..utils.common_functions import frequency_id_to_seconds
from ..routes import CandidateApiUrl, ActivityApiUrl, SchedulerApiUrl
from ..error_handling import ForbiddenError, InvalidUsage, ResourceNotFound
from ..utils.common_functions import http_request, find_missing_items, JSON_CONTENT_TYPE_HEADER


class CampaignBase(object):
    """
    - This is the base class for sending campaign to candidates and to keep track
        of their responses.

    This class contains following methods:

    * __init__():
        This method is called by creating the class object.
        - It takes "user_id" as keyword argument and sets it in self.user_id.

    * get_authorization_header(user_id): [static]
        This method is used to get authorization header for current user. This header is
        used to communicate with other flask micro services like candidate_service,
        activity_service etc.

    * save(self, form_data): [abstract]
        This method is used to save the campaign in db table according to campaign type.
        i.e. sms_campaign or push_notification_campaign etc. and returns the ID of
        new record in db.

    * campaign_create_activity(self, source): [abstract]
        This method is used to create an activity in database table "Activity" when user
        creates a campaign.
            e.g. in case of SMS campaign, activity will appear as
                'Nikola Tesla' created an SMS campaign "We are hiring".

    * schedule(self, data_to_schedule):
        This method is used to schedule given campaign using scheduler_service. Child classes
        will override this to set the value of "data_to_schedule" and update tables like
        email_campaign, sms_campaign etc, with "task_id" (Task created on APScheduler).

    * process_send(self, campaign): [abstract]
        This method is used send the campaign to candidates. Child classes will implement this.

    * get_smartlist_candidates(self, campaign_smartlist):
        This method gets the candidates associated with the given smartlist_id.
        It may search candidates in database/cloud. It is common for all the campaigns. It uses
        candidate_service/candidate_pool_service to do the job.

    * pre_process_celery_task(self, candidates):
        This method is used to do any necessary processing before assigning task to Celery
        worker if required. For example in case of SMS campaign, we filter valid candidates
        (those candidates who have one unique phone number associated).

    * send_sms_campaign_to_candidates(self, candidates):
        This loops over candidates and call send_sms_campaign_to_candidate() to send the
        campaign asynchronously.

    * send_sms_campaign_to_candidate(self, data_to_send_campaign): [abstract]
        This is a celery task. This does the sending part and update "sms_campaign_blast"
        ,"sms_campaign_send" etc.

    * celery_error_handler(uuid):
        This method is used to catch any error of Celery task and log it.

    * call_back_campaign_sent(send_result, user_id, campaign, auth_header):
        Once a campaign has been sent to a list of candidates, Celery hits this method as
        a callback and we create an "Activity" in database table as
            SMS campaign 'We are hiring' has been sent to 500 candidates.

    * create_or_update_url_conversion(destination_url=None, source_url='', hit_count=0,
                                    url_conversion_id=None, hit_count_update=None): [static]
        Here we save/update record of url_conversion in db table "url_conversion".
        This is common for all child classes.

    * create_activity(self, type_=None, source_table=None, source_id=None, params=None):
        This makes HTTP POST call to "activity_service" to create activity in database.
    """
    __metaclass__ = ABCMeta

    def __init__(self, user_id):
        self.user_id = user_id
        # This gets the access_token of current user to communicate with other services.
        self.oauth_header = self.get_authorization_header(self.user_id)
        self.campaign = None  # It will be instance of model e.g. SmsCampaign
        # or PushNotification etc.
        self.body_text = None  # This is 'text' to be sent to candidates as part of campaign.
        # Child classes will get this from respective campaign table.
        # e.g. in case of SMS campaign, this is get from "sms_campaign" database table.
        self.queue_name = None # name of Celery Queue. Each service will use its own queue
        # so that tasks related to one service only assign to that particular queue.

    @staticmethod
    def get_authorization_header(user_id):
        """
        This returns the authorization header containing access token token associated
        with current user. We use this access token to communicate with other services,
        like activity_service to create activity.

        :param user_id: id of user
        :exception: ForbiddenError
        :exception: ResourceNotFound
        :return: Authorization header
        :rtype: dict
        """
        user_token_obj = Token.get_by_user_id(user_id)
        if not user_token_obj:
            raise ResourceNotFound(error_message='No auth token record found for user(id:%s)'
                                                 % user_id)
        user_access_token = user_token_obj.access_token
        if not user_access_token:
            raise ForbiddenError(error_message='User(id:%s) has no auth token associated.'
                                               % user_id)
        return {'Authorization': 'Bearer %s' % user_access_token}

    @abstractmethod
    def save(self, form_data):
        """
        This saves the campaign in database table e.g. in sms_campaign or email_campaign etc.
        Child class will implement this.
        :return:
        """
        pass

    @abstractmethod
    def campaign_create_activity(self, source):
        """
        Child classes will use this to set type, source_id, source_table, params
        to create an activity in  database table "Activity" for newly created campaign.
        :return:
        """
        pass

    def schedule(self, data_to_schedule):
        """
        This actually POST on scheduler_service to schedule a given task.
        we set data_to_schedule dict in child class and call super constructor
        to make HTTP POST call to scheduler_service.

        e.g, in case of SMS campaign, we have
        data_to_schedule = {
                            'url_to_run_task': 'http://127.0.0.1:8012/v1/campaigns/1/send',
                            'task_type': 'one_time',
                            'data_to_post': None
                            }
        **See Also**
        .. see also:: schedule() method in SmsCampaignBase class.
        :param data_to_schedule: This contains the required data to schedule a particular job
        :type data_to_schedule: dict
        :return:
        """
        if not self.campaign:
            raise ForbiddenError(error_message='No campaign given to schedule.')

        if not data_to_schedule.get('url_to_run_task'):
            raise ForbiddenError(error_message='No URL given for the task.')

        # get number of seconds from frequency id
        frequency = frequency_id_to_seconds(data_to_schedule.get('frequency_id'))
        if not frequency:  # This means it is a one time job
            task = {
                "task_type": 'one_time',
                "run_datetime": data_to_schedule['send_datetime'],
            }
        else:
            task = {
                "task_type": 'periodic',
                "frequency": frequency,
                "start_datetime": data_to_schedule['send_datetime'],
                "end_datetime": data_to_schedule['stop_datetime'],
            }
        # set URL to be hit when time comes to run that task
        task['url'] = data_to_schedule['url_to_run_task']
        # set data to POST with above URL
        task['post_data'] = data_to_schedule.get('data_to_post', dict())
        # set content-type in header
        self.oauth_header.update({'Content-Type': 'application/json'})
        response = http_request('POST', SchedulerApiUrl.CREATE_TASK, data=json.dumps(task),
                                headers=self.oauth_header)
        # If any error occurs on POST call, we log the error inside http_request().
        if 'id' in response.json():
            return response.json()['id']
        else:
            raise InvalidUsage(error_message="Error occured while scheduling a task")

    @abstractmethod
    def process_send(self, campaign):
        """
        This will be used to do the processing to send campaign to candidates
        according to specific campaign. Child classes will implement this.
        :return:
        """
        pass

    def get_smartlist_candidates(self, campaign_smartlist):
        """
        This will get the candidates associated to a provided smart list. This makes
        HTTP GET call on candidate service API to get the candidate associated candidates.

        - This method is called from process_send() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :Example:
                SmsCampaignBase.get_candidates(1)

        :param campaign_smartlist: obj (e.g record of "sms_campaign_smartlist" database table)
        :type campaign_smartlist: object e,g obj of SmsCampaignSmartlist
        :return: Returns array of candidates in the campaign's smartlists.
        :rtype: list

        **See Also**
        .. see also:: process_send() method in SmsCampaignBase class.
        """
        params = {'id': campaign_smartlist.smartlist_id, 'return': 'all'}
        # HTTP GET call to candidate_service to get candidates associated with given smartlist id.
        response = http_request('GET', CandidateApiUrl.SMARTLIST_CANDIDATES,
                                headers=self.oauth_header, params=params, user_id=self.user_id)
        # get candidate ids
        try:
            candidate_ids = [candidate['id'] for candidate in
                             json.loads(response.text)['candidates']]
            candidates = [Candidate.get_by_id(_id) for _id in candidate_ids]
        except Exception:
            current_app.logger.exception('get_smartlist_candidates: Error while '
                                         'fetching candidates for smartlist(id:%s)'
                                         % campaign_smartlist.smartlist_id)
            raise
        if not candidates:
            current_app.logger.error('get_smartlist_candidates: '
                                     'No Candidate found. smartlist id is %s. '
                                     '(User(id:%s))' % (campaign_smartlist.smartlist_id,
                                                        self.user_id))
        return candidates

    def send_campaign_to_candidates(self, candidates, logger):
        """
        Once we have the candidates, we iterate each candidate, create celery task and call
        self.send_campaign_to_candidate() to send the campaign. Celery sends campaign to all
        candidates asynchronously and if all tasks finish correctly, it hits a callback function
        (self.callback_campaign_sent() in our case) to notify us that campaign has been sent
        to all candidates.

        e.g. This method is called from process_send() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :param candidates: This contains the objects of model Candidate
        :type candidates: list

        **See Also**
        .. see also:: process_send() method in SmsCampaignBase class.
        """
        try:
            pre_processed_data = self.pre_process_celery_task(candidates)
            # callback is a function which will be hit after campaign is sent to all candidates i.e.
            # once the async task is done the self.callback_campaign_sent will be called
            # When all tasks assigned to Celery complete their execution, following function
            # is called by celery as a callback function.
            # Each service will use its own queue so that tasks related to one service only
            # assign to that particular queue.
            callback = self.callback_campaign_sent.subtask((self.user_id, self.campaign,
                                                            self.oauth_header,),
                                                           queue=self.queue_name)
            # Here we create list of all tasks and assign a self.celery_error_handler() as a
            # callback function in case any of the tasks in the list encounter some error.
            tasks = [self.send_campaign_to_candidate.subtask(
                (self, record), link_error=self.celery_error_handler.subtask(queue=self.queue_name)
                , queue=self.queue_name) for record in pre_processed_data]
            # This runs all tasks asynchronously and sets callback function to be hit once all
            # tasks in list finish running without raising any error. Otherwise callback
            # results in failure status.
            chord(tasks)(callback)
        except Exception:
            logger.exception('send_campaign_to_candidates: Error while sending tasks to Celery')

    def pre_process_celery_task(self, candidates):
        """
        Here we do any necessary processing before assigning task to Celery. Child classes
        will override this if needed.
        :param candidates:
        :return:
        """
        return candidates

    @abstractmethod
    def send_campaign_to_candidate(self, data_to_send_campaign):
        """
        This sends the campaign to given candidate. Child classes will implement this.
        :param data_to_send_campaign: This is the data used by celery task to send campaign
        :type data_to_send_campaign: tuple
        :return:
        """
        pass

    @staticmethod
    @abstractmethod
    def celery_error_handler(uuid):
        """
        This function logs any error occurred for tasks running on celery,
        :return:
        """
        pass

    @staticmethod
    @abstractmethod
    def callback_campaign_sent(sends_result, user_id, campaign, auth_header):
        """
        This is the callback function for campaign sent.
        Child classes will implement this.
        :param sends_result: Result of executed task
        :param user_id: id of user (owner of campaign)
        :param campaign: id of campaign which was sent to candidates
        :param auth_header: auth header of current user to make HTTP request to other services
        :type sends_result: list
        :type user_id: int
        :type campaign: object (e.g SmsCampaign)
        :type auth_header: dict
        :return:
        """
        pass

    @staticmethod
    def create_or_update_url_conversion(destination_url=None, source_url=None, hit_count=0,
                                        url_conversion_id=None, hit_count_update=None):
        """
        - Here we save the source_url(provided in body text) and the shortened_url
            to redirect to our endpoint in db table "url_conversion".

        - This method is called from process_urls_in_sms_body_text() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :param destination_url: link present in body text
        :param source_url: shortened URL of the link present in body text
        :param hit_count: Count of hits
        :param url_conversion_id: id of URL conversion record if needs to update
        :param hit_count_update: True if needs to increase "hit_count" by 1, False otherwise
        :type destination_url: str
        :type source_url: str
        :type hit_count: int
        :type url_conversion_id: int
        :type hit_count_update: bool
        :exception: ResourceNotFound
        :exception: ForbiddenError
        :return: id of the url_conversion record in database
        :rtype: int

        **See Also**
        .. see also:: process_urls_in_sms_body_text() method in SmsCampaignBase class.
        """
        data = {'destination_url': destination_url,
                'source_url': source_url,
                'hit_count': hit_count}
        if url_conversion_id:  # record is already present in database
            record_in_db = UrlConversion.get_by_id(url_conversion_id)
            if record_in_db:
                data['destination_url'] = record_in_db.destination_url
                data['source_url'] = source_url if source_url else record_in_db.source_url
                data['hit_count'] = record_in_db.hit_count + 1 if hit_count_update else \
                    record_in_db.hit_count
                data.update({'last_hit_time': datetime.now()}) if hit_count_update else ''
                record_in_db.update(**data)
                url_conversion_id = record_in_db.id
            else:
                raise ResourceNotFound(
                    error_message='create_or_update_url_conversion: '
                                  'url_conversion(id:%s) not found' % url_conversion_id)
        else:
            missing_required_fields = find_missing_items(data, verify_values_of_all_keys=True)
            if len(missing_required_fields) == len(data.keys()):
                raise ForbiddenError(error_message='destination_url/source_url cannot be None.')
            else:
                new_record = UrlConversion(**data)
                UrlConversion.save(new_record)
                url_conversion_id = new_record.id
        return url_conversion_id

    @staticmethod
    def create_activity(user_id, _type=None, source_table=None, source_id=None,
                        params=None, headers=None):
        """
        - Once we have all the parameters to save the activity in database table "Activity",
            we call "activity_service"'s endpoint /activities/ with HTTP POST call
            to save the activity in db.

        - This method is called from create_sms_send_activity() and
            create_campaign_send_activity() methods of class SmsCampaignBase inside
            sms_campaign_service/sms_campaign_base.py.

        :param user_id: id of user
        :param _type: type of activity (using underscore with type as "type" reflects built in name)
        :param source_table: source table name of activity
        :param source_id: source id of activity
        :param params: params to store for activity
        :type user_id: int
        :type _type: int
        :type source_table: str
        :type source_id: int
        :type params: dict
        :exception: ForbiddenError

        **See Also**
            .. see also:: create_sms_send_activity() method in SmsCampaignBase class.
        """
        if not isinstance(params, dict):
            raise InvalidUsage(error_message='params should be dictionary.')
        try:
            json_data = json.dumps({'source_table': source_table,
                                    'source_id': source_id,
                                    'type': _type,
                                    'params': params})
        except Exception as error:
            raise ForbiddenError(error_message='Error while serializing activity params '
                                               'into JSON. Error is: %s' % error.message)
        headers.update(JSON_CONTENT_TYPE_HEADER)  # Add content-type in header
        # POST call to activity_service to create activity
        http_request('POST', ActivityApiUrl.CREATE_ACTIVITY, headers=headers,
                     data=json_data, user_id=user_id)
