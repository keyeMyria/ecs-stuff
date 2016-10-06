"""
This file contain tests for Social network service Graphql endpoint. It's a single endpoint that
wil return different data base on given query.
"""
# App specific imports
from social_network_service.common.models.user import User
from social_network_service.common.models.venue import Venue
from social_network_service.common.models.event import Event
from social_network_service.common.models.candidate import SocialNetwork
from social_network_service.common.models.event_organizer import EventOrganizer
from social_network_service.common.utils.handy_functions import camel_case_to_snake_case
from social_network_service.tests.helper_functions import get_graphql_data
from social_network_service.common.utils.graphql_utils import (get_query, validate_graphql_response, get_fields)


def test_get_me(token_first, user_first):
    """
    In this test we are validating that graphql endpoint returns logged-in user's data.
    """
    fields = get_fields(User)
    query = get_query('me', fields)
    response = get_graphql_data(query, token_first)
    assert 'errors' not in response, 'Response: %s\nQuery: %s' % (response, query)
    validate_graphql_response('me', response, fields)
    me = response['data']['me']
    assert me['id'] == user_first['id']
    assert me['email'] == user_first['email']


def test_get_event(token_first, eventbrite_event):
    """
    Validate that Graphql endpoint is working fine for `event` and `events` queries.
    Also match data for single event.
    """
    response = assert_valid_response('event', Event, token_first, eventbrite_event['id'])
    event = response['data']['event']
    match_data(event, eventbrite_event, get_fields(Event, exclude=('organizerId', 'url')))


def test_get_events_pagination(token_first, eventbrite_event, meetup_event):
    """
    Validate that pagination is working fine. There are two events created by test user.
    We will get 2 events in first page and then no events in second page (request)
    """
    assert_valid_response('event', Event, token_first, eventbrite_event['id'])
    fields = get_fields(Event)
    query = get_query('events', fields, args=dict(page=1, perPage=10))
    response = get_graphql_data(query, token_first)
    assert 'errors' not in response, 'Response: %s\nQuery: %s' % (response, query)
    validate_graphql_response('events', response, fields, is_array=True)

    # Since there were only two events created, now getting events for second page will return no events
    query = get_query('events', fields, args=dict(page=2, perPage=10))
    response = get_graphql_data(query, token_first)
    assert 'errors' not in response, 'Response: %s\nQuery: %s' % (response, query)
    assert response['data']['events'] == []


def test_get_event_relationship_objects(token_first):
    """
    This test validates that by adding model relationships and their fields will work and Graphql will return those
    relationships data as well. e.g. in this case, we are getting eventOrganizer data inside events data
    """
    fields = get_fields(Event, relationships=('eventOrganizer',))
    query = get_query('events', fields)
    response = get_graphql_data(query, token_first)
    assert 'errors' not in response, 'Response: %s\nQuery: %s' % (response, query)
    validate_graphql_response('events', response, fields, is_array=True)


def test_get_venue(token_first, eventbrite_venue):
    """
    Get a list of venues and a single venue by id. Match response data from expected data.
    """
    response = assert_valid_response('venue', Venue, token_first, eventbrite_venue['id'])
    venue = response['data']['venue']
    assert venue['id'] == eventbrite_venue['id']


def test_get_organizer(token_first, organizer_in_db):
    """
    This test validates that `organizer` and `organizers` queries are working fine. it also matches requested
     organizer's id with returned data.
    """
    response = assert_valid_response('organizer', EventOrganizer, token_first, organizer_in_db['id'])
    assert response['data']['organizer']['id'] == organizer_in_db['id']


def test_get_social_network(token_first, eventbrite):
    """
    This test validates that `socialNetwork` and `socialNetworks` queries are working fine. it also matches
     eventbrite id with returned data.
    """
    assert_valid_response('socialNetwork', SocialNetwork, token_first, eventbrite['id'], ignore_id_test=True)
    fields = get_fields(SocialNetwork)
    query = get_query('socialNetwork', fields, args=dict(name='Eventbrite'))
    response = get_graphql_data(query, token_first)
    assert 'errors' not in response, 'Response: %s\nQuery: %s' % (response, query)
    validate_graphql_response('socialNetwork', response, fields)
    assert response['data']['socialNetwork']['id'] == eventbrite['id']


def test_get_subscribed_social_network(token_first):
    """
    This test validates that `subscribedSocialNetwork` query is returning a list of subscribed social networks.
    """
    assert_valid_response('subscribedSocialNetwork', SocialNetwork, token_first, None, ignore_id_test=True)


def test_get_meetup_groups(token_first):
    """
    This test validates that `meetupGroups` query is returning a list of user's groups on meetup.
    """
    fields = ['id', 'name', 'urlname']
    query = get_query('meetupGroups', fields)
    response = get_graphql_data(query, token_first)
    assert 'errors' not in response, 'Response: %s\nQuery: %s' % (response, query)
    validate_graphql_response('meetupGroups', response, fields, is_array=True)


def test_get_timezones(token_first):
    """
    Validate that `timezone` query will return a list of timezones containing `name` and `value` fields.
    """
    fields = ['name', 'value']
    query = get_query('timezones', fields)
    response = get_graphql_data(query, token_first)
    assert 'errors' not in response, 'Response: %s\nQuery: %s' % (response, query)
    validate_graphql_response('timezones', response, fields, is_array=True)


def test_get_sn_token_status(token_first, eventbrite):
    """
    Validate that Graphql endpoint will return token status for given social network id for `snTokenStatus` query.
    In this case, Eventbrite is the social_network and token status should be True.
    """
    fields = ['status']
    query = get_query('snTokenStatus', fields, args=dict(id=eventbrite['id']))
    response = get_graphql_data(query, token_first)
    assert 'errors' not in response, 'Response: %s\nQuery: %s' % (response, query)
    validate_graphql_response('snTokenStatus', response, fields)
    assert response['data']['snTokenStatus']['status'] is True


def assert_valid_response(key, model, token, obj_id, ignore_id_test=False):
    """
    This helper function gets data from SN service Graphql endpoint according to given model and id of the object
    and validates expected fields in response.
    :param string key: root response object key
    :param db.Model model: model class
    :param string token: access token
    :param int obj_id: object id
    :param bool ignore_id_test: True if you want to skip single object test
    """
    fields = get_fields(model)
    query = get_query(key + 's', fields)
    response = get_graphql_data(query, token)
    assert 'errors' not in response, 'Response: %s\nQuery: %s' % (response, query)
    validate_graphql_response(key + 's', response, fields, is_array=True)
    if not ignore_id_test:
        query = get_query(key, fields, args=dict(id=obj_id))
        response = get_graphql_data(query, token)
        assert 'errors' not in response, 'Response: %s\nQuery: %s' % (response, query)
        validate_graphql_response(key, response, fields)
    return response


def match_data(graphql_obj, restful_obj, fields):
    """
    This helper method takes graphql response object and object returned from restful api and matches given fields.
    :param dict graphql_obj: graphql response object
    :param dict restful_obj: object returned from restful api or by using `to_json()` method on model instance
    :param list | tuple fields: list of fields to be matched
    """
    for field in fields:
        assert graphql_obj[field] == restful_obj[camel_case_to_snake_case(field)], \
            'field: %s, GraphqlObj: %s\nRestfulObj: %s' % (field, graphql_obj, restful_obj)
