"""
This module contains validators for SMS, Facebook, Email and Slack request parameters
Author: Kamal Hasan <kamalhasan.qc@gmail.com>
"""
import re
from talentbot_service.common.error_handling import InvalidUsage, NotFoundError
from talentbot_service.common.models.user import UserPhone, TalentbotAuth, User


def validate_and_format_request_data_for_sms(data):
    """
    Validates and formats request data related to SMS
    :param dict data: Request data
    :return: dictionary of formatted data
    :rtype: dict
    """
    user_phone_id = data.get('user_phone_id')
    user_phone = data.get('user_phone')
    if not bool(user_phone) ^ bool(user_phone_id):  # Only one field must exist XNOR
        raise InvalidUsage("One field should be provided either user_phone or user_phone_id")
    if user_phone_id:
        if not isinstance(user_phone_id, (int, long)):
            raise InvalidUsage("Invalid user_phone_id type")
        phone = UserPhone.get_by_id(user_phone_id)
        if not phone:
            raise InvalidUsage("No resource found against specified user_phone_id")
        tb_auth = TalentbotAuth.get_talentbot_auth(user_phone_id=user_phone_id)
        if tb_auth:
            raise InvalidUsage("user_phone_id is already being used")

    return {"user_phone": user_phone.strip()} if user_phone else {"user_phone_id": user_phone_id}


def validate_and_format_request_data_for_facebook(data):
    """
    Validates and formats request data related to Facebook
    :param dict data: Request data
    :rtype: dict
    """
    facebook_user_id = data.get('facebook_user_id')
    if not facebook_user_id:
        raise InvalidUsage("No facebook_user_id provided")
    return {
        "facebook_user_id": facebook_user_id.strip()
    }


def validate_and_format_data_for_slack(data):
    """
    Validates and formats request data related to Slack
    :param dict data: Request data
    :return: dictionary of formatted data
    :rtype: dict
    """
    dict_of_request_data = {
        "access_token": data.get('access_token'),  # Required
        "team_id": data.get('team_id'),  # Required
        "team_name": data.get('team_name'),  # Required
        "slack_user_id": data.get('user_id'),  # Required
        "bot_id": data.get('bot').get('bot_user_id') if data.get('bot') else None,  # Required
        "bot_token": data.get('bot').get('bot_access_token') if data.get('bot') else None  # Required
    }

    auth_entry = TalentbotAuth.query.filter_by(slack_user_id=dict_of_request_data["slack_user_id"]).first()\
        if dict_of_request_data["slack_user_id"] else None

    if auth_entry:
        raise InvalidUsage("Slack_user_id already exists")
    keys_with_none_values = [key for key in dict_of_request_data if dict_of_request_data[key] is None]
    if len(keys_with_none_values) > 0:
        raise InvalidUsage("Please provide these required fields %s" % [key for key in dict_of_request_data if
                                                                        dict_of_request_data[key] is None])
    for key in dict_of_request_data:
        dict_of_request_data[key] = dict_of_request_data[key].strip()
    return dict_of_request_data


def validate_and_format_data_for_email(data):
    """
    Validates and formats request data related to Email
    :param dict data: Request data
    :return: dictionary of formatted data
    :rtype: dict
    """
    email = data.get("email")
    if not email:
        raise InvalidUsage("No email specified")
    is_valid_email = re.search(r"(^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9]+\.[a-zA-Z0-9.]*\.*[com|org|edu]{3}$)", email)
    if not is_valid_email:
        raise InvalidUsage("Invalid email")
    return {
        "email": email.strip().lower()
    }


def validate_user_id(data):
    """
    This method validates that user_id is not None and type of user_id is int or long and
    makes sure that user exists against the given user_id
    :param dict data: Request data
    """
    user_id = data.get('user_id')
    if not user_id:
        raise InvalidUsage("user_id is a required field")
    if not isinstance(user_id, (int, long)):
        raise InvalidUsage("Invalid user_id type")
    user = User.get_by_id(user_id)
    if not user:
        raise NotFoundError("No user exist for user_id %d" % user_id)