"""
This module contains class SmsBot which is inherited from TalentBot class. It handles bot interaction
with SMS.
- authenticate_user()
- reply()
- handle_communication()
- get_total_sms_segments()
"""
# Builtin import
import random

from talentbot_service.modules.constants import TEXT_MESSAGE_MAX_LENGTH
from twilio.rest import TwilioRestClient

from talentbot_service.modules.talentbot import TalentBot


class SmsBot(TalentBot):
    def __init__(self, questions, bot_name, error_messages, twilio_account_sid, twilio_auth_token,
                 standard_sms_length, twilio_number):
        TalentBot.__init__(self, questions, bot_name, error_messages)
        self.standard_sms_length = standard_sms_length
        self.twilio_number = twilio_number
        self.twilio_client = TwilioRestClient(twilio_account_sid, twilio_auth_token)

    def authenticate_user(self):
        """
        Authenticates user
        :return: True|False
        """
        return True

    def reply(self, response, recipient):
        """
        Replies to the user through sms
        :param str response: Response message from bot
        :param str recipient: User's mobile number
        """
        if len(response) > self.standard_sms_length:
            tokens = response.split('\n')
            total_segments, dict_of_segments = self.get_total_sms_segments(tokens)
            segment_indexer = 1
            while segment_indexer <= total_segments:
                segment = dict_of_segments.get(segment_indexer) + \
                        "("+str(segment_indexer)+"/"+str(total_segments) + ")"
                message = self.twilio_client.messages.create(to=recipient, from_=self.twilio_number,
                                                             body=segment)
                segment_indexer += 1
                print 'Twilio response status: ', message.status
                print 'message body:', segment
        else:
            message = self.twilio_client.messages.create(to=recipient, from_=self.twilio_number,
                                                         body=response)
            print 'SMS Reply: ', response
            print 'Twilio response status: ', message.status

    def handle_communication(self, message, recipient):
        """
        Handles communication between user and bot
        :param str message: User's message
        :param str recipient: User's mobile number
        """
        try:
            response_generated = self.parse_message(message)
            self.reply(response_generated, recipient)
        except Exception:
            error_response = random.choice(self.error_messages)
            self.reply(error_response, recipient)

    @classmethod
    def get_total_sms_segments(cls, tokens):
        """
        Breaks list of string lines into message segments and appends
        these segments in a dict with segment numbers as keys
        :param tokens: list of independent string lines
        :return: total number of message segments, dict of message segments
        :rtype: tuple(int, dict)
        """
        split_response_message = ""
        dict_of_segments = {}
        segments = 0
        while len(tokens) > 0:
            try:
                while len(tokens[0]) + len(split_response_message) <= TEXT_MESSAGE_MAX_LENGTH \
                        and len(tokens) > 0:
                    split_response_message = split_response_message + tokens.pop(0) + "\n"
                segments += 1
                dict_of_segments.update({segments: split_response_message})
                split_response_message = ""
            except IndexError:
                if len(split_response_message) > 0:
                    segments += 1
                    dict_of_segments.update({segments: split_response_message})
                return segments, dict_of_segments
        return segments, dict_of_segments
