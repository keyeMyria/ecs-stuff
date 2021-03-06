"""
Celery tasks are defined here. It will be a separate celery process.
These methods are called by run_job method asynchronously

- Running celery using commandline (social_network_service directory) =>

    celery -A social_network_service.social_network_app.celery_app worker  worker --concurrency=4 --loglevel=info

"""
# Builtin imports
import json
import os
import time
import datetime

# 3rd party imports
import pytest
import requests
from redo import retry
from celery.result import AsyncResult
from boto.s3.connection import S3Connection

# Application imports
from social_network_service.common.models.db import db
from social_network_service.common.constants import MEETUP, EVENTBRITE
from social_network_service.common.models.candidate import SocialNetwork
from social_network_service.common.models.event import MeetupGroup, Event
from social_network_service.common.models.user import UserSocialNetworkCredential
from social_network_service.common.talent_config_manager import TalentConfigKeys, TalentEnvs
from social_network_service.common.redis_cache import redis_store
from social_network_service.common.vendor_urls.sn_relative_urls import SocialNetworkUrls
from social_network_service.custom_exceptions import HitLimitReached
from social_network_service.modules.constants import (ACTIONS, MEETUP_EVENT_STATUS, EVENT, MEETUP_EVENT_STREAM_API_URL,
                                                      MEETUP_RSVPS_STREAM_API_URL)
from social_network_service.modules.event.meetup import Meetup
from social_network_service.modules.rsvp.meetup import Meetup as MeetupRsvp
from social_network_service.modules.rsvp.eventbrite import Eventbrite as EventbriteRsvp
from social_network_service.modules.event.eventbrite import Eventbrite as EventbriteEventBase
from social_network_service.modules.social_network.meetup import Meetup as MeetupSocialNetwork
from social_network_service.modules.social_network.base import SocialNetworkBase
from social_network_service.modules.social_network.eventbrite import Eventbrite as EventbriteSocialNetwork
from social_network_service.modules.urls import get_url
from social_network_service.modules.utilities import get_class, EventNotFound, NoUserFound
from social_network_service.social_network_app import celery_app as celery, app


@celery.task(name="events_and_rsvps_importer")
def rsvp_events_importer(social_network_name, mode, user_credentials_id, datetime_range):
    """
    Imports RSVPs or events of a user, create candidates store them in db and also upload them on Cloud search
    :param str social_network_name: Facebook, Eventbrite, Meetup
    :param str mode: rsvp or event
    :param int user_credentials_id: user credentials entry
    :param dict datetime_range:
    """
    with app.app_context():
        logger = app.config[TalentConfigKeys.LOGGER]
        user_credentials = UserSocialNetworkCredential.get_by_id(user_credentials_id)
        user_id = user_credentials.user_id
        try:
            social_network = SocialNetwork.get_by_name(social_network_name.lower())
            social_network_class = get_class(social_network.name.lower(), 'social_network',
                                             user_credentials=user_credentials)
            # we call social network class here for auth purpose, If token is expired
            # access token is refreshed and we use fresh token8
            sn = social_network_class(user_id)

            logger.info('%s Importer has started for %s(UserId: %s). Social Network is %s.'
                        % (mode.title(), sn.user.name, sn.user.id, social_network.name))
            # Call social network process method to start importing rsvps/event
            sn.process(mode, user_credentials=user_credentials, **datetime_range)
            # Update last_updated of each user_credentials.
            user_credentials.update(updated_datetime=datetime.datetime.utcnow())
        except Exception as e:
            logger.exception('start: running %s importer, user_id: %s failed. %s',
                             mode, user_id, e.message)


@celery.task(name="process_meetup_event")
def process_meetup_event(event):
    """
    This celery task is for an individual event to be processed. When `rsvp_events_importer` task finds that some
    event belongs to getTalent user, it passes this event to this task for further processing.

    In this task, we create meetup objects for social network and event and the finally save this event by mapping
    meetup event fields to gt event fields. If event already exists in database, it is updated.

    If an event contains venue information, is is save in `venue` table or updated an existing venue.
    :param dict event: event dictionary from meetup
    """
    with app.app_context():
        logger = app.config[TalentConfigKeys.LOGGER]

        # if same event is received multiple times, accept first and reject remaining
        meetup_event_lock_key = json.dumps(event)
        if not redis_store.get(meetup_event_lock_key):
            # set lock for 5 minutes
            redis_store.set(meetup_event_lock_key, True, 5 * 60)
        else:
            logger.info('Already received this Meetup Event: %s.' % event)
            return 'Done'

        logger.info('Going to process Meetup Event: %s' % event)
        try:
            time.sleep(5)  # wait for event creation api to save event in database otherwise there can be duplicate
            # event created in database (one by api and other by importer)
            groups = MeetupGroup.get_all_records_by_group_id(event['group']['id'])
            meetup = SocialNetwork.get_by_name('Meetup')
            # have to change in try catch as well
            try:
                meetup_sn = MeetupSocialNetwork(user_id=groups[0].user.id, social_network_id=meetup.id)
            except HitLimitReached:
                meetup_sn = MeetupSocialNetwork(user_id=groups[0].user.id, social_network_id=meetup.id,
                                                validate_token=False)
            meetup_event_base = Meetup(user_credentials=meetup_sn.user_credentials,
                                       social_network=meetup, headers=meetup_sn.headers)
            if event['status'] in [MEETUP_EVENT_STATUS['upcoming'],
                                   MEETUP_EVENT_STATUS['suggested'],
                                   MEETUP_EVENT_STATUS['proposed']]:
                event_data = meetup_event_base.fetch_event(event['id'])
                gt_event_data, gt_venue_data = meetup_event_base.event_sn_to_gt_mapping(event_data)
                for group_user in groups:
                    try:
                        group_user_credentials = UserSocialNetworkCredential.get_by_user_and_social_network_id\
                            (group_user.user.id, meetup.id)
                        meetup_event_obj = Meetup(user_credentials=group_user_credentials,
                                                  social_network=meetup, headers=meetup_sn.headers)
                        if gt_venue_data:
                            gt_venue_data['user_id'] = group_user.user_id
                            venue_in_db = meetup_event_obj.save_or_update_venue(gt_venue_data)
                            gt_event_data['venue_id'] = venue_in_db.id
                        gt_event_data['user_id'] = group_user.user_id
                        meetup_event_obj.save_or_update_event(gt_event_data)
                    except Exception as e:
                        logger.error("An error occured while saving event, error: %s" % e)

            elif event['status'] in ['canceled', MEETUP_EVENT_STATUS['deleted']]:
                social_network_event_id = event['id']
                for group_user in groups:
                    try:
                        event_in_db = Event.get_by_user_id_social_network_id_vendor_event_id(group_user.user_id,
                                                                                             meetup.id,
                                                                                             social_network_event_id)
                        if event_in_db:
                            meetup_event_base.user = group_user.user
                            if meetup_event_base.delete_event(event_in_db.id, delete_from_vendor=False):
                                logger.info('Meetup event has been marked as is_deleted_from_vendor in gt database: %s'
                                            % event_in_db.to_json())
                            else:
                                logger.info('Event could not be marked as is_deleted_from_vendor in gt database: %s'
                                            % event_in_db.to_json())
                        else:
                            logger.info("Meetup event not found in database. event:`%s`." % event)
                    except Exception as e:
                        logger.error("An error occured while marking event deleted, error: %s" % e)

        except Exception:
            logger.exception('Failed to save event: %s' % event)
            rollback()


@celery.task(name="process_meetup_rsvp")
def process_meetup_rsvp(rsvp):
    """
    This celery task is for an individual rsvp to be processed. When `meetup_rsvp_importer` task finds that some
    rsvp belongs to event of getTalent's user, it passes this rsvp to this task for further processing.

    In this task, we create meetup objects for social network and event and the finally save this event by mapping
    meetup event fields to gt event fields. If event already exists in database, it is updated.

    Response from Meetup API looks like
    {
        u'group':
                {u'group_city': u'Denver', u'group_lat': 39.68, u'group_urlname': u'denver-metro-chadd-support',
                    u'group_name': u'Denver-Metro CHADD (Children and Adults with ADHD) Meetup',
                    u'group_lon': -104.92,
                    u'group_topics': [
                                        {u'topic_name': u'ADHD', u'urlkey': u'adhd'},
                                        {u'topic_name': u'ADHD Support', u'urlkey': u'adhd-support'},
                                        {u'topic_name': u'Adults with ADD', u'urlkey': u'adults-with-add'},
                                        {u'topic_name': u'Families of Children who have ADD/ADHD',
                                            u'urlkey': u'families-of-children-who-have-add-adhd'},
                                        {u'topic_name': u'ADHD, ADD', u'urlkey': u'adhd-add'},
                                        {u'topic_name': u'ADHD Parents with ADHD Children',
                                            u'urlkey': u'adhd-parents-with-adhd-children'},
                                        {u'topic_name': u'Resources for ADHD', u'urlkey': u'resources-for-adhd'},
                                        {u'topic_name': u'Parents of Children with ADHD',
                                            u'urlkey': u'parents-of-children-with-adhd'},
                                        {u'topic_name': u'Support Groups for Parents with ADHD Children',
                                            u'urlkey': u'support-groups-for-parents-with-adhd-children'},
                                        {u'topic_name': u'Educators Training on AD/HD',
                                            u'urlkey': u'educators-training-on-ad-hd'},
                                        {u'topic_name': u'Adults with ADHD', u'urlkey': u'adults-with-adhd'}
                                    ],
                    u'group_state': u'CO', u'group_id': 1632579, u'group_country': u'us'
                },
        u'rsvp_id': 1639776896,
        u'venue': {u'lat': 39.674759, u'venue_id': 3407262, u'lon': -104.936317,
                   u'venue_name': u'Denver Academy-Richardson Hall'},
        u'visibility': u'public',
        u'event': {u'event_name': u'Manage the Impact of Technology on
                   Your Child and Family with Lana Gollyhorn',
                   u'event_id': u'235574682',
                   u'event_url': u'https://www.meetup.com/denver-metro-chadd-support/events/235574682/',
                   u'time': 1479778200000},
        u'member': {u'member_name': u'Valerie Brown', u'member_id': 195674019}, u'guests': 0,
        u'mtime': 1479312043215, u'response': u'yes'
    }

    :param dict rsvp: rsvp dictionary from Meetup
    """
    with app.app_context():
        logger = app.config[TalentConfigKeys.LOGGER]
        logger.info('Going to process Meetup RSVP: %s' % rsvp)
        try:
            group = MeetupGroup.get_all_records_by_group_id(rsvp['group']['group_id'])
            meetup = SocialNetwork.get_by_name(MEETUP)
            social_network_event_id = rsvp['event']['event_id']
            for group_user in group:
                # Retry for 20 seconds in case we have RSVP for newly created event.
                retry(_get_event, args=(group_user.user_id, meetup.id, social_network_event_id),
                      sleeptime=5, attempts=6, sleepscale=1, retry_exceptions=(EventNotFound,))
                meetup_sn = MeetupSocialNetwork(user_id=group_user.user.id, social_network_id=meetup.id)
                meetup_rsvp_object = MeetupRsvp(user_credentials=meetup_sn.user_credentials, social_network=meetup,
                                                headers=meetup_sn.headers)
                meetup_rsvp_object.rsvp_via_importer = False
                attendee = meetup_rsvp_object.post_process_rsvp(rsvp)
                if attendee and attendee.rsvp_id:
                    logger.info('RSVP imported successfully. rsvp:%s' % rsvp)
                elif attendee:
                    logger.info('RSVP already present in database. rsvp:%s' % rsvp)
        except Exception:
            logger.exception('Failed to save rsvp: %s' % rsvp)
            rollback()


@celery.task(name="process_eventbrite_rsvp")
def process_eventbrite_rsvp(rsvp):
    """
    This celery task is for an individual RSVP received from Eventbrite to be processed.

    Response from Eventbrite API looks like
        {
            u'config': {u'action': u'order.placed', u'user_id': u'149011448333',
            u'endpoint_url': u'https://emails.ngrok.io/webhook/1', u'webhook_id': u'274022'},
            u'api_url': u'https://www.eventbriteapi.com/v3/orders/573384540/'
        }

    :param dict rsvp: rsvp dictionary from Eventbrite
    """
    with app.app_context():
        logger = app.config[TalentConfigKeys.LOGGER]
        logger.info('Going to process Eventbrite RSVP: %s' % rsvp)
        try:
            eventbrite = SocialNetwork.get_by_name(EVENTBRITE)
            webhook_id = rsvp['config']['webhook_id']
            user_credentials = UserSocialNetworkCredential.get_by_webhook_id_and_social_network_id(webhook_id,
                                                                                                   eventbrite.id)
            if not user_credentials:
                raise NoUserFound("No User found in database that corresponds to webhook_id:%s" % webhook_id)
            # we make social network object here to check the validity of access token.
            # If access token is valid, we proceed to do the processing to save in getTalent db tables otherwise
            # we raise exception AccessTokenHasExpired.
            sn_obj = EventbriteSocialNetwork(user_id=user_credentials.user_id, social_network_id=eventbrite.id)
            eventbrite_rsvp_object = EventbriteRsvp(user_credentials=user_credentials, social_network=eventbrite,
                                                    headers=sn_obj.headers)
            attendee = eventbrite_rsvp_object.process_rsvp_via_webhook(rsvp)
            if attendee and attendee.rsvp_id:
                logger.info('RSVP imported successfully. rsvp:%s' % rsvp)
            elif attendee:
                logger.info('RSVP already present in database. rsvp:%s' % rsvp)
        except Exception:
            logger.exception('Failed to save rsvp: %s' % rsvp)
            rollback()


@celery.task(name="import_eventbrite_event")
def import_eventbrite_event(user_id, event_url, action_type):
    """
    This celery task retrieves user event from eventbrite and then saves or
    """
    with app.app_context():
        logger = app.config[TalentConfigKeys.LOGGER]
        logger.info('Going to process Eventbrite Event: %s' % event_url)
        try:
            eventbrite = SocialNetwork.get_by_name('Eventbrite')
            eventbrite_sn = EventbriteSocialNetwork(user_id=user_id, social_network_id=eventbrite.id)
            eventbrite_event_base = EventbriteEventBase(headers=eventbrite_sn.headers,
                                                        user_credentials=eventbrite_sn.user_credentials,
                                                        social_network=eventbrite_sn.user_credentials.social_network)
            if action_type in [ACTIONS['created'], ACTIONS['published']]:
                logger.info('Event Published on Eventbrite, Event URL: %s' % event_url)
                eventbrite_event_base.get_event(event_url)
            elif action_type == ACTIONS['unpublished']:
                event_id = event_url.split('/')[-2]
                event_id = int(event_id)
                event_in_db = Event.get_by_user_id_social_network_id_vendor_event_id(user_id,
                                                                                     eventbrite.id,
                                                                                     event_id
                                                                                     )
                if event_in_db:
                    if eventbrite_event_base.delete_event(event_in_db.id, delete_from_vendor=False):
                        logger.info('Event has been marked as is_deleted_from_vendor in gt database: %s'
                                    % event_in_db.to_json())
                    else:
                        logger.info('Event could not be marked as is_deleted_from_vendor in gt database: %s'
                                    % event_in_db.to_json())
                else:
                    logger.info("Event unpublished from Eventbrite but it does not exist, don't worry. Event URL: %s"
                                % event_url)
            elif action_type == ACTIONS['updated']:
                pass  # We are handling update action yet because it causes duplicate entries

        except Exception:
            logger.exception('Failed to save event. URL: %s' % event_url)


@celery.task
def error_callback(uuid):
    with app.app_context():
        logger = app.config[TalentConfigKeys.LOGGER]
        print uuid
        result = AsyncResult(uuid)
        exc = result.get(propagate=False)
        logger.error('Task {0} raised exception: {1!r}\n{2!r}'.format(
            uuid, exc, result.traceback))
        db.session.rollback()


def rollback():
    try:
        db.session.rollback()
    except Exception:
        pass


def _get_event(user_id, social_network_id, social_network_event_id):
    """
    This searches the event in database for given parameters.
    :param positive user_id: If of user
    :param positive social_network_id: Id of Meetup social-network
    :param string social_network_event_id: Id of event on Meetup website
    """
    db.session.commit()
    event = Event.get_by_user_id_social_network_id_vendor_event_id(user_id,
                                                                   social_network_id,
                                                                   social_network_event_id)
    if not event:  # TODO: If event is going to happen in future, we should import that event here
        raise EventNotFound('Event is not present in db, social_network_event_id is %s. User Id: %s'
                            % (social_network_event_id, user_id))


@celery.task(name="import_events")
def sync_events(user_credentials):
    """
    This celery task imports all active/live events of a specific user and social network and it will be invoked when
    user will subscribe to Meetup or Eventbrite.
    e.g. if a user subscribes to Meetup, it will import all his upcoming, proposed and suggested events.
     In case of eventbrite, it will import all live events.
    :param type(t) user_credentials: UserSocialNetworkCredentials object
    """
    user_credentials = db.session.merge(user_credentials)
    social_network_base = SocialNetworkBase(user_id=user_credentials.user_id,
                                            social_network_id=user_credentials.social_network_id)
    social_network_base.process(EVENT, user_credentials=user_credentials)


@celery.task(name="import_meetup_events")
def import_meetup_events():
    """
    This task starts at service startup and then it keeps fetching events using Meetup stream API.
    """
    with app.app_context():
        logger = app.config[TalentConfigKeys.LOGGER]
        logger.info('Meetup Event Importer started at UTC: %s' % datetime.datetime.utcnow())

        while True:
            try:
                url = MEETUP_EVENT_STREAM_API_URL
                response = requests.get(url, stream=True, timeout=30)
                logger.info('Meetup Stream Response Status: %s' % response.status_code)
                for raw_event in response.iter_lines():
                    if raw_event:
                        try:
                            event = json.loads(raw_event)
                            group_id = event['group']['id']
                            MeetupGroup.session.commit()
                            group = MeetupGroup.get_by_group_id(group_id)
                            if group:
                                logger.info('Going to save event: %s' % event)
                                process_meetup_event.delay(event)
                        except ValueError:
                            pass
                        except Exception as e:
                            logger.exception('Error occurred while parsing event data, Error: %s\nEvent: %s' %
                                             (e, raw_event))
                            raise
            except Exception as e:
                logger.warning('Out of main loop. Cause: %s' % e)
                time.sleep(5)
                rollback()


@celery.task(name="import_meetup_rsvps")
def import_meetup_rsvps():
    with app.app_context():
        logger = app.config[TalentConfigKeys.LOGGER]
        logger.info('Meetup Rsvp Importer started at UTC: %s' % datetime.datetime.utcnow())

    while True:
        try:
            url = MEETUP_RSVPS_STREAM_API_URL
            response = requests.get(url, stream=True, timeout=30)
            logger.info('Meetup Stream Response Status: %s' % response.status_code)
            for raw_rsvp in response.iter_lines():
                if raw_rsvp:
                    try:
                        rsvp = json.loads(raw_rsvp)
                        group_id = rsvp['group']['group_id']
                        MeetupGroup.session.commit()
                        group = MeetupGroup.get_by_group_id(group_id)
                        if group:
                            logger.info('Going to save rsvp: %s' % rsvp)
                            process_meetup_rsvp.delay(rsvp)
                    except ValueError:
                        pass
                    except Exception as e:
                        logger.exception('Error occurred while parsing rsvp data, Error: %s\nRsvp: %s' %
                                         (e, raw_rsvp))
                        raise
        except Exception as e:
            logger.warning('Out of main loop. Cause: %s' % e)
            time.sleep(5)
            rollback()


@celery.task(name="run_tests")
def run_tests(args, file_path, user_id):
    """
    This task takes list of args which are actually list of test modules, functions or some search criteria based on
    which pytest will run tests.
    :param list args: list of pytest args
    :param str file_path: html file path
    :param int | long user_id: user id
    """
    with app.app_context():
        output_formats = ['json', 'html']
        content_types = ['application/json', 'text/html']
        logger = app.config[TalentConfigKeys.LOGGER]
        aws_access_key_id = app.config[TalentConfigKeys.AWS_KEY]
        aws_secret_access_key = app.config[TalentConfigKeys.AWS_SECRET]
        env = app.config[TalentConfigKeys.ENV_KEY]
        log_message = '''%s:
                         Environment: %s,
                         UserId: %s
                         args: %s
                         %s: %s
                         '''
        try:
            args.extend(['--{0}={1}.{0}'.format(_type, file_path) for _type in output_formats])
            pytest.main(args)
            with open(file_path + '.json') as f:
                output = f.read()
            logger.info(log_message % ('Tests Pass:', env, user_id, args, 'Output', output))
            if env in [TalentEnvs.QA, TalentEnvs.PROD]:
                s3_connection = S3Connection(aws_access_key_id, aws_secret_access_key)
                bucket_obj = s3_connection.get_bucket('api-test-results')
                for ext, mime in zip(output_formats, content_types):
                    key_name = '%s/%s.%s' % (env, file_path.split('/')[-1], ext)
                    filename = '%s.%s' % (file_path, ext)
                    key = bucket_obj.new_key(key_name=key_name)
                    key.set_metadata('Content-Type', mime)
                    key.set_contents_from_filename(filename)
                    os.unlink(filename)
                    logger.info('Output files uploaded on S3 Key: %s%s' % ('api-test-results', key_name))
        except Exception as e:
            logger.error(log_message % ('Failed to run tests:', env, user_id, args, 'Error', e))
