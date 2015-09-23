"""
This file contains some (supposedly) common utility functions that may be used
or consumed by various programs.
"""
import importlib
import json
import logging
import datetime
import requests

from dateutil.parser import parse
from requests_oauthlib import OAuth2Session

from gt_common.gt_models.user import User
from gt_common.gt_models.social_network import SocialNetwork


logger = logging.getLogger('event_service.app')
OAUTH_SERVER = 'http://127.0.0.1:8888/oauth2/authorize'


class Attendee(object):
    """
    Basically a placeholder object that will be used while processing
    RSVPs. See base.py
    """

    def __init__(self, *args, **kwargs):
        self.first_name = None  # first name of attendee
        self.last_name = None  # last name of attendee
        self.full_name = None  # full name of attendee
        self.profile_url = None  # profile url of attendee
        self.picture_url = None  # picture url of attendee
        self.city = None  # city of attendee
        self.country = None  # country of attendee
        self.latitude = None  # latitude of attendee's location
        self.longitude = None  # longitude of attendee's location
        self.zip = None  # zip code of attendee's city/location
        self.rsvp_id = None  # attendee's rsvp id in db
        self.email = None  # attendee's email address
        self.rsvp_status = None  # attendee's rsvp status
        self.candidate_id = None  # attendee's id in candidate table
        self.event = None  # attendee's corresponding event in database
        self.vendor_img_link = None  # attendee's vendor image link
        # (image is present in static files of gt-app)
        self.added_time = None  # attendee's time of rsvp
        self.gt_user_id = None  # attendee's corresponding gt-user id
        self.vendor_rsvp_id = None  # attendee's vendor rsvp id
        self.social_network_id = None  # attendee's social network id
        self.candidate_event_rsvp_id = None  # attendee's entry id in
        self.candidate_source_id = None  # attendee's candidate_source id
        # from db
        self.source_product_id = None  # attendee's source product id in database
        # candidate_event_rsvp

    def __str__(self):
        return 'Name: %s, RSVP_ID: %s, EMAIL: %s' % (self.full_name,
                                                     self.rsvp_id,
                                                     self.email)


def unix_time(dt):
    epoch = datetime.datetime.utcfromtimestamp(0)
    delta = dt - epoch
    return delta.total_seconds()


def milliseconds_since_epoch(dt):
    assert isinstance(dt, datetime.datetime) == True
    return unix_time(dt) * 1000.0


def milliseconds_since_epoch_to_dt(epoch):
    return datetime.datetime.fromtimestamp(epoch / 1000.0)


def log_exception(traceback_info, message):
    """
    This function logs exception when it is called inside a catch block
    where ever it is called, traceback_info and error message is passed
    in arguments.
    :param message:
    :param traceback_info:
    :return:
    """
    traceback_info['error'] = message
    logger.exception("| Reason: %(error)s \n"
                     "functionName: %(functionName)s, "
                     "User: %(User)s, class: %(class)s, "
                     "memberId: %(memberId)s, |"
                     % traceback_info)


def log_error(traceback_info, message):
    """
    This function logs error when it is called inside a catch block
    where ever it is called, traceback_info and error message is passed
    in arguments.
    :param message:
    :param traceback_info:
    :return:
    """
    traceback_info['error'] = message
    logger.error("| Reason: %(error)s |"
                 "functionName: %(functionName)s, "
                 "User: %(User)s, class: %(class)s, "
                 "memberId: %(memberId)s, "
                 % traceback_info)


def authenticate_user(request):
    """
    :rtype: gluon.dal.objects.Row | None
    """
    auth_token = request.headers.get('Authorization')
    if auth_token and isinstance(auth_token, basestring):
        auth_token = auth_token.lower().replace('bearer ', '')
        try:
            remote = OAuth2Session(token={'access_token': auth_token})
            response = remote.get(OAUTH_SERVER)
            if response.status_code == 200:
                user_id = response.json().get('user_id') or ''
                return User.get_by_id(user_id) if user_id else None
            else:
                return None
        except Exception as e:
            return None
    else:
        return None


class EventInputMissing(Exception):
    pass


class EventNotSaved(Exception):
    pass


class EventNotCreated(Exception):
    pass


class EventNotPublished(Exception):
    pass


class EventNotUnpublished(Exception):
    pass


class EventLocationNotCreated(Exception):
    pass


class TicketsNotCreated(Exception):
    pass


class EventNotSaveInDb(Exception):
    pass


class UserCredentialsNotFound(Exception):
    pass


class SocialNetworkNotImplemented(Exception):
    pass


class InvalidAccessToken(Exception):
    pass


def get_message_to_log(gt_user_id='', function_name='', error='', class_name=''):
    """
    Here we define descriptive message to be used for logging purposes
    :param function_name:
    :param error:
    :param class_name:
    :return:
    """
    message_to_log = {
        'user': gt_user_id,  # TODO: replace it with actual user name
        'class': class_name,
        'fileName': 'TalentEventsAPI.py',
        'functionName': function_name,
        'error': error}
    return message_to_log


def log_exception(message_dict):
    """
    This function logs exception when it is called inside a catch block
    where ever it is called using message_dict as descriptive message to log.
    :param message_dict:
    :return:
    """
    message_to_log = ("Reason: %(error)s \n"
                      "functionName: %(functionName)s, "
                      "fileName: %(fileName)s, "
                      "User: %(user)s" % message_dict)
    if message_dict.get('class'):
        message_to_log += ", class: %(class)s" % message_dict
    logger.exception(message_to_log)


def log_error(message_dict):
    """
    This function logs error using message_dict as descriptive message to log.
    :param message_dict:
    :return:
    """
    message_to_log = ("Reason: %(error)s \n"
                      "functionName: %(functionName)s, "
                      "fileName: %(fileName)s, "
                      "User: %(user)s" % message_dict)
    if message_dict.get('class'):
        message_to_log += ", class: %(class)s" % message_dict
    logger.error(message_to_log)


def http_request(method_type, url, params=None, headers=None, data=None, message_to_log=None):
    """
    This is common function to make HTTP Requests. It takes method_type (GET or POST)
    and makes call on given URL. It also handles/logs exception.
    :param method_type: GET or POST.
    :param url: resource URL.
    :param params: params to be sent in URL.
    :param headers: headers for Authorization.
    :param data: data to be sent.
    :param message_to_log: descriptive message to log when exception occurs.
    :return:
    """
    if method_type in ['GET', 'POST']:
        method = getattr(requests, method_type.lower())
        error_message = None
        if url:
            try:
                response = method(url, params=params, headers=headers, data=data)
                # If we made a bad request (a 4XX client error or 5XX server error response),
                # we can raise it with Response.raise_for_status():"""
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                if 'errors' in e.response.json():
                    error_message = e.message + ' , Details: ' \
                                    + json.dumps(e.response.json().get('errors'))
                else:
                    error_message = e.message
            except requests.RequestException as e:
                error_message = e.message
            if error_message and message_to_log:
                message_to_log.update({'error': error_message})
                log_exception(message_to_log)
            return response
        else:
            error_message = 'URL is None. Unable to make %s Call' % method_type
            logger.error(error_message)
    else:
        logger.error('Unknown Method type %s ' % method_type)


def process_event(data, user_id):
    """
    This functions is called from restful POST service (which gets data from
    Event Create Form submission).
    It creates event on vendor as well as saves in database.
    Data in the arguments is the Data coming from Event creation form submission
    user_id is the id of current logged in user (which we get from session).
    """
    function_name = 'process_event()'
    message_to_log = _get_message_to_log(function_name=function_name)
    if data:
        vendor_id = data['socialNetworkId']
        social_network = SocialNetwork.get_by_id(vendor_id)
        data['user_id'] = user_id
        # converting incoming Datetime object from Form submission into the
        # required format for API call
        data['eventStartDatetime'] = parse(data['eventStartDatetime'])
        data['eventEndDatetime'] = parse(data['eventEndDatetime'])
        # creating class object for respective social network
        if social_network.name == EVENTBRITE.name:
            from event_exporter.eventbrite import Eventbrite
            class_object = Eventbrite()
        elif social_network.name == MEETUP.name:
            from event_exporter.meetup import Meetup
            class_object = Meetup(user_id=user_id)
        else:
            error_message = 'Social Network "%s" is not allowed for now, ' \
                            'please implement code for this social network.' \
                            % social_network.name
            message_to_log.update({'error': error_message})
            log_error(message_to_log)
            raise SocialNetworkNotImplemented
        # posting event on social network
        class_object.get_mapped_data(data)
        event_id, tickets_id = class_object.create_event()
        data['ticketsId'] = tickets_id
        if event_id:  # Event has been successfully published on vendor
            # save event in database
            save_event(event_id, data)
    else:
        error_message = 'Data not received from Event Creation/Edit FORM'
        message_to_log.update({'error': error_message})
        log_error(message_to_log)


def save_event(event_id, data):
    """
    This function serves the storage of event in database after it is
    successfully published.
    :param event_id:
    :param data:
    :return:
    """
    function_name = 'save_event()'
    message_to_log = _get_message_to_log(function_name=function_name)
    db_data = data
    # try:
    #     inserted_record_id = db.event.update_or_insert(
    #         ((db.event.vendorEventId == event_id) &
    #          (db.event.socialNetworkId == db_data['socialNetworkId'])),
    #         eventTitle=db_data['eventTitle'],
    #         eventDescription=db_data['eventDescription'],
    #         socialNetworkId=db_data['socialNetworkId'],
    #         userId=db_data['user_id'],
    #         eventStartDatetime=db_data['eventStartDatetime'],
    #         eventEndDatetime=db_data['eventEndDatetime'],
    #         vendorEventId=event_id,
    #         groupId=db_data['groupId'],
    #         groupUrlName=db_data['groupUrlName'],
    #         ticketsId=db_data['ticketsId'],
    #         eventAddressLine1=db_data['eventAddressLine1'],
    #         eventAddressLine2=db_data['eventAddressLine2'],
    #         eventState=db_data['eventState'],
    #         eventCity=db_data['eventCity'],
    #         eventZipCode=db_data['eventZipCode'],
    #         eventCountry=db_data['eventCountry'],
    #         organizerName=db_data['organizerName'],
    #         organizerEmail=db_data['organizerEmail'],
    #         aboutEventOrganizer=db_data['aboutEventOrganizer'],
    #         registrationInstruction=db_data['registrationInstruction'],
    #         eventCost=db_data['eventCost'],
    #         maxAttendees=db_data['maxAttendees'],
    #         eventLongitude=db_data['eventLongitude'],
    #         eventLatitude=db_data['eventLatitude'],
    #         eventCurrency=db_data['eventCurrency'],
    #         eventTimeZone=db_data['eventTimeZone'],
    #     )
    #     db.commit()
    #     logger.info('|  Event has been saved in Database  |')
    # except Exception as e:
    #     error_message = 'Event was not saved in Database\nError: %s' % str(e)
    #     message_to_log.update({'error': error_message})
    #     _log_error(message_to_log)
    #     raise EventNotSaveInDb
    # return inserted_record_id


def validate_token(access_token, social_network):
    """
    This function is called from get_and_update_auth_info() inside RESTful
    service social_networks() to check the validity of the access token
    of current user for a specific social network. We take the access token,
    make request to social network, and check if it didn't error'ed out.
    :param access_token: access_token of current user.
    :param social_network: social network model object for given access_token.
    :return:
    """
    function_name = 'validate_token()'
    message_to_log = _get_message_to_log(function_name=function_name)
    status = False
    payload = None
    if social_network.id == EVENTBRITE.id:
        relative_url = '/users/me/'
    elif social_network.id == MEETUP.id:
        relative_url = '/member/self'
    elif social_network.id == FACEBOOK.id:
        payload = {'access_token': access_token}
        relative_url = '/me'
    else:
        relative_url = ''
    url = social_network.apiUrl + relative_url
    headers = {'Authorization': 'Bearer %s' % access_token}
    try:
        response = requests.get(url, headers=headers, params=payload)
        if response.ok:
            status = True
        else:
            error_message = "Access token has expired for %s" % social_network.name
            message_to_log.update({'error': error_message})
            _log_error(message_to_log)
    except requests.RequestException as e:
        error_message = e.message
        message_to_log.update({'error': error_message})
        _log_exception(message_to_log)
    return status


def refresh_access_token(user_credential, social_network):
    """
    When user authorize to Meetup account, we get a refresh token
    and access token. Access token expires in one hour.
    Here we refresh the access_token using refresh_token without user
    involvement and save in user_credentials db table
    :param user_credential:
    :param social_network:
    :return:
    """
    function_name = 'refresh_access_token()'
    message_to_log = _get_message_to_log(function_name=function_name)
    status = False
    if social_network.name == MEETUP.name:
        user_refresh_token = user_credential.refreshToken
        member_id = user_credential.memberId
        auth_url = social_network.authUrl + "/access?"
        client_id = social_network.clientKey
        client_secret = social_network.secretKey
        payload_data = {'client_id': client_id,
                        'client_secret': client_secret,
                        'grant_type': 'refresh_token',
                        'refresh_token': user_refresh_token}
        response = http_request('POST', auth_url, data=payload_data,
                                message_to_log=message_to_log)
        try:
            if response.ok:
                access_token = response.json().get('access_token')
                status = save_token_in_db(access_token,
                                          user_refresh_token,
                                          member_id,
                                          social_network)
                logger.info("Access Token has been refreshed")
            else:
                error_message = response.json().get('error')
                message_to_log.update({'error': error_message})
                _log_error(message_to_log)
        except Exception as e:
            error_message = "Error occurred while refreshing access token. Error is: " \
                            + e.message
            message_to_log.update({'error': error_message})
            _log_exception(message_to_log)
    return status


def validate_and_refresh_access_token(user_credential):
    """
    This function is called to validate access token. if access token has
    expired, it also refreshes it and saves the fresh access token in database
    :return:
    """
    refreshed_token_status = False
    social_network = SocialNetwork.get_by_id(user_credential.socialNetworkId)
    access_token = user_credential.accessToken
    access_token_status = validate_token(access_token, social_network)
    if not access_token_status:  # access token has expired, need to refresh it
        refreshed_token_status = refresh_access_token(user_credential, social_network)
    return access_token_status, refreshed_token_status


def get_class(social_network_name, category):
    _class = None
    if category == 'social_network':
        module_name = 'SocialNetworkService.' + social_network_name
    else:
        module_name = 'SocialNetworkService.' + category + '.' + social_network_name + '_' + category
    try:
        module = importlib.import_module(module_name)
    except ImportError as ie:
        logger.exception("Event service manager cannot import module,"
                         " details: %s" % ie.message)
    else:
        if category == 'social_network':
            _class = getattr(module, social_network_name.title())
        else:
            _class = getattr(module, social_network_name.title() + category.title())
    return _class
