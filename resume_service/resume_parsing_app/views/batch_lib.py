"""Functions used by batch processing endpoints."""
__author__ = 'erik@getTalent'
# Standard Library
from datetime import datetime
from datetime import timedelta
import json
# Framework specific
from flask import jsonify
# Module Specific
from resume_service.common.redis_conn import redis_client
from resume_service.common.models.user import Token
from resume_service.resume_parsing_app.views.parse_lib import process_resume
from resume_service.common.utils.handy_functions import grouper
from resume_service.common.routes import ResumeApiUrl, SchedulerApiUrl
import requests

DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def add_fp_keys_to_queue(filepicker_keys, user_id, token):
    """
    Adds filename to redis list. The redis key is formed using the user_id.
    :param list filepicker_keys:
    :param str user_id:
    :return str:
    """
    queue_string = 'batch:{}:fp_keys'.format(user_id)
    list_length = redis_client.rpush(queue_string, *filepicker_keys)
    batches = grouper(filepicker_keys, 100)
    scheduled = datetime.now() + timedelta(seconds=15)
    for batch in batches:
        for key in batch:
            payload = json.dumps({
                "task_type": "one_time",
                "run_datetime": scheduled.strftime(DATE_FORMAT),
                "url": "{}/{}".format(ResumeApiUrl.BATCH_URL, user_id),
            })
            # TODO Handle missed connections/http errors.
            scheduler_request = requests.post(SchedulerApiUrl.TASKS, data=payload,
                                              headers={'Authorization': 'bearer {}'.format(token),
                                                       'Content-Type': 'application/json'})
        scheduled += timedelta(seconds=20)

    return {'redis_key': queue_string, 'quantity': list_length}


def _process_batch_item(user_id, create_candidate=True):
    """
    Endpoint for scheduler service to parse resumes update status data.
    :param int user_id: Id of the user who scheduled the batch process.
    :param bool create_candidate: Boolean for desire to create a candidate.
    :return: json dict in candidate object format.
    """
    queue_string = 'batch:{}:fp_keys'.format(user_id)
    fp_key = redis_client.lpop(queue_string)
    # LPOP returns none if the list is empty so we should end our current batch.
    if fp_key is None:
        return jsonify(**{'error': {'message': 'Empty Queue for user: {}'.format(user_id)}})
    # Adding none here allows for unit-testing and will still result in unauthorized responses
    # given a user does not have a Token.
    oauth_token = Token.query.filter_by(user_id=user_id).first() or None
    parse_params = {
        'filepicker_key': fp_key,
        'create_candidate': create_candidate,
        'oauth': oauth_token
    }
    return process_resume(parse_params)
