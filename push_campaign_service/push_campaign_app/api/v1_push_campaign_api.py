"""
This module contains RESTful API endpoints for Push Campaign Service.

A brief overview of all endpoints is as follows:

    1. Create a push campaign
        URL: /v1/push-campaigns [POST]

        Sends a POST request to this endpoint with required data to create a push campaign.
        It actually creates a draft for campaign. To send a campaign, you need to schedule it.

    2. Get campaigns of a user
        URL: /v1/push-campaigns [GET]

        To get all push campaigns of a user, send a GET request to this endpoint

    3. Delete multiple push campaigns of a user
        URL: /v1/push-campaigns [DELETE]

        API user can send a DELETE request to this endpoint with campaign ids as list
        { ids: [1,2,3]}  to delete multiple campaigns.

    4. Get a single campaign of a user
        URL: /v1/push-campaigns/:id [GET]

        To get a specific campaign of a user, send a GET request to this endpoint

    5. Update a specific campaign of a user
        URL: /v1/push-campaigns/:id [PUT]

        To update a specific campaign of a user, send a PUT request to this endpoint

    6. Delete a specific campaign of a user
        URL: /v1/push-campaigns/:id [DELETE]

        To delete a specific campaign of a user, send a DELETE request to this endpoint

    7. Schedule a campaign
        URL: /v1/push-campaigns/:id/schedule [POST]

        User can schedule a campaign by sending a POST request to this endpoint with frequency,
        start_datetime and end_datetime.

    8. Reschedule a campaign
        URL: /v1/push-campaigns/:id/schedule [PUT]

        User can reschedule his campaign by updating the frequency, start_datetime or end_datetime
        by sending a PUT request to this point.

    9. Unschedule a campaign
        URL: /v1/push-campaigns/:id/schedule [DELETE]

        User can unschedule his campaign by by sending a DELETE request to this point.

    10. Send a campaign
        URL: /v1/push-campaigns/:id/send [POST]

        This endpoint is used to send a campaign (that has already been created) to associated
        candidates by send a POST request to this endpoint.

    12. Get `Sends` of a Blast
        URL: /v1/push-campaigns/:id/blasts/:blast_id/sends [GET]

        A campaign can have multiple blast. To get sends of a single blast for a specific campaign
        send a GET request to this endpoint.

    13. Get `Sends` of a campaign
        URL: /v1/push-campaigns/<int:campaign_id>/sends [GET]

        To get all sends of a campaign, use this endpoint

    14. Get `Blasts` of a campaign
        URL: /v1/push-campaigns/:id/blasts [GET]

        To get a list of all blasts associated to a campaign, send a GET request
        to this endpoint. A blast contains statistics of a campaign when a campaign
        is sent once to associated candidates.

    15. Get a specific `Blast` of a campaign
        URL: /v1/push-campaigns/:id/blasts/:blast_id [GET]

        To get details of a specific blast associated to a campaign, send a GET request
        to this endpoint. A blast contains statistics of a campaign when a campaign
        is sent once to associated candidates.
"""
# TODO --basit: Endpoints regarding URL redirection and url_conversion are missing here

# Standard Library
import json
import types

# Third Party
from flask import request
from flask import redirect
from flask import Blueprint
from flask.ext.restful import Resource

# Application Specific
from push_campaign_service.common.campaign_services.campaign_base import CampaignBase
from push_campaign_service.common.campaign_services.campaign_utils import CampaignUtils
from push_campaign_service.common.campaign_services.custom_errors import CampaignException
from push_campaign_service.common.campaign_services.validators import get_valid_json_data
from push_campaign_service.common.error_handling import (InternalServerError, ResourceNotFound,
                                                         ForbiddenError, InvalidUsage)
from push_campaign_service.common.models.misc import UrlConversion
from push_campaign_service.common.talent_api import TalentApi
from push_campaign_service.common.routes import PushCampaignApi
from push_campaign_service.common.utils.auth_utils import require_oauth
from push_campaign_service.common.utils.api_utils import api_route, ApiResponse
from push_campaign_service.common.models.push_campaign import (PushCampaign,
                                                               PushCampaignBlast,
                                                               PushCampaignSendUrlConversion)
from push_campaign_service.modules.push_campaign_base import PushCampaignBase
from push_campaign_service.modules.utilities import associate_smart_list_with_campaign
from push_campaign_service.modules.constants import CAMPAIGN_REQUIRED_FIELDS
from push_campaign_service.push_campaign_app import logger

# TODO --basit: imports can be improved in terms of line length
# creating blueprint
push_notification_blueprint = Blueprint('push_notification_api', __name__)
api = TalentApi()
api.init_app(push_notification_blueprint)
api.route = types.MethodType(api_route, api)


@api.route(PushCampaignApi.CAMPAIGNS)
class PushCampaignsResource(Resource):
    """
    Resource to get, create and delete campaigns
    """
    decorators = [require_oauth()]
    # TODO --basit: import PushCampaignApiUrl in this file for the example of code in docString
    # TODO: json -> JSON in all comments

    def get(self):
        """
        This action returns a list of all push campaigns for current user.

        :return campaigns_data: a dictionary containing list of campaigns and their count
        :rtype json

        :Example:

            >>> import requests
            >>> headers = {'Authorization': 'Bearer <access_token>'}
            >>> response = requests.get(PushCampaignApiUrl.CAMPAIGNS, headers=headers)

        .. Response::

            {
                "count": 2,
                "campaigns": [
                            {
                              "added_datetime": "2015-11-19 18:54:04",
                              "frequency_id": 2,
                              "id": 3,
                              "name": "QC Technologies",
                              "start_datetime": "2015-11-19 18:55:08",
                              "end_datetime": "2015-11-25 18:55:08"
                              "body_text": "Join QC Technologies.",
                              "url": "https://www.qc-technologies.com/careers"
                            },
                            {
                              "added_datetime": "2015-11-19 18:55:08",
                              "frequency_id": 1,
                              "id": 4,
                              "name": "getTalent",
                              "start_datetime": "2015-12-12 10:55:08",
                              "end_datetime": "2015-12-31 18:55:08"
                              "body_text": "Job opening at QC Technologies",
                              "url": "https://www.qc-technologies.com/careers"
                            }
              ]
            }

        .. Status:: 200 (OK)
                    401 (Unauthorized to access getTalent)
                    500 (Internal Server Error)
        """
        user = request.user
        # TODO --basit: we can remove this variable `user`, Just pass request.user.id in below code
        campaigns = PushCampaign.get_by_user_id(user.id)
        campaigns = [campaign.to_json() for campaign in campaigns]
        return dict(campaigns=campaigns, count=len(campaigns)), 200

    def post(self):
        """
        This method takes data to create a Push campaign in database. This campaign is just a
        draft and we need to schedule or send it later.
        :return: id of created campaign and a success message
        :type: json

        :Example:

            >>> import json
            >>> import requests
            >>> campaign_data = {
            >>>                    "name": "QC Technologies",
            >>>                    "body_text": "New job openings...",
            >>>                    "url": "https://www.qc-technologies.com",
            >>>                    "smartlist_ids": [1, 2, 3]
            >>>                 }
            >>> headers = {
            >>>               "Authorization": "Bearer <access_token>",
            >>>                "content-type": "application/json"
            >>>           }
            >>> data = json.dumps(campaign_data)
            >>> response = requests.post(
            >>>                             PushCampaignApiUrl.CAMPAIGNS,
            >>>                             data=data,
            >>>                             headers=headers,
            >>>                         )

        .. Response::

            {
                "id": 11,
                "message": "Push campaign was created successfully"
            }

        .. Status:: 201 (Resource Created)
                    401 (Unauthorized to access getTalent)
                    403 (Forbidden error)
                    500 (Internal Server Error)

        ..Error Codes:: 7003 (RequiredFieldsMissing)
        """
        user = request.user
        data = get_valid_json_data(request)
        missing_fields = [key for key in ['name',
                                          'body_text',
                                          'url',
                                          'smartlist_ids'] if key not in data or not data[key]]
        if missing_fields:
            raise InvalidUsage('Some required fields are missing',
                               additional_error_info=dict(missing_fields=missing_fields),
                               error_code=CampaignException.MISSING_REQUIRED_FIELD)
        campaign = PushCampaignBase(user_id=user.id)
        campaign_id, _ = campaign.save(data)
        response = dict(id=campaign_id, message='Push campaign was created successfully')
        response = json.dumps(response)
        # TODO --basit: remove hard coding location instead use ApiUrl as we discussed earlier
        headers = dict(Location='/%s/push-campaigns/%s' % (PushCampaignApi.VERSION, campaign_id))
        return ApiResponse(response, headers=headers, status=201)

    def delete(self):
        """
        Deletes multiple campaigns using ids given in list in request data.
        :return:

        :Example:

            >>> import json
            >>> import requests
            >>> headers = {'Authorization': 'Bearer <access_token>',
            >>>             'content-type': 'application/json'
            >>>           }
            >>> campaign_ids = {'ids': [1, 2, 3]}
            >>> data = json.dumps(campaign_ids)
            >>> response = requests.delete(PushCampaignApiUrl.CAMPAIGNS, headers=headers, data=data)

        .. Response::

            {
                'message': '3 Campaigns have been deleted successfully'
            }

        .. Status:: 200 (Resource deleted)
                    207 (Not all deleted)
                    400 (Bad request)
                    403 (Forbidden error)
                    500 (Internal Server Error)
        """
        req_data = get_valid_json_data(request)
        campaign_ids = req_data['ids'] if 'ids' in req_data else []
        if not isinstance(req_data['ids'], list):
            raise InvalidUsage('Bad request, include campaign_ids as list data',
                               error_code=InvalidUsage.http_status_code())
        # check if campaigns_ids list is not empty
        if not campaign_ids:
            return dict(message='No campaign id provided to delete'), 200

        if not all([isinstance(campaign_id, (int, long)) for campaign_id in campaign_ids]):
            raise InvalidUsage('Bad request, campaign_ids must be integer',
                               error_code=InvalidUsage.http_status_code())
        not_deleted = []
        not_found = []
        # TODO --basit: Following should be not_owned
        not_owner = []
        status_code = None
        for campaign_id in campaign_ids:
            campaign_obj = PushCampaignBase(request.user.id)
            try:
                deleted = campaign_obj.delete(campaign_id)
                if not deleted:
                    # error has been logged inside delete()
                    not_deleted.append(campaign_id)
            except ForbiddenError:
                status_code = ForbiddenError.http_status_code()
                not_owner.append(campaign_id)
            except ResourceNotFound:
                status_code = ResourceNotFound.http_status_code()
                not_found.append(campaign_id)
            except InvalidUsage:
                status_code = InvalidUsage.http_status_code()
                not_deleted.append(campaign_id)
        if status_code and len(campaign_ids) == 1:  # It means only one campaign_id was provided
            return dict(message='Unable to delete campaign.'), status_code
        if not_deleted or not_owner or not_found:
            return dict(message='Unable to delete %d campaign(s).'
                                % (len(not_deleted) + len(not_found) + len(not_owner)),
                        not_deleted_ids=not_deleted, not_found_ids=not_found,
                        not_owned_ids=not_owner), 207
        else:
            return dict(message='%d campaign(s) deleted successfully.' % len(campaign_ids)), 200


@api.route(PushCampaignApi.CAMPAIGN)
class CampaignByIdResource(Resource):
    """
    Resource to update, get and delete a specific campaign.
    """
    decorators = [require_oauth()]

    def get(self, campaign_id):
        """
        This action returns a single campaign created by current user.
        :param campaign_id: push campaign id
        :type campaign_id: int | long
        :return campaign_data: a dictionary containing campaign json serializable data
        :rtype json

        :Example:

            >>> import requests
            >>> headers = {'Authorization': 'Bearer <access_token>'}
            >>> campaign_id = 1
            >>> response = requests.get(PushCampaignApiUrl.CAMPAIGN % campaign_id,
            >>>                        headers=headers)

        .. Response::

            {
                "campaign":{
                              "added_datetime": "2015-11-19 18:54:04",
                              "frequency_id": 2,
                              "id": 1,
                              "name": "QC Technologies",
                              "start_datetime": "2015-11-19 18:55:08",
                              "end_datetime": "2015-11-25 18:55:08"
                              "body_text": "Join QC Technologies.",
                              "url": "https://www.qc-technologies.com/careers"
                            }
            }
        .. Status:: 200 (OK)
                    401 (Unauthorized to access getTalent)
                    404 (ResourceNotFound)
                    500 (Internal Server Error)
        """
        # TODO --basit: There will also be 403 status code in above
        user = request.user
        campaign = PushCampaignBase.get_campaign_if_domain_is_valid(campaign_id, user,
                                                                    CampaignUtils.PUSH)
        response = dict(campaign=campaign.to_json())
        return response, 200

    def put(self, campaign_id):
        """
        This method takes data to update a Push campaign components.

        :param campaign_id: unique id of push campaign
        :type campaign_id: int, long
        :return: success message
        :type: json

        :Example:

            >>> import json
            >>> import requests
            >>> campaign_data = {
            >>>                     "name": "QC Technologies",
            >>>                     "body_text": "New job openings...",
            >>>                     "url": "https://www.qc-technologies.com",
            >>>                     "smartlist_ids": [1, 2, 3]
            >>>                  }
            >>> headers = {
            >>>             "Authorization": "Bearer <access_token>",
            >>>             "content-type": "application/json"
            >>>            }
            >>> campaign_id = 1
            >>> data = json.dumps(campaign_data)
            >>> response = requests.put(
            >>>                             PushCampaignApiUrl.CAMPAIGN % campaign_id ,
            >>>                             data=data,
            >>>                             headers=headers,
            >>>                         )

        .. Response::

            {
                "message": "Push campaign has been updated successfully"
            }

        .. Status:: 201 (Resource Created)
                    401 (Unauthorized to access getTalent)
                    400 (Invalid Usage)
                    500 (Internal Server Error)

        ..Error Codes:: 7003 (RequiredFieldsMissing)
        """
        # TODO --basit: There will also be 403 status code in above. Kindly double check every where else
        user = request.user
        data = get_valid_json_data(request)
        if not campaign_id > 0:
            # TODO --basit: I think Following error message is not correct, because there
            # TODO is no database interaction yet
            raise ResourceNotFound('Campaign not found with id %s' % campaign_id)
        campaign = PushCampaignBase.get_campaign_if_domain_is_valid(campaign_id, user,
                                                                    CampaignUtils.PUSH)
        for key, value in data.items():
            if key not in CAMPAIGN_REQUIRED_FIELDS:
                raise InvalidUsage('Invalid field in campaign data',
                                   additional_error_info=dict(invalid_field=key))
            if not value:
                raise InvalidUsage('Invalid value for field in campaign data',
                                   additional_error_info=dict(field=key,
                                                              invalid_value=value),
                                   error_code=CampaignException.MISSING_REQUIRED_FIELD)

        data['user_id'] = user.id
        # We are confirmed that this key has some value after above validation
        smartlist_ids = data.pop('smartlist_ids')
        campaign.update(**data)
        associated_smartlist_ids = [smartlist.id for smartlist in campaign.smartlists]
        if isinstance(smartlist_ids, list):
            for smartlist_id in smartlist_ids:
                if smartlist_id not in associated_smartlist_ids:
                    associate_smart_list_with_campaign(smartlist_id, campaign.id)
                else:
                    logger.info('Smartlist (id: %s) already associated with campaign'
                                % smartlist_id)
        elif isinstance(smartlist_ids, (int, long)):
            associate_smart_list_with_campaign(smartlist_ids, campaign.id)

        response = dict(message='Push campaign was updated successfully')
        return response, 200

    def delete(self, campaign_id):
        """
        Removes a single campaign from getTalent's database.
        :param campaign_id: (Integer) unique id in push_campaign table on GT database.

        :Example:

            >>> import requests
            >>> headers = {'Authorization': 'Bearer <access_token>'}
            >>> campaign_id = 1
            >>> response = requests.delete(PushCampaignApiUrl.CAMPAIGN % campaign_id,
            >>>                            headers=headers)

        .. Response::

            {
                'message': 'Campaign(id:125) has been deleted successfully'
            }
        .. Status:: 200 (Resource Deleted)
                    400 (Bad request)
                    403 (Forbidden: Current user cannot delete Push campaign)
                    404 (Campaign not found)
                    500 (Internal Server Error)

        ..Error codes::
                    5010 (ERROR_DELETING_CAMPAIGN)
        """
        campaign_obj = PushCampaignBase(request.user.id)
        campaign_deleted = campaign_obj.delete(campaign_id)
        if campaign_deleted:
            return dict(message='Campaign(id:%s) has been deleted successfully.' % campaign_id), 200
        else:
            raise InternalServerError(
                'Campaign(id:%s) was not deleted.' % campaign_id,
                error_code=CampaignException.ERROR_DELETING_CAMPAIGN)


@api.route(PushCampaignApi.SCHEDULE)
class SchedulePushCampaignResource(Resource):
    """
    This resource is used to schedule, reschedule and unschedule a specific campaign.
    """
    decorators = [require_oauth()]

    def post(self, campaign_id):
        """
        It schedules an Push Notification campaign using given campaign_id by making HTTP request to
         scheduler_service.

        :Example:

            >>> import json
            >>> import requests
            >>> headers = {'Authorization': 'Bearer <access_token>',
            >>>            'Content-type': 'application/json'}
            >>> schedule_data =
            >>>             {
            >>>                 "frequency_id": 2,
            >>>                 "start_datetime": "2015-11-26T08:00:00Z",
            >>>                 "end_datetime": "2015-11-30T08:00:00Z"
            >>>             }
            >>> campaign_id = str(1)
            >>> schedule_data = json.dumps(schedule_data)
            >>> response = requests.post(PushCampaignApiUrl.SCHEDULE % campaign_id,
            >>>                             headers=headers, data=schedule_data)

        .. Response::

                {
                    "message": "Campaign(id:1) is has been scheduled.
                    "task_id"; "33e32e8ac45e4e2aa710b2a04ed96371"
                }

        .. Status:: 200 (OK)
                    400 (Bad request)
                    401 (Unauthorized to access getTalent)
                    403 (Forbidden Error)
                    404 (Campaign not found)
                    500 (Internal Server Error)

        .. Error codes:
                    7006 (CampaignAlreadyScheduled)

        :param campaign_id: integer, unique id representing campaign in GT database
        :return: JSON containing message and task_id.
        """
        user = request.user
        get_valid_json_data(request)
        if not campaign_id:
            raise InvalidUsage('campaign_id should be a positive number')
        pre_processed_data = PushCampaignBase.data_validation_for_campaign_schedule(
            request, campaign_id, CampaignUtils.PUSH)
        campaign_obj = PushCampaignBase(user.id)
        campaign_obj.campaign = pre_processed_data['campaign']
        task_id = campaign_obj.schedule(pre_processed_data['data_to_schedule'])
        message = 'Campaign(id:%s) has been re-scheduled.' % campaign_id
        return dict(message=message, task_id=task_id), 200

    def put(self, campaign_id):
        """
        This endpoint is to reschedule a campaign. It first deletes the old schedule of
        campaign from scheduler_service and then creates new task.

        :Example:

            >>> import json
            >>> import requests
            >>> headers = {'Authorization': 'Bearer <access_token>',
            >>>            'Content-type': 'application/json'}
            >>> schedule_data =
            >>>             {
            >>>                 "frequency_id": 2,
            >>>                 "start_datetime": "2015-11-26T08:00:00Z",
            >>>                 "end_datetime": "2015-11-30T08:00:00Z"
            >>>             }
            >>> campaign_id = 1
            >>> data = json.dumps(schedule_data)
            >>> response = requests.put(PushCampaignApiUrl.CAMPAIGN % campaign_id,
            >>>                             headers=headers, data=data)

        .. Response::

                {
                    "message": "Campaign(id:1) is has been re-scheduled.
                    "task_id"; "33e32e8ac45e4e2aa710b2a04ed96371"
                }

        .. Status:: 200 (OK)
                    400 (Bad request)
                    401 (Unauthorized to access getTalent)
                    403 (Forbidden Error)
                    404 (Campaign not found)
                    500 (Internal Server Error)

        :param campaign_id: integer, unique id representing campaign in GT database
        :return: JSON containing message and task_id.
        """
        get_valid_json_data(request)
        if not campaign_id:
            raise InvalidUsage('campaign_id should be a positive number')
        # create object of class PushCampaignBase
        push_camp_obj = PushCampaignBase(request.user.id)
        task_id = push_camp_obj.reschedule(request, campaign_id)
        if task_id:
            message = 'Campaign(id:%s) has been re-scheduled.' % campaign_id
        else:
            message = 'Campaign(id:%s) is already scheduled with given data.' % campaign_id
            task_id = push_camp_obj.campaign.scheduler_task_id
        return dict(message=message, task_id=task_id), 200

    def delete(self, campaign_id):
        """
        Unschedule a single campaign from scheduler_service and removes the scheduler_task_id
        from getTalent's database.

        :param campaign_id: (Integer) unique id in push_campaign table on GT database.

        :Example:

            >>> import requests
            >>> headers = {
            >>>             'Authorization': 'Bearer <access_token>',
            >>>            }
            >>> campaign_id = 1
            >>> response = requests.delete(PushCampaignApiUrl.CAMPAIGN % campaign_id,
            >>>                             headers=headers,
            >>>                         )

        .. Response::

            {
                'message': 'Campaign(id:125) has been unscheduled.'
            }

        .. Status:: 200 (Resource Deleted)
                    403 (Forbidden: Current user cannot delete Push campaign)
                    404 (Campaign not found)
                    500 (Internal Server Error)
        """
        if not campaign_id:
            raise InvalidUsage('campaign_id should be a positive number')
        task_unscheduled = PushCampaignBase.unschedule(campaign_id, request, CampaignUtils.PUSH)
        if task_unscheduled:
            return dict(message='Campaign(id:%s) has been unscheduled.' % campaign_id), 200
        else:
            return dict(message='Campaign(id:%s) is already unscheduled.' % campaign_id), 200


@api.route(PushCampaignApi.SEND)
class SendPushCampaign(Resource):
    """
    Resource sends a specific campaign to associated candidates.
    """
    decorators = [require_oauth()]

    def post(self, campaign_id):
        """
        It sends given Campaign (from given campaign id) to the smartlist candidates
            associated with given campaign.

        :Example:

            >>> import requests
            >>> headers = {'Authorization': 'Bearer <access_token>'}
            >>> campaign_id = 1
            >>> response = requests.post(PushCampaignApiUrl.SEND % campaign_id,
            >>>                          headers=headers)

        .. Response::

                {
                    "message": "Push campaign (id: 1) has been sent successfully to all candidates"
                }

        .. Status:: 200 (OK)
                    401 (Unauthorized to access getTalent)
                    404 (Campaign not found)
                    500 (Internal Server Error)

        .. Error Codes:: 5102 (NoSmartlistAssociated)

        :param campaign_id: integer, unique id representing campaign in GT database
        """
        user = request.user
        # TODO --basit: `user` can be removed, knidly double check every where else
        campaign_obj = PushCampaignBase(user_id=user.id)
        campaign_obj.campaign_id = campaign_id
        campaign_obj.send(campaign_id)
        return dict(message='Campaign(id:%s) is being sent to candidates' % campaign_id), 200


@api.route(PushCampaignApi.BLAST_SENDS)
class PushCampaignBlastSends(Resource):
    """
    Endpoint looks like /v1/push-campaigns/:id/blasts/:id/sends
    This resource is used to GET Campaign "sends" for one particular blast of a given campaign.
    """

    decorators = [require_oauth()]

    def get(self, campaign_id, blast_id):
        """
        Returns Campaign sends for given campaign_id and blast_id

        :Example:

        >>> import requests
        >>> headers = {'Authorization': 'Bearer <access_token>'}
        >>> campaign_id = 1
        >>> blast_id = 1
        >>> response = requests.get(PushCampaignApiUrl.BLAST_SENDS % (campaign_id, blast_id),
        >>>                         headers=headers)

        .. Response::

            {
                "sends":
                        [
                            {
                              "candidate_id": 1,
                              "id": 9,
                              "sent_datetime": "2015-11-23 18:25:09",
                              "blast_id": 1,
                              "updated_datetime": "2015-11-23 18:25:08"
                            },
                            {
                              "candidate_id": 2,
                              "id": 10,
                              "sent_datetime": "2015-11-23 18:25:13",
                              "blast_id": 1,
                              "updated_datetime": "2015-11-23 18:25:13"
                           }
                        ],
                "count": 2
            }

        .. Status:: 200 (OK)
                    400 (Bad request)
                    401 (Unauthorized to access getTalent)
                    403 (Not owner of campaign)
                    404 (Campaign not found)
                    500 (Internal Server Error)

        :param campaign_id: integer, unique id representing campaign in getTalent database
        :return: 1- count of campaign sends and 2- Push campaign sends records as dict
        """
        user = request.user
        # Get a campaign that was created by this user
        campaign = PushCampaignBase.get_campaign_if_domain_is_valid(campaign_id, user,
                                                                    CampaignUtils.PUSH)
        blast = PushCampaignBlast.get_by_id(blast_id)
        if not blast:
            raise ResourceNotFound('Campaign Blast not found with id: %s' % blast_id)
        if blast.campaign_id == campaign.id:
            sends = [send.to_json() for send in blast.blast_sends]
            response = dict(sends=sends, count=len(sends))
            return response, 200
        else:
            raise ForbiddenError('Campaign Blast (id: %s) is not associated with campaign (id: %s)'
                                 % (blast_id, campaign.id))


@api.route(PushCampaignApi.SENDS)
class PushCampaignSends(Resource):
    """
    Endpoint looks like /v1/push-campaigns/:id/sends
    This resource is used to GET Campaign sends
    """

    decorators = [require_oauth()]

    def get(self, campaign_id):
        """
        Returns campaign sends for given push campaign id

        :param campaign_id: integer, unique id representing push campaign in getTalent database
        :return: 1- count of campaign sends and 2- Push campaign sends

        :Example:

            >>> import requests
            >>> headers = {'Authorization': 'Bearer <access_token>'}
            >>> campaign_id = 1
            >>> response = requests.get(PushCampaignApiUrl.SENDS % campaign_id,
            >>>                         headers=headers)

        .. Response::

            {
                "campaign_sends": [
                            {
                              "campaign_blast_id": 10,
                              "candidate_id": 268,
                              "id": 6,
                              "sent_datetime": "2015-12-30 17:03:53"
                            },
                            {
                              "campaign_blast_id": 12,
                              "candidate_id": 268,
                              "id": 7,
                              "sent_datetime": "2015-12-30 17:07:39"
                            }
                ],
                "count": 2

            }

        .. Status:: 200 (OK)
                    401 (Unauthorized to access getTalent)
                    404 (Campaign not found)
                    500 (Internal Server Error)
        """
        user = request.user
        # Get a campaign that was created by this user
        campaign = PushCampaignBase.get_campaign_if_domain_is_valid(campaign_id, user,
                                                                    CampaignUtils.PUSH)
        sends = []
        # Add sends for every blast to `sends` list to get all sends of a campaign.
        # A campaign can have multiple blasts
        [sends.extend(blast.blast_sends.all()) for blast in campaign.blasts.all()]
        # Get JSON serializable data
        sends = [send.to_json() for send in sends]
        response = dict(sends=sends, count=len(sends))
        return response, 200


@api.route(PushCampaignApi.BLASTS)
class PushCampaignBlasts(Resource):
    """
    Endpoint looks like /v1/push-campaigns/:id/blasts.
    This class returns all the blast objects associated with given campaign.
    """
    decorators = [require_oauth()]

    def get(self, campaign_id):
        """
        This endpoint returns a list of blast objects (dict) associated with a
        specific push campaign.

        :param campaign_id: int, unique id of a push campaign
        :return: json data containing list of blasts and their counts


        :Example:

            >>> import requests
            >>> headers = {'Authorization': 'Bearer <access_token>'}
            >>> campaign_id = 1
            >>> response = requests.get(PushCampaignApiUrl.BLASTS % campaign_id,
            >>>                         headers=headers)

        .. Response::

            {
                "blasts": [
                            {
                              "campaign_id": 2,
                              "clicks": 6,
                              "id": 1,
                              "sends": 10,
                              "updated_datetime": "2015-12-30 14:33:44"
                            },
                            {
                              "campaign_id": 2,
                              "clicks": 11,
                              "id": 2,
                              "sends": 20,
                              "updated_datetime": "2015-12-30 14:33:00"
                            }
                ],
                "count": 2

            }

        .. Status:: 200 (OK)
                    401 (Unauthorized to access getTalent)
                    404 (Campaign not found)
                    500 (Internal Server Error)
        """
        user = request.user
        # Get a campaign that was created by this user
        campaign = PushCampaignBase.get_campaign_if_domain_is_valid(campaign_id, user,
                                                                    CampaignUtils.PUSH)
        # Serialize blasts of a campaign
        blasts = [blast.to_json() for blast in campaign.blasts.all()]
        response = dict(blasts=blasts, count=len(blasts))
        return response, 200


@api.route(PushCampaignApi.BLAST)
class PushCampaignBlastById(Resource):
    """
    Resource is used to retrieve a specific campaign's blast.
    """
    decorators = [require_oauth()]

    def get(self, campaign_id, blast_id):
        """
        This endpoint returns a specific blast object (dict)
        associated with a specific push campaign.

        :param campaign_id: int, unique id of a push campaign
        :param blast_id: int, unique id of a blast of campaign
        :return: json data containing blast


        :Example:

            >>> import requests
            >>> headers = {'Authorization': 'Bearer <access_token>'}
            >>> campaign_id = 1
            >>> blast_id = 3
            >>> response = requests.get(PushCampaignApiUrl.BLAST % (campaign_id, blast_id),
            >>>                         headers=headers)

        .. Response::

            {
                "blast":
                        {
                          "campaign_id": 2,
                          "clicks": 6,
                          "id": 3,
                          "sends": 10,
                          "updated_datetime": "2015-12-30 14:33:44"
                        }
            }

        .. Status:: 200 (OK)
                    401 (Unauthorized to access getTalent)
                    404 (Blast not found, Campaign not found)
                    500 (Internal Server Error)
        """
        user = request.user
        # Get a campaign that was created by this user
        # TODO --basit: There is a method in CampaignBase called get_valid_blast_obj(). We can
        # TODO-- use that one here
        campaign = PushCampaignBase.get_campaign_if_domain_is_valid(campaign_id, user,
                                                                    CampaignUtils.PUSH)
        # Serialize blasts of a campaign
        blast = campaign.blasts.filter_by(id=blast_id).first()
        if blast:
            response = dict(blast=blast.to_json())
            return response, 200
        else:
            raise ResourceNotFound('Blast not found for campaign (id: %s) with id %s'
                                   % (campaign_id, blast_id))


@api.route(PushCampaignApi.REDIRECT)
class PushCampaignUrlRedirection(Resource):
    """
    This endpoint redirects the candidate to our app.
    """
    # TODO --basit: We can improve this comment when candidate will be redirected?
    def get(self, url_conversion_id):
        """
        This endpoint is /v1/redirect/:id

        When recruiter(user) assigns a URL as a redirect for that push notification,
        we save the original URL as destination URL in "url_conversion" database table.
        Then we create a new URL (which is
        created during the process of sending campaign to candidate) to redirect the candidate
        to our app. This looks like

                http://127.0.0.1:8013/v1/redirect/1
        After signing this URL, it looks like
        http://127.0.0.1:8013/v1/redirect/1052?valid_until=1453990099.0&auth_user=no_user&extra=
                &signature=cWQ43J%2BkYetfmE2KmR85%2BLmvuIw%3D
        This is called signed_url.

        When candidate clicks on above URL, it is redirected to this flask endpoint, where we
        keep track of number of clicks and hit_counts for a URL. We then create activity that
        'this' candidate has clicked on 'this' campaign. Finally we redirect the candidate to
        destination URL (Original URL provided by the recruiter)

        .. Status:: 200 (OK)
                    400 (Invalid Usage)
                    401 (Unauthorized to access getTalent)
                    403 (Forbidden Error)
                    404 (Campaign not found)
                    500 (Internal Server Error)

        ., Error codes::
                    5005 (EmptyDestinationUrl)

        :param url_conversion_id: id of url_conversion record in db
        :type url_conversion_id: int
        :return: redirects to the destination URL else raises exception
        """
        try:
            redirection_url = CampaignBase.url_redirect(url_conversion_id, CampaignUtils.PUSH,
                                                        verify_signature=True,
                                                        request_args=request.args,
                                                        requested_url=request.full_path)
            return redirect(redirection_url)
        # In case any type of exception occurs, candidate should only get internal server error
        except Exception:
            # As this endpoint is hit by client, so we log the error, and return internal server
            # error.
            logger.exception("Error occurred while URL redirection for Push campaign.")
        return dict(message='Internal Server Error'), 500


@api.route(PushCampaignApi.URL_CONVERSION, PushCampaignApi.URL_CONVERSION_BY_SEND_ID)
class UrlConversionResource(Resource):
    """
    Resource is used to retrieve URL conversion object.
    """
    decorators = [require_oauth()]

    def get(self, **kwargs):
        """
        This endpoint returns a UrlConversion object given by id.
        To get this resource, user must be in same domain as the owner of this send.

        :Example:
            >>> import requests
            >>> headers = {'Authorization': 'Bearer <access_token>'}
            >>> _id = 10
            >>> response = requests.get(PushCampaignApiUrl.URL_CONVERSION % _id,
            >>>                          headers=headers)

            Or you can get UrlConversion JSON object using campaign send id
            >>> send_id = 10
            >>> response = requests.get(PushCampaignApiUrl.URL_CONVERSION_BY_SEND_ID % send_id,
            >>>                          headers=headers)

        .. Response::

                {
                    "url_conversion": {
                        "id": 10,
                        "last_hit_time": "",
                        "hit_count": 0,
                        "added_time": "2016-02-12 12:46:09",
                        "source_url": "http://127.0.0.1:8013/v1/redirect/1638?valid_until=
                        1486903569.01&auth_user=no_user&extra=&signature=ha9B947UcLJ0
                        jbqqSRF4O82%2Bb5E%3D",
                        "destination_url": "https://www.digitalocean.com/community/tutorials/
                        how-to-install-and-use-docker-getting-started"
                    }
                }

        .. Status:: 200 (OK)
                    401 (Unauthorized to access getTalent)
                    403 (Can't get send url conversion with different domain)
                    500 (Internal Server Error)
        """
        user = request.user
        # TODO --basit: Can we move this somehow under CampaignBase? Cause this will be used by all
        # TODO campaigns. Same is for delete method below.
        _id = kwargs.get('_id')
        send_id = kwargs.get('send_id')
        if _id:
            url_conversion = UrlConversion.get_by_id(_id)
            if not url_conversion:
                raise ResourceNotFound('Resource not found with id: %s' % _id)

            send_url_conversion = url_conversion.push_campaign_sends_url_conversions.first()
            if not(send_url_conversion and send_url_conversion.send):
                raise ResourceNotFound('Resource not found')

            if send_url_conversion.send.candidate.user.domain_id != user.domain_id:
                raise ForbiddenError("You can not get other domain's url_conversion records")

            return {'url_conversion': url_conversion.to_json()}

        elif send_id:
            send_url_conversion = PushCampaignSendUrlConversion.get_by_campaign_send_id(send_id)
            if not send_url_conversion:
                raise ResourceNotFound('Resource not found')
            if send_url_conversion.send.candidate.user.domain_id == user.domain_id:
                url_conversion = send_url_conversion.url_conversion.to_json()
                return {'url_conversion': url_conversion}
            else:
                # TODO --basit: Error message can be improved
                raise ForbiddenError('You can not get other domain url_conversion records')

    def delete(self, **kwargs):
        """
        This endpoint deletes a UrlConversion object given by url_conversion id or campaign send id.
        To delete this resource, user must be in same domain as the owner of this send.

        :Example:

            >>> import requests
            >>> headers = {'Authorization': 'Bearer <access_token>'}
            >>> _id = 10
            >>> response = requests.delete(PushCampaignApiUrl.URL_CONVERSION % _id,
            >>>                          headers=headers)

            Or you can delete a UrlConversion rescord by campaign send id.
            >>> send_id = 10
            >>> response = requests.delete(PushCampaignApiUrl.URL_CONVERSION_BY_SEND_ID % send_id,
            >>>                          headers=headers)


        .. Response::

                {
                    "message": "UrlConversion (id: %s) deleted successfully"
                }

        .. Status:: 200 (OK)
                    401 (Unauthorized to access getTalent)
                    403 (Can't get send url conversion with different domain)
                    500 (Internal Server Error)
        """
        _id = kwargs.get('_id')
        send_id = kwargs.get('send_id')
        if _id:
            url_conversion = UrlConversion.get_by_id(_id)
            if not url_conversion:
                raise ResourceNotFound('Resource not found with id: %s' % _id)
            UrlConversion.delete(url_conversion)
            return {'message': "UrlConversion (id: %s) deleted successfully" % _id}
        elif send_id:
            send_url_conversion = PushCampaignSendUrlConversion.get_by_campaign_send_id(send_id)
            if not send_url_conversion:
                raise ResourceNotFound('Resource not found')
            url_conversion = send_url_conversion.url_conversion
            _id = url_conversion.id
            UrlConversion.delete(url_conversion)
            return {'message': "UrlConversion (id: %s) deleted successfully" % _id}

