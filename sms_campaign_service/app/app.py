"""
    This module contains flask app startup.
    We register blueprints for different APIs with this app.
    Error handlers are added at the end of file.
"""
# Standard  Library imports
import json
import traceback
from datetime import datetime

# Initializing App. This line should come before any imports from models
from sms_campaign_service import init_app
app = init_app()

# create celery object
from sms_campaign_service.celery_config import make_celery
celery = make_celery(app)

# Run Celery from terminal as
# celery -A sms_campaign_service.app.app.celery worker

# start the scheduler
from sms_campaign_service.gt_scheduler import GTScheduler
from apscheduler.events import EVENT_JOB_ERROR
from apscheduler.events import EVENT_JOB_EXECUTED
from apscheduler.jobstores.redis_store import RedisJobStore

sched = GTScheduler()
sched.add_jobstore(RedisJobStore(), 'redisJobStore')

from sms_campaign_service.utilities import working_environment
IS_DEV = working_environment()

# from apscheduler.jobstores.shelve_store import ShelveJobStore
# from apscheduler.scheduler import Scheduler
# from common.utils.apscheduler.jobstores.redis_store import RedisJobStore
# from common.utils.apscheduler.scheduler import Scheduler
# config = {'apscheduler.jobstores.file.class': 'apscheduler.jobstores.shelve_store:ShelveJobStore',
#           'apscheduler.jobstores.file.path': '/tmp/dbfile'}
# sched = Scheduler(config)
# sched.add_jobstore(ShelveJobStore('/tmp/dbfile'), 'file')
# jobstore = RedisJobStore(jobs_key='example.jobs', run_times_key='example.run_times')
# sched.add_jobstore(jobstore)


# def my_listener(event):
#     if event.exception:
#         print('The job crashed :(\n')
#         print str(event.exception.message) + '\n'
#     else:
#         print('The job worked :)')
#
# sched.add_listener(my_listener, EVENT_JOB_EXECUTED | EVENT_JOB_ERROR)
# sched.start()

# Third party imports
import json
import flask
import twilio.twiml
from flask import request
from flask import render_template
from flask.ext.cors import CORS
from flask.ext.restful import Api
from werkzeug.utils import redirect

# Application specific imports
from restful.sms_campaign import sms_campaign_blueprint
from sms_campaign_service import logger
from sms_campaign_service.utilities import run_func, run_func_1, get_all_tasks
from social_network_service.utilities import http_request
from sms_campaign_service.utilities import url_conversion
from sms_campaign_service.utilities import send_sms_campaign
from sms_campaign_service.utilities import get_smart_list_ids
from sms_campaign_service.sms_campaign_base import SmsCampaignBase
from sms_campaign_service.app.app_utils import ApiResponse
from sms_campaign_service.custom_exceptions import ApiException
from sms_campaign_service.common.error_handling import InternalServerError

# Register Blueprints for different APIs
app.register_blueprint(sms_campaign_blueprint)
api = Api(app)

# Enable CORS
CORS(app, resources={
    r'/*': {
        'origins': '*',
        'allow_headers': ['Content-Type', 'Authorization']
    }
})


@app.route('/')
def hello_world():
    return 'Welcome to SMS Campaign Service'


@app.route('/sms_campaign/', methods=['POST'])
def sms_campaign_create():
    try:
        camp_obj = SmsCampaignBase(user_id=int(request.form['user_id']))
        campaign_id = camp_obj.save(request.form)
        logger.debug('Campaign(id:%s) has been saved.' % campaign_id)
        return 'Campaign(id:%s) has been saved.' % campaign_id
    except:
        logger.exception("Error occurred while saving SMS campaign.")
    return ''


@app.route('/sms_campaign/<int:campaign_id>/send/', methods=['POST'])
def sms_campaign_send(campaign_id=None):
    try:
        user_id = request.args.get('user_id')
        assert user_id and campaign_id
        camp_obj = SmsCampaignBase(user_id=user_id)
        total_sends = camp_obj.process_send(campaign_id=campaign_id)
        return 'Campaign(id:%s) has been sent to %s candidate(s).' % (campaign_id, total_sends)
    except:
        logger.exception("Error occurred while sending SMS campaign.")
    return ''


@app.route('/sms_campaign/<int:campaign_id>/url_redirection/', methods=['GET'])
def sms_campaign_url_redirection(campaign_id=None):
    try:
        user_id = request.args.get('user_id')
        url_conversion_id = request.args.get('url_conversion_id')
        assert user_id and campaign_id and url_conversion_id

        camp_obj = SmsCampaignBase(user_id=user_id)
        redirection_url = camp_obj.process_url_redirect(campaign_id=campaign_id,
                                                        url_conversion_id=url_conversion_id)
        if redirection_url:
            return redirect(redirection_url)
        else:
            return "Couldn't find redirection URL"
    except:
        logger.exception("Error occurred while URL redirection for SMS campaign.")


@app.route('/url_conversion/', methods=['GET'])
def short_url_test():
    """
    This is a test end point which converts given URL to short URL
    :return:
    """
    url = request.args.get('url')
    if url:
        short_url, long_url = url_conversion(url)
        data = {'short_url': short_url,
                'status_code': 200}
    else:
        data = {'message': 'No URL given in request',
                'status_code': 200}
    return flask.jsonify(**data), 200


@app.route('/tasks')
def tasks():
    data = get_all_tasks()
    return render_template('tasks.html', tasks=data)


@app.route('/sms', methods=['GET', 'POST'])
def sms():
    """
    This is a test end point which sends sms campaign
    :return:
    """
    # if request.args.has_key('text'):
    #     body_text = request.args['text']
    #     body_text = process_link_in_body_text(body_text)
    # else:
    #     body_text = 'Welcome to getTalent'
    # ids = get_smart_list_ids()
    start_min = request.args.get('start')
    end_min = request.args.get('end')
    start_date = datetime(2015, 11, 13, 17, int(start_min), 50)
    end_date = datetime(2015, 11, 13, 17, int(end_min), 36)
    repeat_time_in_sec = int(request.args.get('frequency'))
    func = request.args.get('func')
    arg1 = request.args.get('arg1')
    arg2 = request.args.get('arg2')
    # for x in range (1,50):
    job = sched.add_interval_job(run_func_1,
                                 seconds=repeat_time_in_sec,
                                 start_date=start_date,
                                 args=[func, [arg1, arg2], end_date],
                                 jobstore='redisJobStore')
    print 'Task has been added and will run at %s ' % start_date
    return 'Task has been added to queue!!!'
    # response = send_sms_campaign(ids, body_text)
    if response:
        return flask.jsonify(**response), response['status_code']
    else:
        raise InternalServerError


@app.route("/sms_receive", methods=['GET', 'POST'])
def sms_receive():
    """
    This is a test end point to receive sms
    :return:
    """
    if request.values:
        response = 'SMS received from %(From)s on %(To)s.\n' \
                   'Body text is "%(Body)s"' \
                   % request.values
        print response
    return """
        <?xml version="1.0" encoding="UTF-8"?>
            <Response>
            </Response>
            """

# resp = twilio.twiml.Response()
# resp.message("Thank you for your response")
# return str(resp)
# <Message> Hello </Message>


@app.errorhandler(ApiException)
def handle_api_exception(error):
    """
    This handler handles ApiException error
    :param error: exception object containing error info
    :type error:  ApiException
    :return: json response
    """
    logger.debug('Error: %s\nTraceback: %s' % (error, traceback.format_exc()))
    response = json.dumps(error.to_dict())
    return ApiResponse(response, status=error.status_code)


@app.errorhandler(Exception)
def handle_any_errors(error):
    """
    This handler handles any kind of error in app.
    :param error: exception object containing error info
    :type error:  Exception
    :return: json response
    """
    logger.debug('Error: %s\nTraceback: %s' % (error, traceback.format_exc()))
    response = json.dumps(dict(message='Ooops! Internal server error occurred..' + str(error.message)))
    return ApiResponse(response, status=500)

