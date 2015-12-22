"""
Test cases for creating schedule job with and without token.
"""

# Third party imports
import json
import pytest
import requests

# Application imports
from scheduler_service.scheduler import scheduler
from scheduler_service.tests.conftest import APP_URL, hmac, APP

__author__ = 'saad'


@pytest.mark.usefixtures('auth_header', 'job_config', 'general_task_header')
class TestSchedulerCreate:

    def test_single_schedule_general_job(self, general_task_header):
        """
        Create a job by hitting the endpoint but by using valid HMAC signature and make sure response
        is correct and job id is returned.
        Args:
            auth_data: Fixture that contains token.
            job_config (dict): Fixture that contains job config to be used as
            POST data while hitting the endpoint.
        :return:
        """
        data, header = general_task_header
        response = requests.post(APP_URL + '/schedule/', data=data,
                                 headers=header)
        assert response.status_code == 201
        data = json.loads(response.text)
        assert data is not None

        scheduler.remove_job(job_id=data)

    def test_single_schedule_job(self, auth_header, job_config):
        """
        Create a job by hitting the endpoint and make sure response
        is correct.
        Args:
            auth_data: Fixture that contains token.
            job_config (dict): Fixture that contains job config to be used as
            POST data while hitting the endpoint.
        :return:
        """
        response = requests.post(APP_URL + '/tasks/', data=json.dumps(job_config),
                                 headers=auth_header)
        assert response.status_code == 201
        data = response.json()
        assert data['id'] is not None

        # Let's delete jobs now
        response_remove = requests.delete(APP_URL + '/tasks/id/' + data['id'],
                                          headers=auth_header)
        assert response_remove.status_code == 200

    def test_multiple_schedule_job(self, auth_header, job_config):
        """
        Create multiple jobs. Then schedule jobs and finally remove all jobs.
         Args:
            auth_data: Fixture that contains token.
            job_config (dict): Fixture that contains job config to be used as
            POST data while hitting the endpoint.
        :return:
        """
        jobs = []

        # schedule some jobs and remove all of them
        for i in range(10):
            response = requests.post(APP_URL + '/tasks/', data=json.dumps(job_config),
                                     headers=auth_header)
            assert response.status_code == 201
            jobs.append(json.loads(response.text)['id'])

        response_remove_jobs = requests.delete(APP_URL + '/tasks/',
                                               data=json.dumps(dict(ids=jobs)),
                                               headers=auth_header)

        assert response_remove_jobs.status_code == 200

    def test_single_schedule_job_without_token(self, job_config):
        """
        Create a job without a token, it shouldn't be created and we should get a
        401 when endpoint hit
        Args:
            job_config (dict): Fixture that contains job config to be used as
            POST data while hitting the endpoint.
        :return:
        """
        invalid_header = {'Authorization': 'Bearer invalid_token',
                          'Content-Type': 'application/json'}

        response = requests.post(APP_URL + '/tasks/', data=json.dumps(job_config),
                                 headers=invalid_header)
        assert response.status_code == 401
