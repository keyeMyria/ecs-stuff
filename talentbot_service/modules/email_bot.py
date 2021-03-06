"""
This module contains class EmailBot which is inherited from TalentBot class. It handles bot interaction
with Email.
- authenticate_user()
- reply()
- handle_communication()
"""
# Builtin imports
import random
# Common utils
from talentbot_service.common.models.user import TalentbotAuth, User
# App specific imports
from talentbot_service.common.talent_config_manager import TalentConfigKeys
from talentbot_service.modules.constants import AUTHENTICATION_FAILURE_MSG, I_AM_PARSING_A_RESUME, USER_DISABLED_MSG
from talentbot_service.modules.talent_bot import TalentBot
from talentbot_service import logger, app
from talentbot_service.common.utils.amazon_ses import send_email


class EmailBot(TalentBot):
    """
    This class handles bot-user communication through Email
    """
    def __init__(self, questions, bot_name,
                 bot_image, error_messages):
        super(EmailBot, self).__init__(questions, bot_name, error_messages)
        self.bot_image = bot_image

    def authenticate_user(self, email_id, subject, email_body):
        """
        Authenticates user and remove secret email token from message body
        :param str email_id: User Email Id
        :param str subject: Received Email subject
        :param str email_body: Received Email body
        :rtype: tuple (True|False, str|None, int|None)
        :return: is_authenticated, email_body, user Id
        """
        user_id = TalentbotAuth.get_user_id(email=email_id)
        if user_id:
            user = User.get_by_id(user_id[0])
            if user.is_disabled:
                is_authenticated, user_id = True, None
                return is_authenticated, email_body, user_id
            is_authenticated = True
            return is_authenticated, email_body, user_id[0]
        is_authenticated, user_id = False, None
        return is_authenticated, email_body, user_id

    def reply(self, recipient, subject, message):
        """
        Sends Email to the recipient via mailgun API
        :param str recipient: Email sender
        :param str subject: Subject of email
        :param str message: Email response message
        :return: response from mailgun API
        :rtype: response
        """
        html = '<html><img src="' + self.bot_image + '" style="width: 9%; display:'\
                                                     ' inline;"><h5 style="display:'\
                                                     ' table-cell; vertical-align:'\
                                                     ' top;margin-left: 1%;">' + message +\
               '</h5></html>'
        response = send_email(source=app.config[TalentConfigKeys.BOT_SOURCE_EMAIL], subject=subject, body=None,
                              html_body=html, email_format='html', to_addresses=[recipient])
        logger.info('Mail reply "%s", to %s' % (message, recipient))
        return response

    def handle_communication(self, recipient, subject, message):
        """
        Handles communication between user and bot
        :param str recipient: User's email Id
        :param str subject: Email subject
        :param message: User's message
        :rtype: None
        """
        is_authenticated, message, user_id = self.authenticate_user(recipient, subject, message)
        if is_authenticated:
            if not user_id:
                self.reply(recipient, subject, USER_DISABLED_MSG)
            else:
                if self.is_response_time_more_than_usual(message):
                    self.reply(recipient, subject, I_AM_PARSING_A_RESUME)
                try:
                    response_generated = self.parse_message(message, user_id)
                    if not response_generated:
                        raise IndexError
                    response_generated = self.clean_response_message(response_generated)
                    self.reply(recipient, subject, "<br />".join(response_generated.split("\n")))
                except Exception as error:
                    logger.error("Error occurred while generating response: %s" % error.message)
                    error_response = random.choice(self.error_messages)
                    self.reply(recipient, subject, error_response)
        else:  # User not authenticated
            self.reply(recipient, subject, AUTHENTICATION_FAILURE_MSG)
