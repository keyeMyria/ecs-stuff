"""
Celery tasks are defined here. It will be a separate celery process.
These methods are called by run_job method asynchronously

- Running celery using commandline (scheduler_service directory) =>

    celery -A scheduler_service.run.celery  worker --concurrency=4 --loglevel=info

- Running celery flower using commandline (scheduler_service directory) =>

    celery flower -A scheduler_service.run.celery

For Scheduler Service, celery flower is =>

    localhost:5511

"""
# Application imports
import json

from scheduler_service.common.utils.handy_functions import http_request
from scheduler_service import celery_app as celery, flask_app as app, TalentConfigKeys


@celery.task(name="send_request")
def send_request(access_token, secret_key_id, url, content_type, post_data):
    """
    This method will be called by run_job asynchronously
    :param access_token: authorization token for user
    :param url: the URL where to send post request
    :param content_type: the content type i.e json or xml
    :param secret_key_id: Redis key which have a corresponding secret value to decrypt data
    :param kwargs: post data i.e campaign name, smartlist ids
    :return:
    """
    with app.app_context():
        logger = app.config[TalentConfigKeys.LOGGER]
        logger.info("Celery running....")
        headers = {
            'Content-Type': content_type,
            'Authorization': access_token
        }
        if content_type == 'application/json':
            post_data = json.dumps(post_data)
        if secret_key_id:
            headers.update({'X-Talent-Secret-Key-ID': secret_key_id})
        # Send request to URL with job post data
        logger.info("Sending post request to %s" % url)
        response = http_request(method_type='POST', url=url, data=post_data, headers=headers)

        try:
            return response.text
        except Exception as e:
            # This exception will be caught by flower
            return {'message': e.message, 'status_code': response.status_code}