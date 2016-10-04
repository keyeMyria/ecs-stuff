"""
This module contains talentbot service's endpoints to receive webhook calls from
Facebook, Email, SMS and Slack
"""
# Builtin imports
from multiprocessing import Process
# Common utils
from talentbot_service.common.talent_config_manager import TalentConfigKeys
from talentbot_service.common.models.user import TalentbotAuth
from talentbot_service.common.routes import TalentBotApiUrl
from talentbot_service.common.utils.handy_functions import send_request
# Service specific
from talentbot_service.modules.email_bot import EmailBot
from talentbot_service.modules.facebook_bot import FacebookBot
from talentbot_service.modules.slack_bot import SlackBot
from talentbot_service.modules.sms_bot import SmsBot
from talentbot_service.modules.process_scheduler import ProcessScheduler
from constants import TWILIO_NUMBER, ERROR_MESSAGE, STANDARD_MSG_LENGTH, QUESTIONS, BOT_NAME, \
    MAILGUN_SENDING_ENDPOINT, BOT_IMAGE, TWILIO_AUTH_TOKEN, TWILIO_ACCOUNT_SID
from talentbot_service import app, logger
# 3rd party imports
from flask import request
import json
from urllib import quote

mailgun_api_key = app.config[TalentConfigKeys.MAILGUN_API_KEY]
slack_bot = SlackBot(QUESTIONS, BOT_NAME, ERROR_MESSAGE)
sms_bot = SmsBot(bot_name=BOT_NAME, error_messages=ERROR_MESSAGE,
                 standard_sms_length=STANDARD_MSG_LENGTH, twilio_account_sid=TWILIO_ACCOUNT_SID,
                 twilio_auth_token=TWILIO_AUTH_TOKEN, twilio_number=TWILIO_NUMBER, questions=QUESTIONS)
email_bot = EmailBot(mailgun_api_key, MAILGUN_SENDING_ENDPOINT, QUESTIONS, BOT_NAME, BOT_IMAGE,
                     ERROR_MESSAGE)
facebook_bot = FacebookBot(QUESTIONS, BOT_NAME, ERROR_MESSAGE)


@app.route(TalentBotApiUrl.INDEX)
def index():
    """
    Just returns Add to Slack button for testing purpose
    :rtype: str
    """
    return '''<a href="https://slack.com/oauth/authorize?scope=bot+users%3Aread+users%3Awrite+chat%3Awrite%3Abot&client_id=19996241921.72874812897">
           <img alt="Add to Slack" height="40" width="139" src="https://platform.slack-edge.com/img
           '/add_to_slack.png" srcset="https://platform.slack-edge.com/img/add_to_slack.png 1x, https:
           //platform.slack-edge.com/img/add_to_slack@2x.png 2x" /></a>'''


@app.route(TalentBotApiUrl.SLACK_LISTEN, methods=['POST'])
def listen_slack():
    """
    Listens to the slack web hook
    :rtype: str
    """
    event = request.json.get('event')
    if event:
        current_timestamp = event.get('ts')
        channel_id = request.json.get('event').get('channel')
        slack_user_id = request.json.get('event').get('user')
        '''if slack_bot.timestamp:
            if current_timestamp == slack_bot.timestamp and channel_id == slack_bot.recent_channel_id\
                    and slack_user_id == slack_bot.recent_user_id:
                logger.info("Same callback again, response wasn't in 3 seconds")
                return "OK" '''
        message = request.json.get('event').get('text')
        if message and channel_id and slack_user_id:
            logger.info("Message slack:%s, Current_timestamp: %s, Previous timestamp: %s"
                        % (message, current_timestamp, slack_bot.timestamp))
            parent_process = Process(target=ProcessScheduler.schedule_slack_process,
                                     args=(slack_bot, channel_id, message, slack_user_id, current_timestamp))
            parent_process.start()
            return 'HTTP_200_OK'
    challenge = request.json.get('challenge')
    if challenge:
        return quote(challenge)
    return 'HTTP_200_OK'


@app.route(TalentBotApiUrl.SMS_LISTEN, methods=['GET', 'POST'])
def handle_twilio_webhook():
    """
    Listens to the twilio callbacks
    :rtype: str
    """
    recipient = request.form.get('From')
    message_body = request.form.get('Body')
    if recipient and message_body:
        sms_bot.handle_communication(message_body, recipient)
    return 'HTTP_200_OK'


@app.route(TalentBotApiUrl.EMAIL_LISTEN, methods=['POST'])
def receive_mail():
    """
    End point which listens mail gun callbacks
    :rtype: str
    """
    message = request.form.get('stripped-text')
    sender = request.form.get('sender')
    subject = request.form.get('subject')
    if message and sender:
        logger.info('Received email body: ' + message + ', Sender: ' + sender)
        email_bot.handle_communication(sender, subject, message)
    return 'HTTP_200_OK'


@app.route(TalentBotApiUrl.FACEBOOK_LISTEN, methods=['GET'])
def handle_verification():
    """
    End point which handles facebook challenge code
    :rtype: str
    """
    challenge = request.args['hub.challenge']
    return quote(challenge)


@app.route(TalentBotApiUrl.FACEBOOK_LISTEN, methods=['POST'])
def handle_incoming_messages():
    """
    End point to listen facebook web hooks
    :rtype: str
    """
    data = request.json
    sender = data['entry'][0]['messaging'][0]['sender']['id']
    msg = data['entry'][0]['messaging'][0].get('message')
    if msg and sender:
        message = data['entry'][0]['messaging'][0]['message']['text']
        parent_process = Process(target=ProcessScheduler.schedule_fb_process,
                                 args=(sender, message, facebook_bot))
        parent_process.start()
    return 'HTTP_200_OK'


@app.route(TalentBotApiUrl.SLACK_AUTH, methods=['GET', 'POST'])
def get_new_user_credentials():
    """
    Receives user data when he installs talentbot on slack and saves in db
    :rtype str
    """
    code = request.args.get('code')
    client_id = app.config['SLACK_APP_CLIENT_ID']
    client_secret = app.config['SLACK_APP_CLIENT_SECRET']
    response = send_request('POST', 'https://slack.com/api/oauth.access', access_token=None,
                            params={'client_id': client_id, 'client_secret': client_secret, 'code': code})
    json_result = json.loads(response.content)
    if json_result.get('ok'):
        access_token = json_result['access_token']
        team_id = json_result['team_id']
        team_name = json_result['team_name']
        user_id = json_result['user_id']
        auth_entry = TalentbotAuth.query.filter_by(slack_user_id=user_id).first()
        bot_id = json_result['bot']['bot_user_id']
        bot_token = json_result['bot']['bot_access_token']

        if not auth_entry:

            talent_bot_auth = TalentbotAuth(slack_user_token=access_token, slack_team_id=team_id,
                                            slack_user_id=user_id, slack_team_name=team_name, bot_id=bot_id,
                                            bot_token=bot_token)
            talent_bot_auth.save()
            return "Your Slack credentials have been saved"
        auth_entry.slack_user_token = access_token
        auth_entry.bot_id = bot_id
        auth_entry.bot_token = bot_token
        auth_entry.save()
        return "Your slack token has been updated"
    return "Your slack id already exists"
