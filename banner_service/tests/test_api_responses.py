import pytest
import json

from banner_service.app import app, redis_store
from banner_service.app.modules.v1_api_processors import BANNER_REDIS_KEY

REQUIRED_RESPONSE_KEYS = ('title', 'text', 'link', 'color', 'timestamp')


class TestApiEndpoints(object):
    def setup_method(self, method):
        with app.test_client() as tc:
            self.app = tc

    def teardown_method(self, method):
        with app.test_client() as tc:
            redis_store.delete(BANNER_REDIS_KEY)

    def test_create_response(self):
        """
        Tests that we can create a banner via the endpoint.
        """
        sample_banner = {
            'title': 'Rutabaga',
            'text': 'Rutabaga beta feature available to test now!',
            'link': 'www.getTalent.com',
            'color': 'vermillion'
        }

        response = self.app.post(
            '/v1/banners',
            data=json.dumps(sample_banner),
            headers={'Content-Type': 'application/json'})

        response_json = json.loads(response.data)
        assert response_json.get('banner_created')

    def test_cannot_create_when_exists(self):
        """
        Tests presence of error response if a banner is already in redis.
        """
        sample_banner = {
            'title': 'Rutabaga',
            'text': 'Rutabaga beta feature available to test now!',
            'link': 'www.getTalent.com',
            'color': 'vermillion'
        }

        response = self.app.post(
            '/v1/banners',
            data=json.dumps(sample_banner),
            headers={'Content-Type': 'application/json'})

        response_json = json.loads(response.data)
        assert response_json.get('banner_created')

        second_banner = {
            'title': 'Onions',
            'text': 'Onions: not just for making you cry now!',
            'link': 'www.whySoSerious.com',
            'color': 'rose'
        }

        response = self.app.post(
            '/v1/banners',
            data=json.dumps(second_banner),
            headers={'Content-Type': 'application/json'})

        response_json = json.loads(response.data)
        assert response_json.get('error', {}).get(
            'message') == 'Cannot POST banner when an active banner exists'

    def test_get_endpoint_with_no_data(self):
        """
        Tests that get will return error when no banner stored in redis.
        """
        response = self.app.get('/v1/banners')
        response_json = json.loads(response.data)
        assert response_json.get(
            'error', {}).get('message') == 'No banner currently set.'

    def test_can_read_created(self):
        """
        Tests that the expected keys exist in the GET response after creating a banner.
        """
        sample_banner = {
            'title': 'Rutabaga',
            'text': 'Rutabaga beta feature available to test now!',
            'link': 'www.getTalent.com',
            'color': 'vermillion'
        }

        post_response = self.app.post(
            '/v1/banners',
            data=json.dumps(sample_banner),
            headers={'Content-Type': 'application/json'})

        response_json = json.loads(post_response.data)
        assert response_json.get('banner_created')

        get_response = self.app.get('/v1/banners')
        response_json = json.loads(get_response.data)

        assert all(key in response_json for key in REQUIRED_RESPONSE_KEYS)

    def test_can_delete_banner(self):
        sample_banner = {
            'title': 'Rutabaga',
            'text': 'Rutabaga beta feature available to test now!',
            'link': 'www.getTalent.com',
            'color': 'vermillion'
        }

        post_response = self.app.post(
            '/v1/banners',
            data=json.dumps(sample_banner),
            headers={'Content-Type': 'application/json'})

        response_json = json.loads(post_response.data)
        assert response_json.get('banner_created')

        delete_response = self.app.delete('/v1/banners')
        response_json = json.loads(delete_response.data)
        assert response_json.get('banner_delete')

        get_response = self.app.get('/v1/banners')
        response_json = json.loads(get_response.data)
        assert response_json.get(
            'error', {}).get('message') == 'No banner currently set.'
