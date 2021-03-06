import pytest

from banner_service.app.modules.v1_banner_processors import (
    create_banner, BANNER_REDIS_KEY, read_banner, delete_banner)
from banner_service.app import app, redis_store


class TestCRDFunction(object):
    def setup_method(self, method):
        with app.test_client() as tc:
            self.app = tc

    def teardown_method(self, method):
        with app.test_client() as tc:
            redis_store.delete(BANNER_REDIS_KEY)

    def test_we_can_create(self):
        with self.app:
            assert create_banner({
                'title': 'Potato',
                'text': 'We have a new potato feature',
                'style': 'chartreuse'
            })

    def test_we_can_read(self):
        # TODO add user id
        REQUIRED_RESPONSE_KEYS = ('title', 'text', 'style', 'timestamp')
        with self.app:
            # Create the entry
            # Redundant assert that we can create when no key is set.
            assert create_banner({
                'title': 'Turnip',
                'text': 'We can now grow turnips for you',
                'style': 'lavender'
            })

            response = read_banner()
            assert all(key in response for key in REQUIRED_RESPONSE_KEYS)

    def test_we_can_delete(self):
        with self.app:
            # Create the entry
            # Redundant assert that we can create when no key is set.
            assert create_banner({
                'title': 'Turnip',
                'text': 'We can now grow turnips for you',
                'style': 'lavender'
            })

            assert delete_banner()
