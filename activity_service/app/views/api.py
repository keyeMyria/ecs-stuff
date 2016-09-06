"""Activities API for getting activities for a user's domain or posting new activities
   to the database.
"""
__author__ = 'erikfarmer'
# stdlib
from datetime import datetime
from uuid import uuid4
import json
import re
from time import time
# framework specific/third party
from flask import jsonify
from flask import request
from flask import Blueprint
from requests import codes as STATUS_CODES

# application specific
from activity_service.common.models.user import User
from activity_service.app import db, logger
from activity_service.common.routes import ActivityApi
from activity_service.common.models.misc import Activity
from activity_service.common.error_handling import NotFoundError
from activity_service.common.utils.api_utils import ApiResponse
from activity_service.common.utils.auth_utils import require_oauth
from activity_service.common.campaign_services.campaign_utils import CampaignUtils

DATE_FORMAT = '%Y-%m-%dT%H:%M:%S'
POSTS_PER_PAGE = 20
mod = Blueprint('activities_api', __name__)


@mod.route(ActivityApi.ACTIVITIES_PAGE, methods=['GET'])
@require_oauth()
def get_activities(page):
    """
    :param int page: Page used in pagination for GET requests.
    :return: JSON formatted pagination response or message notifying creation status.
    """
    start_datetime, end_datetime = None, None
    valid_user_id = request.user.id
    is_aggregate_request = request.args.get('aggregate') == '1'
    start_param = request.args.get('start_datetime')
    end_param = request.args.get('end_datetime')
    api_id = uuid4()
    tam = TalentActivityManager(api_id)

    if start_param:
        start_datetime = datetime.strptime(start_param, DATE_FORMAT)

    if end_param:
        end_datetime = datetime.strptime(end_param, DATE_FORMAT)

    if is_aggregate_request:
        return jsonify({
            'activities': tam.get_recent_readable(
                valid_user_id, start_datetime=start_datetime, end_datetime=end_datetime
            )
        })

    else:
        post_qty = request.args.get('post_qty') if request.args.get('post_qty') else POSTS_PER_PAGE

        try:
            request_page = int(page)

        except ValueError:
            return jsonify({'error': {'message': 'page parameter must be an integer'}}), STATUS_CODES.bad

        return jsonify(tam.get_activities(user_id=valid_user_id, post_qty=post_qty,
                                          start_datetime=start_datetime,
                                          end_datetime=end_datetime, page=request_page))


@mod.route(ActivityApi.ACTIVITY_MESSAGES, methods=['GET'])
@require_oauth()
def get_activity_messages():
    """
    This endpoint returns a dictionary where keys are activity type ids and values are
    raw messages for that kind of activities.

    .. Response::

        {
            1: [
                "%(username)s uploaded resume of candidate %(formattedName)s",
                "%(username)s uploaded %(count)s candidate resumes",
                "candidate.png" ],

            2: [
                "%(username)s updated candidate %(formattedName)s",
                "%(username)s updated %(count)s candidates",
                "candidate.png" ],
            .
            .
            .
        }
    :return:
    """
    return jsonify(dict(messages=TalentActivityManager.MESSAGES))


@mod.route(ActivityApi.ACTIVITIES, methods=['GET', 'POST'])
@require_oauth()
def post_activity():
    valid_user_id = request.user.id
    if request.method == 'POST':
        content = request.get_json()

        return create_activity(valid_user_id, content.get('type'), content.get('source_table'),
                               content.get('source_id'), content.get('params'))
    source_table = request.args.get('source_table')
    source_id = request.args.get('source_id')
    type_id = request.args.get('type')
    activity = Activity.get_single_activity(valid_user_id, type_id, source_id, source_table)
    if not activity:
        raise NotFoundError('Activity not found for given query params.')

    return ApiResponse(json.dumps({"activity": activity.to_json()}), status=STATUS_CODES.OK)


def create_activity(user_id, type_, source_table=None, source_id=None, params=None):
    """Method for creating a DB entry in the activity table.
    :param int user_id: ID of the authenticated user.
    :param int type_: Integer corresponding to TalentActivityAPI attributes.
    :param str|None source_table: String representing the DB table the activity relates to.
    :param int|None source_id: Integer of the source_table's ID for entered specific activity.
    :param dict|None params: Dictionary of created/updated source_table attributes.
    :return: HTTP Response
    """
    activity = Activity(
        user_id=int(user_id),
        type=type_,
        source_table=source_table,
        source_id=source_id,
        params=json.dumps(params) if params else None,
        added_time=datetime.utcnow()
    )
    try:
        db.session.add(activity)
        db.session.commit()
        return json.dumps({'activity': {'id': activity.id}}), STATUS_CODES.created
    except Exception:
        # TODO logging
        return json.dumps({'error': 'There was an error saving your log entry'}), STATUS_CODES.internal_server_error


class TalentActivityManager(object):
    """API class for ActivityService."""
    # params=dict(id, formattedName, sourceProductId, client_ip (if widget))
    MESSAGES = {
        Activity.MessageIds.RSVP_EVENT: (
            "%(firstName)s  %(lastName)s responded <b>%(response)s</b> "
            "on %(creator)s 's event <b>'%(eventTitle)s'</b> %(img)s",
            "%(firstName)s  %(lastName)s responded <b>%(response)s<b>"
            " on event '%(eventTitle)s'",
            "candidate.png"),
        Activity.MessageIds.EVENT_CREATE: ("%(username)s created an event <b>%(event_title)s",
                                           "%(username)s created %(count)s events.</b>",
                                           "event.png"),
        Activity.MessageIds.EVENT_DELETE: ("%(username)s deleted an event <b>%(event_title)s",
                                           "%(username)s deleted %(count)s events.</b>",
                                           "event.png"),
        Activity.MessageIds.EVENT_UPDATE: ("%(username)s updated an event <b>%(event_title)s.",
                                           "%(username)s updated %(count)s events.</b>",
                                           "event.png"),
        Activity.MessageIds.CANDIDATE_CREATE_WEB: (
            "%(username)s uploaded resume of candidate %(formattedName)s",
            "%(username)s uploaded %(count)s candidate resumes", "candidate.png"),
        Activity.MessageIds.CANDIDATE_CREATE_CSV: (
            "%(username)s imported candidate %(formattedName)s via spreadsheet",
            "%(username)s imported %(count)s candidates via spreadsheet",
            "candidate.png"),
        Activity.MessageIds.CANDIDATE_CREATE_WIDGET: (
            "Candidate %(formattedName)s joined via widget",
            "%(count)s candidates joined via widget", "widget.png"),
        Activity.MessageIds.CANDIDATE_CREATE_MOBILE: (
            "%(username)s added candidate %(formattedName)s via mobile",
            "%(username)s added %(count)s candidates via mobile",
            "candidate.png"),
        Activity.MessageIds.CANDIDATE_UPDATE: (
            "%(username)s updated candidate %(formattedName)s",
            "%(username)s updated %(count)s candidates",

            "candidate.png"),
        Activity.MessageIds.CANDIDATE_DELETE: (
            "%(username)s deleted candidate %(formattedName)s",
            "%(username)s deleted %(count)s candidates",
            "candidate.png"),
        Activity.MessageIds.CAMPAIGN_CREATE: (
            "%(username)s created an %(campaign_type)s campaign: %(campaign_name)s",
            "%(username)s created %(count)s campaigns",
            "campaign.png"),
        Activity.MessageIds.CAMPAIGN_DELETE: (
            "%(username)s deleted an %(campaign_type)s campaign: %(name)s",
            "%(username)s deleted %(count)s campaigns",
            "campaign.png"),
        Activity.MessageIds.CAMPAIGN_SEND: (
            "Campaign %(name)s was sent to %(num_candidates)s candidates",
            "%(count)s campaigns were sent out",
            "campaign.png"),
        Activity.MessageIds.CAMPAIGN_EXPIRE: (
            "%(username)s's recurring campaign %(name)s has expired",
            "%(count)s recurring campaigns of %(username)s have expired", "campaign.png"),  # TODO
        Activity.MessageIds.CAMPAIGN_PAUSE: (
            "%(username)s paused campaign %(name)s", "%(username)s paused %(count)s campaigns",
            "campaign.png"),
        Activity.MessageIds.CAMPAIGN_RESUME: (
            "%(username)s resumed campaign %(name)s", "%(username)s resumed %(count)s campaigns",
            "campaign.png"),
        Activity.MessageIds.SMARTLIST_CREATE: (
            "%(username)s created list %(name)s", "%(username)s created %(count)s lists",
            "smartlist.png"),
        Activity.MessageIds.SMARTLIST_DELETE: (
            "%(username)s deleted list: %(name)s", "%(username)s deleted %(count)s lists",
            "smartlist.png"),
        Activity.MessageIds.DUMBLIST_CREATE: (
            "%(username)s created a list: <b>%(name)s</b>.", "%(username)s created %(count)s lists",
            "dumblist.png"),
        Activity.MessageIds.DUMBLIST_DELETE: (
            "%(username)s deleted list %(name)s", "%(username)s deleted %(count)s lists",
            "dumblist.png"),
        Activity.MessageIds.SMARTLIST_ADD_CANDIDATE: (
            "%(formattedName)s was added to list %(name)s",
            "%(count)s candidates were added to list %(name)s",
            "smartlist.png"),
        Activity.MessageIds.SMARTLIST_REMOVE_CANDIDATE: (
            "%(formattedName)s was removed from list %(name)s",
            "%(count)s candidates were removed from list %(name)s",
            "smartlist.png"),
        Activity.MessageIds.USER_CREATE: (
            "%(username)s has joined", "%(count)s users have joined", "notification.png"),
        Activity.MessageIds.WIDGET_VISIT: (
            "Widget was visited", "Widget was visited %(count)s times", "widget.png"),
        Activity.MessageIds.NOTIFICATION_CREATE: (
            "You received an update notification", "You received %(count)s update notifications",
            "notification.png"),
        Activity.MessageIds.CAMPAIGN_EMAIL_SEND: (
            "%(candidate_name)s received email of campaign %(campaign_name)s",
            "%(count)s candidates received email of campaign %(campaign_name)s", "campaign.png"),
        Activity.MessageIds.CAMPAIGN_EMAIL_OPEN: (
            "%(candidate_name)s opened email of campaign %(campaign_name)s",
            "%(count)s candidates opened email of campaign %(campaign_name)s", "campaign.png"),
        Activity.MessageIds.CAMPAIGN_EMAIL_CLICK: (
            "%(candidate_name)s clicked email of campaign %(campaign_name)s",
            "Campaign %(campaign_name)s was clicked %(count)s times", "campaign.png"),
        Activity.MessageIds.CAMPAIGN_SMS_SEND: (
            "SMS Campaign <b>%(campaign_name)s</b> has been sent to %(candidate_name)s.",
            "SMS Campaign %(campaign_name)s has been sent to %(candidate_name)s.",
            "campaign.png"),
        Activity.MessageIds.CAMPAIGN_SMS_CLICK: (
            "%(candidate_name)s clicked on SMS Campaign <b>%(campaign_name)s</b>.",
            "%(candidate_name)s clicked on %(campaign_name)s.",
            "campa"
            "ign.png"),
        Activity.MessageIds.CAMPAIGN_SMS_REPLY: (
            "%(candidate_name)s replied <b>%(reply_text)s</b> on SMS campaign %(campaign_name)s.",
            "%(candidate_name)s replied '%(reply_text)s' on campaign %(campaign_name)s.",
            "campaign.png"),
        Activity.MessageIds.CAMPAIGN_SCHEDULE: (
            "%(username)s scheduled an %(campaign_type)s campaign: <b>%(campaign_name)s</b>.",
            "%(username)s scheduled an %(campaign_type)s campaign: <b>%(campaign_name)s</b>.",
            "campaign.png"),
        Activity.MessageIds.PIPELINE_CREATE: (
            "%(username)s created a pipeline: <b>%(name)s</b>.",
            "%(username)s created a pipeline: <b>%(name)s</b>.",
            "pipeline.png"),
        Activity.MessageIds.PIPELINE_DELETE: (
            "%(username)s deleted pipeline: <b>%(name)s</b>.",
            "%(username)s deleted pipeline: <b>%(name)s</b>.",
            "pipeline.png"),
        Activity.MessageIds.TALENT_POOL_CREATE: (
            "%(username)s created a Talent Pool: <b>%(name)s</b>.",
            "%(username)s created a Talent Pool: <b>%(name)s</b>.",
            "talent_pool.png"),
        Activity.MessageIds.TALENT_POOL_DELETE: (
            "%(username)s deleted Talent Pool: <b>%(name)s</b>.",
            "%(username)s deleted Talent Pool: <b>%(name)s</b>.",
            "talent_pool.png"),
        Activity.MessageIds.CAMPAIGN_PUSH_CREATE: (
            "%(username)s created a Push campaign: '%(campaign_name)s'",
            "%(username)s created a Push campaign: '%(campaign_name)s'",
            "campaign.png"),
        Activity.MessageIds.CAMPAIGN_PUSH_SEND: (
            "Push Campaign <b>%(campaign_name)s</b> has been sent to %(candidate_name)s.",
            "Push Campaign %(campaign_name)s has been sent to %(candidate_name)s.",
            "campaign.png"),
        Activity.MessageIds.CAMPAIGN_PUSH_CLICK: (
            "%(candidate_name)s clicked on Push Campaign <b>%(campaign_name)s</b>.",
            "%(candidate_name)s clicked on %(campaign_name)s.",
            "campaign.png")
    }

    def __init__(self, call_id):
        self._check_format_string_regexp = re.compile(r'%\((\w+)\)s')
        self.call_id = call_id

    def get_activities(self, user_id, post_qty, start_datetime=None, end_datetime=None, page=1):
        """Method for retrieving activity logs based on a domain ID that is extracted via an
           authenticated user ID.
        :param int user_id: ID of the authenticated user.
        :param datetime|None start_datetime: Optional datetime object for query filters.
        :param datetime|None end_datetime: Optional datetime object for query filters.
        :param int page: Pagination start.
        :return: JSON encoded SQL-Alchemy.pagination response.
        """
        user_domain_id = User.query.filter_by(id=user_id).value('domainId')
        user_ids = User.query.filter_by(domain_id=user_domain_id).values('id')
        flattened_user_ids = [item for sublist in user_ids for item in sublist]
        filters = [Activity.user_id.in_(flattened_user_ids)]
        if start_datetime: filters.append(Activity.added_time > start_datetime)
        if end_datetime: filters.append(Activity.added_time < end_datetime)
        activities = Activity.query.filter(*filters).order_by(Activity.added_time.desc())\
            .paginate(page, post_qty, False)
        activities_response = {
            'total_count': activities.total,
            'items': [{
                          'params': json.loads(activity.params),
                          'source_table': activity.source_table,
                          'source_id': activity.source_id,
                          'type': activity.type,
                          'user_id': activity.user_id,
                          'user_name': activity.user.name if activity.user else '',
                          'added_time': str(activity.added_time),
                          'id': activity.id
                      }
                      for activity in activities.items
                      ]
        }
        return activities_response

    # Like 'get' but gets the last 200 consecutive activity types. can't use GROUP BY because it doesn't respect ordering.
    def get_recent_readable(self, user_id, start_datetime=None, end_datetime=None, limit=3):
        logger.info("{} getting recent readable for {} - {}".format(
            self.call_id, start_datetime or 'N/A', end_datetime or 'N/A'
        ))

        start_time = time()
        current_user = User.query.filter_by(id=user_id).first()
        logger.info("{} fetched current user in {} seconds".format(self.call_id, time() - start_time))

        # Get the last 200 activities and aggregate them by type, with order.
        user_domain_id = current_user.domain_id
        user_ids = User.query.filter_by(domain_id=user_domain_id).values('id')
        logger.info("{} fetched domain IDs in {} seconds".format(self.call_id, time() - start_time))
        flattened_user_ids = [item for sublist in user_ids for item in sublist]
        logger.info("{} flattened domain IDs in {} seconds".format(self.call_id, time() - start_time))
        filters = [Activity.user_id.in_(flattened_user_ids)]

        if start_datetime:
            filters.append(Activity.added_time>=start_datetime)
        if end_datetime:
            filters.append(Activity.added_time<=end_datetime)

        activities = Activity.query.filter(*filters).limit(200)
        logger.info("{} fetched activities in {} seconds".format(
            self.call_id, time() - start_time)
        )

        aggregated_activities = []
        current_activity_count = 0

        for i, activity in enumerate(activities):
            current_activity_count += 1
            current_activity_type = activity.type
            if current_activity_type not in self.MESSAGES:
                logger.error('Given Campaign Type (%s) not found.' % current_activity_type)
                continue
            next_activity_type = activities[i + 1].type if (
                i < activities.count() - 1) else None  # None means last activity

            if current_activity_type != next_activity_type:  # next activity is new, or the very last one, so aggregate these ones
                activity_aggregate = {}
                activity_aggregate['count'] = current_activity_count
                activity_aggregate['readable_text'] = self._activity_text(activity,
                                                                          activity_aggregate[
                                                                              'count'],
                                                                          current_user)
                activity_aggregate['image'] = self.MESSAGES[activity.type][2]

                aggregated_activities.append(activity_aggregate)
                if len(aggregated_activities) == limit:  # if we've got enough activity groups, quit
                    break

                current_activity_count = 0
        logger.info("{} finished making readable in {} seconds".format(self.call_id, time() - start_time))

        return aggregated_activities

    def _activity_text(self, activity, count, current_user):
        if activity.user_id != current_user.id:
            username = User.query.filter_by(id=activity.user_id).value('firstName')
        else:
            username = "You"

        params = json.loads(activity.params) if activity.params else dict()
        params['username'] = username

        format_strings = self.MESSAGES.get(activity.type)
        if not format_strings:
            format_string = "No message for activity type %s" % activity.type
        elif not count or count == 1:  # one single activity
            format_string = format_strings[0]
            if 'You has' in format_string:
                format_string = format_string.replace('You has',
                                                      'You have')  # To fix 'You has joined'
            elif "You's" in format_string:  # To fix "You's recurring campaign has expired"
                format_string = format_string.replace("You's", "Your")
        else:  # many activities
            format_string = format_strings[1]
            params['count'] = count

        # If format_string has a param not in params, set it to unknown
        for param in re.findall(self._check_format_string_regexp, format_string):
            if not params.get(param):
                params[param] = 'unknown'
            if param == 'campaign_type' and params[param].lower() not in CampaignUtils.WITH_ARTICLE_AN:
                format_string = format_string.replace("an", "a")

        return format_string % params