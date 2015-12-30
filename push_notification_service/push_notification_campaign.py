from werkzeug.exceptions import BadRequest

from push_notification_service.common.error_handling import *
from push_notification_service.common.models.push_notification import *
from push_notification_service.common.utils.activity_utils import ActivityMessageIds
from push_notification_service.common.campaign_services.campaign_utils import CampaignBase
from push_notification_service.common.routes import PushNotificationServiceApi
from push_notification_service import logger
from push_notification_service.custom_exceptions import *
from push_notification_service.constants import ONE_SIGNAL_APP_ID, ONE_SIGNAL_REST_API_KEY
from push_notification_service.one_signal_sdk import OneSignalSdk

one_signal_client = OneSignalSdk(app_id=ONE_SIGNAL_APP_ID,
                                 rest_key=ONE_SIGNAL_REST_API_KEY)


class PushCampaignBase(CampaignBase):

    def __init__(self, user_id, *args, **kwargs):
        """
        Here we set the "user_id" by calling super constructor.
        :param args:
        :param kwargs:
        :return:
        """
        # sets the user_id
        super(PushCampaignBase, self).__init__(user_id, *args, **kwargs)
        self.push_notification = None
        self.subscribed_candidate_ids = []
        self.unsubscribed_candidate_ids = []
        self.campaign_blast = None

    def get_all_campaigns(self):
        """
        This gets all the campaigns created by current user
        :return: all campaigns associated to with user
        :rtype: list
        """
        return PushCampaign.get_by_user_id(self.user_id)

    def save(self, form_data):
        """
        This saves the campaign in database table push_notification in following steps:

            1- Save push notification in database
            2 Create activity that
                "%(user_name)s created an Push Notification campaign: '%(campaign_name)s'"

        :param form_data: data from UI
        :type form_data: dict
        :return: id of sms_campaign in db
        :rtype: int
        """
        pass

    @classmethod
    def pre_process_schedule(cls, request, campaign_id):
        """
        This implements the base class method. Before making HTTP POST/GET call on
        scheduler_service, we do the following.
        1- Check if request has valid JSON content-type header
        2- Check if current user is an owner of given campaign_id
        :return: dictionary containing Campaign obj, data to schedule SMS campaign,
                    scheduled_task and bearer access token
        :rtype: dict
        """
        campaign_obj = cls.validate_ownership_of_campaign(campaign_id, request.user.id)
        # check if campaign is already scheduled
        scheduled_task = cls.is_already_scheduled(campaign_obj.scheduler_task_id,
                                                  request.oauth_token)
        # Updating scheduled task should not be allowed in POST request
        if scheduled_task and request.method == 'POST':
            raise ForbiddenError(error_message='Use PUT method to update task')
        try:
            data_to_schedule_campaign = request.get_json()
        except BadRequest:
            raise InvalidUsage(error_message='Given data should be in dict format')
        if not data_to_schedule_campaign:
            raise InvalidUsage(
                error_message='No data provided to schedule %s (id:%s)'
                              % (campaign_obj.__tablename__, campaign_id))
        return {'campaign': campaign_obj,
                'data_to_schedule': data_to_schedule_campaign,
                'scheduled_task': scheduled_task,
                'auth_header': {'Authorization': request.oauth_token}}

    @staticmethod
    def validate_ownership_of_campaign(campaign_id, current_user_id):
        """
        This function returns True if the current user is an owner for given
        campaign_id. Otherwise it raises the Forbidden error.
        :param campaign_id: id of campaign form getTalent database
        :param current_user_id: Id of current user
        :exception: InvalidUsage
        :exception: ResourceNotFound
        :exception: ForbiddenError
        :return: Campaign obj if current user is an owner for given campaign.
        :rtype: PushNotification
        """
        if not isinstance(campaign_id, (int, long)):
            raise InvalidUsage(error_message='Include campaign_id as int|long')
        campaign_obj = PushCampaign.get_by_id(campaign_id)
        if not campaign_obj:
            raise ResourceNotFound(error_message='Push Campaign (id=%s) not found.' % campaign_id)
        if campaign_obj.user_id == current_user_id:
            return campaign_obj
        else:
            raise ForbiddenError(error_message='You are not the owner of Push campaign(id:%s)' % campaign_id)

    def schedule(self, data_to_schedule):
        """
        This method schedules a campaign by sending a POST request to scheduler service.
        :param data_to_schedule:
        :return:
        """
        data_to_schedule.update(
            {'url_to_run_task': PushNotificationServiceApi.SEND % self.campaign.id}
        )
        # get scheduler task_id
        task_id = super(PushCampaignBase, self).schedule(data_to_schedule)
        data_to_schedule.update({'task_id': task_id})
        # update push_notification_campaign record with task_id
        self.campaign.update(task_id=task_id)
        return task_id

    def process_send(self, campaign_id):
        self.push_notification = PushCampaign.get_by_id(campaign_id)
        if self.push_notification:
            self.campaign_blast = PushCampaignBlast(campaign_id=campaign_id)
            PushCampaignBlast.save(self.campaign_blast)
            candidates = []
            smartlists = self.push_notification.smartlists
            if not smartlists:
                raise NoSmartlistAssociated('No smartlist is associated with Push Campaign (id:%s). '
                                            '(User(id:%s))' % (self.push_notification.id, self.user_id))
            for smartlist in smartlists:
                candidates += self.get_smartlist_candidates(smartlist)
            for candidate in candidates:
                self.send_campaign_to_candidate(candidate)
            return self.subscribed_candidate_ids, self.unsubscribed_candidate_ids
        else:
            raise ResourceNotFound('Push Campaign was not found with id : %s' % campaign_id)

    @staticmethod
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
        :type campaign: row
        :type auth_header: dict
        :return:
        """
        pass

    @staticmethod
    # @celery_app.task(name='callback_campaign_sent')
    def callback_campaign_sent(sends_result, user_id, campaign, auth_header):
        """
        Once a Push Notification campaign has been sent to all candidates, this function is hit, and here we

        add activity e.g. (Push Notification Campaign "abc" was sent to "200" candidates")

        :param sends_result: Result of executed task
        :param user_id: id of user (owner of campaign)
        :param campaign: id of campaign which was sent to candidates
        :param auth_header: auth header of current user to make HTTP request to other services
        :type sends_result: list
        :type user_id: int
        :type campaign: row
        :type auth_header: dict

        **See Also**
        .. see also:: send_campaign_to_candidates() method in CampaignBase class inside
                        common/utils/campaign_utils.py
        """
        if isinstance(sends_result, list):
            total_sends = sends_result.count(True)
            PushCampaignBase.create_campaign_send_activity(user_id,
                                                          campaign, auth_header, total_sends) \
                if total_sends else ''
            logger.debug('process_send: Push Notification Campaign(id:%s) has been sent to %s candidate(s).'
                         '(User(id:%s))' % (campaign.id, total_sends, user_id))
        else:
            logger.error('callback_campaign_sent: Result is not a list')

    @classmethod
    def create_campaign_send_activity(cls, user_id, source, auth_header, num_candidates):
        """
        - Here we set "params" and "type" of activity to be stored in db table "Activity"
            for Campaign sent.

        - Activity will appear as "Push Notification %(campaign_name)s has been sent to %(num_candidates)s candidates".

        - This method is called from send_sms_campaign_to_candidates() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :param user_id: id of user
        :param source: Source row
        :param auth_header: Authorization header
        :param num_candidates: number of candidates to which campaign is sent
        :type user_id: int
        :type source: row
        :type auth_header: dict
        :type num_candidates: int

        **See Also**
        .. see also:: send_push_notification_campaign_to_candidates() method in PushNotificationCampaign class.
        """
        if not isinstance(source, PushCampaign):
            raise InvalidUsage(error_message='source should be an instance of model PushNotification')
        params = {'campaign_name': source.title,
                  'num_candidates': num_candidates}
        cls.create_activity(user_id,
                            type_=ActivityMessageIds.CAMPAIGN_PUSH_NOTIFICATION_CREATE,
                            source_id=source.id,
                            source_table=PushCampaign.__tablename__,
                            params=params,
                            headers=auth_header)

    @staticmethod
    def celery_error(error):
        """
        This function logs any error occurred for tasks running on celery,
        :return:
        """
        pass

    def campaign_create_activity(self, source):
        pass

    def send_campaign_to_candidate(self, candidate):
        device_ids = map(lambda device: device.one_signal_device_id, candidate.devices)
        if device_ids:
            try:
                resp = one_signal_client.send_notification(self.push_notification.url,
                                                           self.push_notification.content,
                                                           self.push_notification.title,
                                                           players=device_ids)
                if resp.ok:
                    campaign_send = PushCampaignSend(campaign_blast_id=self.campaign_blast.id,
                                                     candidate_id=candidate.id
                                                     )
                    PushCampaignSend.save(campaign_send)
                    sends = self.campaign_blast.sends + 1
                    self.campaign_blast.update(sends=sends)
                    self.subscribed_candidate_ids.append(candidate.id)
                else:
                    self.unsubscribed_candidate_ids.append(candidate.id)
                    response = resp.json()
                    errors = response['errors']
                    logger.error('Error while sending push notification to candidate (id: %s),'
                                 'Errors: %s' % errors)

            except Exception as e:
                logger.error('Unable to send push  notification (id: %s) to candidate (id: %s)'
                             % (self.push_notification.id, candidate.id))
                self.unsubscribed_candidate_ids.append(candidate.id)
        else:
            logger.error('Candidate has not subscribed for push notification')
            self.unsubscribed_candidate_ids.append(candidate.id)

