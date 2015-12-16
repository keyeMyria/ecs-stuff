"""
Author: Hafiz Muhammad Basit, QC-Technologies,
        Lahore, Punjab, Pakistan <basit.gettalent@gmail.com>

This contains following helper classes/functions for SMS Campaign Service.

- Class TwilioSMS which uses TwilioAPI to buy new number, or send sms etc.
- Function search_urls_in_text() to search a URL present in given text.
- Function url_conversion() which takes the URL and try to make it shorter using
    Google's shorten URL API.
"""

# Standard Library
import re

# Third Party Imports
import twilio
import twilio.rest
from twilio.rest import TwilioRestClient

# Common Utils
from sms_campaign_service.common.utils.app_rest_urls import (SmsCampaignApiUrl, GTApis)

# Application Specific
from sms_campaign_service import logger
from sms_campaign_service.custom_exceptions import TwilioAPIError
from sms_campaign_service.sms_campaign_app_constants import (TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN,
                                                             NGROK_URL)


class TwilioSMS(object):
    """
    This class contains the methods of Twilio API to be used for SMS campaign service
    """

    def __init__(self):
        self.client = twilio.rest.TwilioRestClient(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
        self.country = 'US'
        self.phone_type = 'local'
        self.sms_enabled = True
        # self.sms_call_back_url = 'http://demo.twilio.com/docs/sms.xml'
        self.sms_call_back_url = SmsCampaignApiUrl.SMS_RECEIVE
        # self.sms_call_back_url = 'http://74cf4bd2.ngrok.io/v1/receive'
        self.sms_method = 'POST'

    def send_sms(self, body_text=None, receiver_phone=None, sender_phone=None):
        # -------------------------------------
        # sends SMS to given number
        # -------------------------------------
        try:
            message = self.client.messages.create(
                body=body_text,
                to=receiver_phone,
                from_=sender_phone
            )
            return message
        except twilio.TwilioRestException as error:
            raise TwilioAPIError(error_message=
                                 'Cannot get available number. Error is "%s"'
                                 % error.msg if hasattr(error, 'msg') else error.message)

    def get_available_numbers(self):
        # -------------------------------------
        # get list of available numbers
        # -------------------------------------
        try:
            phone_numbers = self.client.phone_numbers.search(
                country=self.country,
                type=self.phone_type,
                sms_enabled=self.sms_enabled,
            )
        except Exception as error:
            raise TwilioAPIError(error_message=
                                 'Cannot get available number. Error is "%s"'
                                 % error.msg if hasattr(error, 'msg') else error.message)
        return phone_numbers

    def purchase_twilio_number(self, phone_number):
        # --------------------------------------
        # Purchase a number
        # --------------------------------------
        try:
            number = self.client.phone_numbers.purchase(friendly_name=phone_number,
                                                        phone_number=phone_number,
                                                        sms_url=self.sms_call_back_url,
                                                        sms_method=self.sms_method,
                                                        )
            logger.info('Bought new Twilio number %s' % number.sid)
        except Exception as error:
            raise TwilioAPIError(error_message=
                                 'Cannot buy new number. Error is "%s"'
                                 % error.msg if hasattr(error, 'msg') else error.message)

    def update_sms_call_back_url(self, phone_number_sid):
        # --------------------------------------
        # Updates SMS callback URL of a number
        # --------------------------------------
        try:
            number = self.client.phone_numbers.update(phone_number_sid,
                                                      sms_url=self.sms_call_back_url)
            logger.info('SMS call back URL has been set to: %s' % number.sms_url)
        except Exception as error:
            raise TwilioAPIError(error_message=
                                 'Cannot buy new number. Error is "%s"'
                                 % error.msg if hasattr(error, 'msg') else error.message)

    def get_sid(self, phone_number):
        # --------------------------------------
        # Gets sid of a given number
        # --------------------------------------
        try:
            number = self.client.phone_numbers.list(phone_number=phone_number)
            if len(number) == 1:
                return 'SID of Phone Number %s is %s' % (phone_number, number[0].sid)
        except Exception as error:
            raise TwilioAPIError(error_message=
                                 'Cannot buy new number. Error is "%s"'
                                 % error.msg if hasattr(error, 'msg') else error.message)


def search_urls_in_text(text):
    """
    This checks if given text has any URL link present in it and returns all urls in a list.
    This checks for URLs starting with either http or https or www.
    :param text: string in which we want to search URL
    :type text: str
    :return: list of all URLs present in given text | []
    :rtype: list
    """
    return re.findall(r'https?://[^\s<>"]+|ftps?://[^\s<>"]+|www\.[^\s<>"]+', text)


# TODO: remove this when app is up
def replace_ngrok_link_with_localhost(temp_ngrok_link):
    """
    We have exposed our endpoint via ngrok. We need to expose endpoint as Google's shorten URL API
    looks for valid URL to convert into shorter version. While making HTTP request to this endpoint,
    if ngrok is not running somehow, we replace that link with localhost to hit that endpoint. i.e.

        https://9a99a454.ngrok.io/v1/campaigns/1298/url_redirection/294/?candidate_id=544
    will become
        https://127.0.0.1:8011/v1/campaigns/1298/url_redirection/294/?candidate_id=544

    In final version of app, this won't be necessary as we'll have valid URL for app.
    :param temp_ngrok_link:
    :return:
    """
    relative_url = temp_ngrok_link.split(SmsCampaignApiUrl.API_VERSION)[1]
    # API_URL is http://127.0.0.1:8011/v1 for dev
    return SmsCampaignApiUrl.API_URL % relative_url


# TODO: remove this when app is up
def replace_localhost_with_ngrok(localhost_url):
    """
    We have exposed our endpoint via ngrok. We need to expose endpoint as Google's shorten URL API
    looks for valid URL to convert into shorter version. While making HTTP request to this endpoint,
    if ngrok is not running somehow, we replace localhost_url with the ngrok exposed URL. i.e.

        https://127.0.0.1:8011/v1/campaigns/1298/url_redirection/294/?candidate_id=544

    will become

        https://9a99a454.ngrok.io/v1/campaigns/1298/url_redirection/294/?candidate_id=544


    In final version of app, this won't be necessary as we'll have valid URL for app.
    :param localhost_url:
    :return:
    """
    relative_url = localhost_url.split(str(GTApis.SMS_CAMPAIGN_SERVICE_PORT))[1]
    return NGROK_URL % relative_url
