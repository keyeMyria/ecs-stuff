"""
Resume jobs which are already scheduled and in paused state.
Also try to resume the jobs without using token and it should give 401 status code
"""

# Third party imports
import json
import pytest
import requests

# Application imports
from scheduler_service.custom_exceptions import SchedulerServiceApiException
from scheduler_service.tests.conftest import APP_URL

__author__ = 'saad'


@pytest.mark.usefixtures('auth_header', 'job_config')
class TestSchedulerResume:

    def test_single_resume_job(self, auth_header, job_config):
        """
        Create and pause a job using service endpoints and then after it is paused, resume the job and check its
        next_run_datetime is not None (Running Job has next_run_datetime equal to next running datetime)
        Args:
            auth_data: Fixture that contains token.
            job_config (dict): Fixture that contains job config to be used as
            POST data while hitting the endpoint.
        :return:
        """
        jobs = []

        for i in range(10):
            response = requests.post(APP_URL + '/tasks/', data=json.dumps(job_config),
                                     headers=auth_header)
            assert response.status_code == 201
            jobs.append(response.json()['id'])
        job_id = jobs[0]

        # Send job stop request
        response_stop = requests.post(APP_URL + '/tasks/' + job_id + '/pause/',
                                      headers=auth_header)
        assert response_stop.status_code == 200

        # Paused jobs have their next_run_datetime set to 'None'
        response = requests.get(APP_URL + '/tasks/id/' + job_id, headers=auth_header)
        next_run_datetime = response.json()['task']['next_run_datetime']
        assert next_run_datetime == 'None'

        # Resume job stop request
        response_resume = requests.post(APP_URL + '/tasks/' + job_id + '/resume/',
                                        headers=auth_header)
        assert response_resume.status_code == 200

        # Normal jobs don't have their next_run_datetime set to 'None'
        response = requests.get(APP_URL + '/tasks/id/' + job_id, headers=auth_header)
        next_run_datetime = response.json()['task']['next_run_datetime']
        assert next_run_datetime != 'None'

        # Resume job stop request again - does not affect
        response_resume_again = requests.post(APP_URL + '/tasks/' + job_id + '/resume/',
                                              headers=auth_header)
        assert response_resume_again.status_code == 500 and \
               response_resume_again.json()['error']['code'] == SchedulerServiceApiException.CODE_ALREADY_RUNNING

        # Let's delete jobs now
        response_remove = requests.delete(APP_URL + '/tasks/id/' + job_id,
                                          headers=auth_header)
        assert response_remove.status_code == 200

        # Delete job id which is deleted
        del jobs[:1]

        # Get all jobs except for the one which we just deleted
        for job_id in jobs:
            response_get = requests.get(APP_URL + '/tasks/id/' + job_id,
                                        headers=auth_header)
            assert response_get.json()['task']['id'] == job_id and \
                   response_get.json()['task']['next_run_datetime'] is not None

        # Delete all jobs
        response_remove = requests.delete(APP_URL + '/tasks/', data=json.dumps(dict(ids=jobs)),
                                          headers=auth_header)
        assert response_remove.status_code == 200

    def test_multiple_resume_jobs(self, auth_header, job_config):
        """
        Create and pause 10 job using service endpoints and then after they are paused, resume all jobs and check their
        next_run_datetime which should not be None (Running Job has next_run_datetime equal to next running datetime)
        Args:
            auth_data: Fixture that contains token.
            job_config (dict): Fixture that contains job config to be used as
            POST data while hitting the endpoint.
        :return:
        """
        jobs_id = []

        for i in range(10):
            response = requests.post(APP_URL + '/tasks/', data=json.dumps(job_config),
                                     headers=auth_header)
            assert response.status_code == 201
            jobs_id.append(response.json()['id'])

        # Send job stop request i.e. stop all jobs
        response_stop = requests.post(APP_URL + '/tasks/pause/', data=json.dumps(dict(ids=jobs_id)),
                                      headers=auth_header)
        assert response_stop.status_code == 200

        # Resume all jobs
        response_resume = requests.post(APP_URL + '/tasks/resume/', data=json.dumps(dict(ids=jobs_id)),
                                        headers=auth_header)

        assert response_resume.status_code == 200

        jobs = []
        # Resume jobs have their next_run_datetime set to not 'None'
        for job_id in jobs_id:
            response_get = requests.get(APP_URL + '/tasks/id/' + job_id,
                                        headers=auth_header)
            jobs.append(response_get.json()['task'])

        for res in jobs:
            next_run_datetime = res['next_run_datetime']
            assert next_run_datetime is not 'None'

        # Delete all jobs
        response_remove = requests.delete(APP_URL + '/tasks/', data=json.dumps(dict(ids=jobs_id)),
                                          headers=auth_header)
        assert response_remove.status_code == 200

    def test_single_resume_job_without_token(self, auth_header, job_config):
        """
        Resume job without using bearer token, it should throw 401 status code
        Args:
            auth_data: Fixture that contains token.
            job_config (dict): Fixture that contains job config to be used as
            POST data while hitting the endpoint.
        :return:
        """
        response = requests.post(APP_URL + '/tasks/', data=json.dumps(job_config),
                                 headers=auth_header)

        assert response.status_code == 201
        data = json.loads(response.text)
        assert data['id'] is not None

        # Send job stop request
        response_stop = requests.post(APP_URL + '/tasks/' + data['id'] + '/pause/',
                                      headers=auth_header)
        assert response_stop.status_code == 200

        invalid_header = auth_header.copy()
        # Set the token to invalid
        invalid_header['Authorization'] = 'Bearer invalid_token'

        # Now try resume with invalid token
        response_get = requests.post(APP_URL + '/tasks/' + data['id'] + '/resume/',
                                     headers=invalid_header)

        assert response_get.status_code == 401

        # Let's delete jobs now
        response_remove = requests.delete(APP_URL + '/tasks/id/' + data['id'],
                                          headers=auth_header)
        assert response_remove.status_code == 200

        # There shouldn't be any more jobs now
        response = requests.get(APP_URL + '/tasks/id/' + data['id'], headers=auth_header)
        assert response.status_code == 404

    def test_multiple_resume_jobs_without_token(self, auth_header, job_config):
        """
        Resume multiple jobs using ids as a list of job_ids that were created using service endpoints.
        Then pause them and resume them without using bearer token, it should give 401 status code
        Args:
            auth_data: Fixture that contains token.
            job_config (dict): Fixture that contains job config to be used as
            POST data while hitting the endpoint.
        :return:
        """
        jobs_id = []

        for i in range(10):
            response = requests.post(APP_URL + '/tasks/', data=json.dumps(job_config),
                                     headers=auth_header)
            assert response.status_code == 201
            jobs_id.append(response.json()['id'])

        # Stop all jobs
        response_stop = requests.post(APP_URL + '/tasks/pause/', data=json.dumps(dict(ids=jobs_id)),
                                      headers=auth_header)
        assert response_stop.status_code == 200

        invalid_header = auth_header.copy()
        invalid_header['Authorization'] = 'Bearer invalid_token'

        # Then try to resume all jobs with invalid token
        response_resume = requests.post(APP_URL + '/tasks/resume/', data=json.dumps(dict(ids=jobs_id)),
                                        headers=invalid_header)

        assert response_resume.status_code == 401

        jobs = []
        # Paused jobs have their next_run_datetime set to next time

        # Get all jobs
        for job_id in jobs_id:
            response_get = requests.get(APP_URL + '/tasks/id/' + job_id, data=json.dumps(dict(ids=jobs_id)),
                                        headers=auth_header)
            jobs.append(response_get.json())

        # Paused jobs should have their next run time set to None
        for res in jobs:
            next_run_datetime = res['task']['next_run_datetime']
            assert next_run_datetime == 'None'

        # Delete all jobs
        response_remove = requests.delete(APP_URL + '/tasks/', data=json.dumps(dict(ids=jobs_id)),
                                          headers=auth_header)
        assert response_remove.status_code == 200
