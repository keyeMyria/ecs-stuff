"""
Author: Hafiz Muhammad Basit, QC-Technologies, <basit.gettalent@gmail.com>

Here we have helper functions to be used in tests
"""
from datetime import datetime, timedelta
from app_common.common.campaign_services.tests_helpers import CampaignsTestsHelpers
from app_common.common.models.misc import Frequency
from app_common.common.tests.sample_data import fake
from ....utils.datetime_utils import DatetimeUtils

__author__ = 'basit'


# This is common data for creating test events
EVENT_DATA = {
    "organizer_id": '',  # will be updated in fixture 'meetup_event_data' or 'eventbrite_event_data'
    "venue_id": '',  # will be updated in fixture 'meetup_event_data' or 'eventbrite_event_data'
    "title": "Test Event",
    "description": "Test Event Description",
    "registration_instruction": "Just Come",
    "start_datetime": (datetime.utcnow() + timedelta(days=2)).strftime(DatetimeUtils.ISO8601_FORMAT),
    "end_datetime": (datetime.utcnow() + timedelta(days=3)).strftime(DatetimeUtils.ISO8601_FORMAT),
    "group_url_name": "QC-Python-Learning",
    "social_network_id": '',  # will be updated in fixture 'meetup_event_data' or 'eventbrite_event_data'
    "timezone": "Asia/Karachi",
    "cost": 0,
    "currency": "USD",
    "social_network_group_id": 18837246,
    "max_attendees": 10
}


def create_data_for_campaign_creation(subject, smartlist_id, campaign_name=fake.name()):
    """
    This function returns the required data to create an email campaign.
    """
    body_text = fake.sentence()
    body_html = "<html><body><h1>%s</h1></body></html>" % body_text
    return {'name': campaign_name,
            'subject': subject,
            'body_html': body_html,
            'frequency_id': Frequency.ONCE,
            'list_ids': [smartlist_id] if smartlist_id else []
            }
