"""
This module has a class ProcessScheduler which runs class SlackBot's question handler in a thread and
makes sure it is finished.
 - schedule_process()
"""
# Builtin imports
from multiprocessing import Process


class ProcessScheduler(object):
    """
    This class runs class SlackBot's handle_question() method in an async thread
    """
    def __init__(self):
        pass

    @staticmethod
    def schedule_slack_process(slack_bot, channel_id, message, slack_user_id, current_timestamp):
        """
        This method runs class SlackBot's handle_question() method in a thread and makes sure it ends
        :param SlackBot slack_bot: SlackBot object
        :param str channel_id: Slack channel Id
        :param str message: User's message
        :param str slack_user_id: User's Slack Id
        :param str current_timestamp: Current timestamp
        """
        slack_handler_process = Process(target=slack_bot.handle_communication,
                                        args=(channel_id, message, slack_user_id, current_timestamp))
        slack_handler_process.start()

    @staticmethod
    def schedule_fb_process(fb_user_id, message, facebook_bot):
        """
        This method runs class FacebookBot's handle_question() method in a thread and makes sure it
        ends
        :param FacebookBot facebook_bot: FacebookBot object
        :param str fb_user_id: User's Facebook Id
        :param message: User's message
        """
        fb_handler_process = Process(target=facebook_bot.handle_communication,
                                     args=(fb_user_id, message))
        fb_handler_process.start()
