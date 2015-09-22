import json
import datetime
import requests
from common.gt_models.event import Event

API_URL = 'http://127.0.0.1:5000'
GET_TOKEN = 'http://127.0.0.1:8888/oauth2/token'


class TestResourceEvents:

    def test_get_with_invalid_token(self):
        response = requests.get(API_URL + '/events/', headers=dict(Authorization='Bearer %s' % 'invalid_token'))
        assert response.status_code == 401, 'It should be unauthorized (401)'
        assert 'events' not in response.json()

    def test_get_with_valid_token(self, auth_data):
        response = requests.get(API_URL + '/events/', headers=dict(Authorization='Bearer %s' % auth_data['access_token']))
        assert response.status_code == 200, 'Status should be Ok (200)'
        events = response.json()['events']
        assert len(events) > 0, 'There should be no events for test user'

    def test_post_with_invalid_token(self):
        response = requests.post(API_URL + '/events/', data=dict(a='a', b='b'),  headers=dict(Authorization='Bearer %s' % 'invalid_token'))
        assert response.status_code == 401, 'It should be unauthorized (401)'
        assert 'events' not in response.json()

    def test_post_with_valid_token(self, auth_data, test_event):
        event_data = test_event
        response = requests.post(API_URL + '/events/', data=json.dumps(event_data),
                                 headers={'Authorization': 'Bearer %s' % auth_data['access_token'],
                                          'Content-Type': 'application/json'})
        assert response.status_code == 201, 'Status should be Ok, Resource Created (201)'
        event_id = response.json()['id']
        assert event_id > 0, 'Event id should be a positive number'

    def test_eventbrite_with_missing_required_fields(self, auth_data, eventbrite_missing_data):
        key, event_data = eventbrite_missing_data
        event_data[key] = ''
        response = requests.post(API_URL + '/events/', data=json.dumps(event_data),
                                 headers={'Authorization': 'Bearer %s' % auth_data['access_token'],
                                          'Content-Type': 'application/json'})
        assert response.status_code == 453, 'There should be an missing field error for %s KeyError' % key

    def test_meetup_with_missing_required_fields(self, auth_data, meetup_missing_data):
        key, event_data = meetup_missing_data
        event_data[key] = ''
        response = requests.post(API_URL + '/events/', data=json.dumps(event_data),
                                 headers={'Authorization': 'Bearer %s' % auth_data['access_token'],
                                          'Content-Type': 'application/json'})
        assert response.status_code == 453, 'There should be an missing field error for %s KeyError' % key

    def test_meetup_with_valid_address(self, auth_data, meetup_event_data):
        event_data = meetup_event_data
        response = requests.post(API_URL + '/events/', data=json.dumps(event_data),
                                 headers={'Authorization': 'Bearer %s' % auth_data['access_token'],
                                          'Content-Type': 'application/json'})
        assert response.status_code == 201, 'Event should be created, address is valid'

    def test_meetup_with_invalid_address(self, auth_data, meetup_event_data):
        event_data = meetup_event_data
        event_data['eventAddressLine1'] = 'Invalid address'
        event_data['eventCity'] = 'City that does not exists'
        response = requests.post(API_URL + '/events/', data=json.dumps(event_data),
                                 headers={'Authorization': 'Bearer %s' % auth_data['access_token'],
                                          'Content-Type': 'application/json'})
        assert response.status_code == 458, 'Event should not be created, address is invalid'


class TestEventById:

    def test_get_with_invalid_token(self):
        response = requests.post(API_URL + '/events/1', headers=dict(Authorization='Bearer %s' % 'invalid_token'))
        assert response.status_code == 401, 'It should be unauthorized (401)'
        assert 'event' not in response.json()

    def test_get_with_valid_token(self, auth_data, event_in_db):
        event = event_in_db
        response = requests.get(API_URL + '/events/' + str(event.id), headers=dict(Authorization='Bearer %s' % auth_data['access_token']))
        assert response.status_code == 200, 'Status should be Ok (200)'
        results = response.json()
        assert 'event' in results
        api_event = results['event']
        event = event.to_json()
        comparison = '\n{0: <20}  |  {1: <40} |  {2: <40}\n'.format('Key', 'Expected', 'Found')
        comparison += '=' * 100 + '\n'
        status = True
        for key, val in event.items():
            mismatch = ''
            if event[key] == api_event[key]:
                mismatch = '**'
            comparison += '{0: <20}  {1}|  {2: <40} |  {3: <40}\n'.format(key, mismatch, event[key], api_event[key])
            comparison += '-' * 100 + '\n'
            status = status and event[key] == api_event[key]

        assert status == True, 'Event values were not matched\n' + comparison

    def test_post_with_invalid_token(self):
        response = requests.post(API_URL + '/events/1', headers=dict(Authorization='Bearer %s' % 'invalid_token'))
        assert response.status_code == 401, 'It should be unauthorized (401)'

    def test_post_with_valid_token(self, auth_data, event_in_db):
        event = event_in_db.to_json()
        datetime_now = datetime.datetime.now()
        event['eventTitle'] = 'Test update event'
        event['eventStartDatetime'] = str(datetime_now + datetime.timedelta(days=50))
        event['eventEndDatetime'] = str(datetime_now + datetime.timedelta(days=60))
        response = requests.post(API_URL + '/events/' + str(event['id']), data=json.dumps(event),
                                 headers={'Authorization': 'Bearer %s' % auth_data['access_token'],
                                          'Content-Type': 'application/json'})
        assert response.status_code == 204, 'Status should be Ok, Resource Modified (204)'
        event_db = Event.get_by_id(event['id']).to_json()
        assert event['eventTitle'] == event_db['eventTitle'], 'eventTitle is modified'
        assert event['eventStartDatetime'] == event_db['eventStartDatetime'], 'eventStartDatetime is modified'
        assert event['eventEndDatetime'] == event_db['eventEndDatetime'], 'eventEndDatetime is modified'

    def test_delete_with_invalid_token(self, event_in_db):
        response = requests.delete(API_URL + '/events/' + str(event_in_db.id), headers=dict(Authorization='Bearer %s' % 'invalid_token'))
        assert response.status_code == 401, 'It should be unauthorized (401)'

    def test_delete_with_valid_token(self, auth_data, event_in_db):
        response = requests.delete(API_URL + '/events/' + str(event_in_db.id), headers=dict(Authorization='Bearer %s' % auth_data['access_token']))
        assert response.status_code == 200, 'Status should be Ok (200)'
