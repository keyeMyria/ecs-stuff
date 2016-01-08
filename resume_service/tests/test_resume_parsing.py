"""Test suite for Flask Resume Parsing MicroService."""
__author__ = 'erik@getTalent.com'
# Standard library
import json
import os
# Third party
import requests as r
# Module Specific.
from resume_service.common.redis_conn import redis_client
from resume_service.resume_parsing_app.views.batch_lib import add_fp_keys_to_queue
# Test fixtures, imports required even though not 'used'
# TODO: Look into importing these once and use via namespacing.
from resume_service.tests.test_fixtures import client_fixture
from resume_service.tests.test_fixtures import country_fixture
from resume_service.tests.test_fixtures import culture_fixture
from resume_service.tests.test_fixtures import domain_fixture
from resume_service.tests.test_fixtures import email_label_fixture
from resume_service.tests.test_fixtures import org_fixture
from resume_service.tests.test_fixtures import token_fixture
from resume_service.tests.test_fixtures import user_fixture
from resume_service.tests.test_fixtures import phone_label_fixture
from resume_service.tests.test_fixtures import product_fixture

APP_URL = 'http://0.0.0.0:8003/v1'
API_URL = APP_URL + '/parse_resume'
BATCH_URL = APP_URL + '/batch'


def test_base_url():
    """Test that the application root lists the endpoint."""
    base_response = r.get(APP_URL)
    assert '/parse_resume' in base_response.content


def test_doc_from_fp_key(token_fixture):
    """Test that .doc files from S3 can be parsed."""
    response = fetch_resume_fp_key_response(token_fixture, '0169173d35beaf1053e79fdf1b5db864.docx')
    assert 'candidate' in response



def test_doc_by_post(token_fixture):
    """Test that .doc files that are posted to the end point can be parsed."""
    response = fetch_resume_post_response(token_fixture, 'test_bin.docx')
    # doc_db_record = db.session.query(Candidate).filter_by(formatted_name='Veena Nithoo').first()
    # assert not doc_db_record
    assert 'candidate' in response


def test_v15_pdf_from_fp_key(token_fixture):
    """Test that v1.5 pdf files from S3 can be parsed."""
    response = fetch_resume_fp_key_response(token_fixture, 'e68b51ee1fd62db589d2669c4f63f381.pdf')
    assert 'candidate' in response


def test_v14_pdf_from_fp_key(token_fixture):
    """Test that v1.4 pdf files from S3 can be parsed."""
    response = fetch_resume_fp_key_response(token_fixture, 'test_bin_14.pdf')
    assert 'candidate' in response


def test_v13_pdf_from_fp_key(token_fixture):
    """Test that v1.3 pdf files from S3 can be parsed."""
    response = fetch_resume_fp_key_response(token_fixture, 'test_bin_13.pdf')
    assert 'candidate' in response


def test_v14_pdf_by_post(token_fixture):
    """Test that v1.4 pdf files can be posted."""
    response = fetch_resume_post_response(token_fixture, 'test_bin_14.pdf')
    assert 'candidate' in response


def test_v13_pdf_by_post(token_fixture):
    """Test that v1.5 pdf files can be posted."""
    response = fetch_resume_post_response(token_fixture, 'test_bin_13.pdf')
    assert 'candidate' in response


def test_jpg_from_fp_key(token_fixture):
    """Test that jpg files from S3 can be parsed."""
    response = fetch_resume_fp_key_response(token_fixture, 'test_bin.jpg')
    assert 'candidate' in response


def test_jpg_by_post(token_fixture):
    """Test that jpg files can be posted."""
    response = fetch_resume_post_response(token_fixture, 'test_bin.jpg')
    assert 'candidate' in response


def test_2448_3264_jpg_by_post(token_fixture):
    """Test that large jpgs files can be posted."""
    response = fetch_resume_post_response(token_fixture, '2448_3264.jpg')
    assert 'candidate' in response


def test_no_token_fails():
    """Test that tokens are required."""
    filepicker_key = '0169173d35beaf1053e79fdf1b5db864.docx'
    test_response = r.post(API_URL, data=dict(filepicker_key=filepicker_key))
    json_obj = json.loads(test_response.content)
    assert 'error' in json_obj


def test_invalid_token_fails():
    """Test that VALID tokens are required."""
    filepicker_key = '0169173d35beaf1053e79fdf1b5db864.docx'
    test_response = r.post(API_URL,
                           headers={'Authorization': 'Bearer %s' % 'invalidtokenzzzz'},
                           data=dict(filepicker_key=filepicker_key))
    json_obj = json.loads(test_response.content)
    assert 'error' in json_obj


def test_v15_pdf_by_post(token_fixture):
    """Test that v1.5 pdf files can be posted."""
    response = fetch_resume_post_response(token_fixture, 'test_bin.pdf', create_mode='True')
    assert 'candidate' in response
    assert 'id' in response['candidate']


def test_batch_processing(user_fixture, token_fixture):
    # create a single file queue
    user_id = user_fixture.id
    queue_string = 'batch:{}:fp_keys'.format(user_id)
    unused_queue_status = add_fp_keys_to_queue(['e68b51ee1fd62db589d2669c4f63f381.pdf'], user_id)
    redis_client.expire(queue_string, 10)
    # mock hit from scheduler service.
    response = r.get(BATCH_URL + '/{}'.format(user_id),
                     headers={'Authorization': 'Bearer %s' % token_fixture.access_token})
    assert 'candidate' in response.content


def test_health_check():
    """HealthCheck/PingDom test endpoint."""
    response = r.get('http://127.0.0.1:8003/healthcheck')
    assert response.status_code == 200


def fetch_resume_post_response(token_fixture, file_name, create_mode=''):
    """Posts file to local test auth server for json formatted resumes."""
    current_dir = os.path.dirname(__file__)
    with open(os.path.join(current_dir, 'test_resumes/{}'.format(file_name)), 'rb') as resume_file:
        response = r.post(API_URL,
                          headers={'Authorization': 'Bearer %s' % token_fixture.access_token},
                          data=dict(
                              resume_file_name=file_name,
                              create_candidate=create_mode,
                          ),
                          files=dict(resume_file=resume_file),
                         )
    return json.loads(response.content)


def fetch_resume_fp_key_response(token_fixture, fp_key):
    """Posts FilePicker key to local test auth server for json formatted resumes."""
    test_response = r.post(API_URL,
                           headers={'Authorization': 'Bearer %s' % token_fixture.access_token},
                           data=dict(filepicker_key=fp_key))
    return json.loads(test_response.content)
