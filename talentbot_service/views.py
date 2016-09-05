# Builtin imports
import random
# App specific imports
from const import TWILIO_NUMBER, ERROR_MESSAGE, STANDARD_MSG_LENGTH, SLACK_BOT_TOKEN, QUESTIONS, BOT_NAME
from talentbot import slack_client, twilio_client,\
    create_a_response, handle_slack_messages, \
    send_mail_via_api, sender_action, handle_user_messages,\
    reply_on_facebook, get_total_sms_segments, SlackBot
from talentbot_service import app
# 3rd party imports
from flask import request

TIME_STAMP = 9999999
AT_BOT = ""


slack_bot = SlackBot(SLACK_BOT_TOKEN, QUESTIONS, BOT_NAME, ERROR_MESSAGE)


@app.route('/index')
def index():
    """
    Index page
    """
    return "Index"


@app.route("/listen-slack", methods=['GET', 'POST'])
def listen_slack():
    """
    Listens to the slack web hook
    :return: str
    """
<<<<<<< HEAD:talentbot_service/views.py
    message = request.form.get('text')
    channel_id = request.form.get('channel_id')
    if message and slack_bot.at_bot and channel_id:
        if slack_bot.at_bot in message or slack_bot.at_bot+':' in message:
            message = message.lstrip(slack_bot.at_bot)
            slack_bot.handle_communication(channel_id, message)
        return "OK"
=======
    slack_client.rtm_connect()
    message = request.form['text']
    global AT_BOT
    if AT_BOT == "":
        # TODO: Avoid inline imports
        from talentbot import get_bot_id
        AT_BOT = get_bot_id()
    if AT_BOT in message or AT_BOT+':' in message:
        message = message.lstrip(AT_BOT)
        handle_slack_messages(request.form['channel_id'], message)
    return "OK"
>>>>>>> 5dbd5a4a8295243e7916f6b36a17921ce0fe29b0:talentbot-service/views.py


@app.route("/talentbot-message-campaign/", methods=['GET', 'POST'])
def handle_twilio_webhook():
    """
    Listens to the twilio callbacks
    :return: str
    """
    # TODO: remove empty line

    recipient = request.form.get('From')
    message_body = request.form.get('Body')
    if recipient and message_body:
        response = create_a_response(message_body)
        if len(response) > STANDARD_MSG_LENGTH:
            tokens = response.split('\n')
            total_segments, dict_of_segments = get_total_sms_segments(tokens)
            segment_indexer = 1
            while segment_indexer <= total_segments:
                segment = dict_of_segments.get(segment_indexer) + \
                        "("+str(segment_indexer)+"/"+str(total_segments)+")"  # TODO: PEP08 warning
                message = twilio_client.messages.create(to=recipient, from_=TWILIO_NUMBER,
                                                        body=segment)
                segment_indexer += 1
                print 'Twilio response status: ', message.status
                print 'message body:', segment
        else:
            message = twilio_client.messages.create(to=recipient, from_=TWILIO_NUMBER,
                                                    body=response)
            print 'Reply: ', response
            print 'Twilio response status: ', message.status

    return str('ok')


@app.route('/mailgun/msg/', methods=['POST'])
def receive_mailgun_mail():
    """
    End point which listens mail gun callbacks
    :return: str
    """
    message = request.form.get('stripped-text')
    sender = request.form.get('sender')
    print message, sender
    try:
        response = create_a_response(message)
    except IndexError:
        response = random.choice(ERROR_MESSAGE)
    send_mail_via_api(request.form['sender'], request.form['subject'], "<br />".join(response.split("\n")))
    print 'Mail reply: ', response
    return "OK"


@app.route('/', methods=['GET'])
def handle_verification():
    """
    End point which handles facebook challenge code
    :return: str
    """
    return request.args['hub.challenge']


@app.route('/', methods=['POST'])
def handle_incoming_messages():
    """
    End point to listen facebook web hooks
    :return: str
    """
    data = request.json
    sender = data['entry'][0]['messaging'][0]['sender']['id']
    msg = data['entry'][0]['messaging'][0].get('message')
    current_timestamp = data['entry'][0]['messaging'][0]['timestamp']
    print 'current timestamp:', current_timestamp, 'old timestamp:', TIME_STAMP
    if msg and TIME_STAMP != current_timestamp:
        global TIME_STAMP
        TIME_STAMP = current_timestamp
        sender_action(sender, "mark_seen")
        sender_action(sender, "typing_on")
        message = data['entry'][0]['messaging'][0]['message']['text']
        try:
            handle_user_messages(sender, message)
            print 'FB incoming message:'+message
        except Exception:
            reply_on_facebook(sender, random.choice(ERROR_MESSAGE))
            sender_action(sender, "typing_off")
            return "ok"
    return "ok"


@app.route('/slack/auth', methods=['GET', 'POST'])
def get_new_user_credentials():
    return "ok"
