"""
This module contains SocialNetworkBase class which provides common methods for
all social networks like get_access_token(), validate_access_token(),
refresh_access_token(), get_member_id() and save_user_credentials_in_db() etc.
"""

import requests

from abc import ABCMeta
from social_network_service import logger
from common.models.user import User, UserCredentials
from common.models.social_network import SocialNetwork
from social_network_service.custom_exections import NoUserFound, \
    UserCredentialsNotFound, MissingFiledsInUserCredentials, ApiException
from utilities import log_error, log_exception, http_request, get_class


class SocialNetworkBase(object):
    """This is the base class for all three social networks
     1-Meetup, 2-Eventbrite, 3-Facebook for now.
     It contains the common functionality and some abstract methods which
     are implemented by child classes.

    It contains following methods:

    * __init__():
        This method is called by creating any child RSVP class object.
        - It takes "user_id" as keyword argument.
        - It sets initial values for its object e.g.
            It sets user, user_credentials, social network,
            headers (authentication headers), api_url, access_token.

    * process(self, mode, user_credentials=None):
        This method is called by the social network manager while importing
        events or RSVPs. It takes "mode" as parameter and based
        on its value, it calls the process_events() or process_event_rsvps() to
        import events and rsvps respectively.

    * get_access_token(cls, data):
        When user tries to connect to a social network (eventbrite and meetup
        for now), then after successful redirection, social network returns a
        "code" to exchange for access and refresh tokens. We exchange "code"
        for access and refresh tokens in this method.

    * get_member_id(self, data):
        This method is used to get the member id of getTalent user on provided
        social network. e.g. profile id of user on Facebook.

    * validate_token(self, payload=None):
        This method is made for validation of access token. It returns True if
        access token is valid and False otherwise.

    * refresh_access_token(self):
        If access token has expired, any child can implement this method to
        refresh access token accordingly,

    * validate_and_refresh_access_token(self):
        This uses validate_token() to validate and refresh_access_token()
        to refresh access token.

    * save_user_credentials_in_db(user_credentials):
        Once we have the access token of user for some social network, we save
        this in user_credentials db table in this method.

    - This class does the authentication of access token and calls required
        methods to import/create events or import RSVPs

    - We make the object of this class as given in following:
        :Example:

        If we are importing events of Meetup social network, then we do the
            following steps:

        1- Create class object
            from social_network_service.meetup import Meetup
            sn = Meetup(user_id=1)

        2- Call process()
            sn.process('event', user_credentials=user_credentials)

        3- Create EventClass object
            sn_event_obj = event_class(user_credentials=user_credentials,
                                           social_network=self.social_network,
                                           headers=self.headers)
        4- Get events of user from API of social network
            self.events = sn_event_obj.get_events()

        5- Finally call process_events(self.events) to process and save events
            in database.
                sn_event_obj.process_events(self.events)

    **See Also**
        .. seealso:: start() function in social network manager.
        (social_network_service/manager.py)

        .. seealso:: process_event() function in social network manager.
        (social_network_service/manager.py)
    """
    __metaclass__ = ABCMeta

    def __init__(self,  *args, **kwargs):
        """
        - This sets the user's credentials as base class property so that it
            can be used in other classes.

        - We also check the validity of access token and try to refresh it in
            case it has expired.
        :param args:
        :param kwargs:
        :return:
        """
        self.events = []
        self.api_relative_url = None
        user_id = kwargs.get('user_id')
        self.user = User.query.get(user_id)
        if isinstance(self.user, User):
            self.social_network = \
                SocialNetwork.get_by_name(self.__class__.__name__)
            self.user_credentials = \
                UserCredentials.get_by_user_and_social_network_id(
                    user_id, self.social_network.id)
            if self.user_credentials:
                data = {
                    "access_token": self.user_credentials.access_token,
                    "gt_user_id": self.user_credentials.user_id,
                    "social_network_id": self.social_network.id,
                    "api_url": self.social_network.api_url
                }
                # checks if any field is missing for given user credentials
                items = [value for key, value in data.iteritems()
                         if key is not "api_url"]
                if all(items):
                    self.api_url = data['api_url']
                    self.gt_user_id = data['gt_user_id']
                    self.social_network_id = data['social_network_id']
                    self.access_token = data['access_token']
                    self.headers = {'Authorization': 'Bearer ' + self.access_token}
                else:
                    # gets fields which are missing
                    items = [key for key, value in data.iteritems()
                             if key is not "api_url" and not value]
                    data_to_log = {'user_id': self.user.id,
                                   'missing_items': items}
                    # Log those fields in error which are not present in Database
                    error_message = \
                        "User id: %(user_id)s\n Missing Item(s) in user's " \
                        "credential: %(missing_items)s\n" % data_to_log
                    raise MissingFiledsInUserCredentials('API Error: %s' % error_message)
            else:
                raise UserCredentialsNotFound('API Error: User Credentials not'
                                              ' found')
        else:
            error_message = "No User found in database with id %(user_id)s" \
                            % kwargs.get('user_id')
            raise NoUserFound('API Error: %s' % error_message)
        # Eventbrite and meetup social networks take access token in header
        # so here we generate authorization header to be used by both of them
        self.headers = {'Authorization': 'Bearer ' + self.access_token}
        # token validity is checked here
        # if token is expired, we refresh it here
        self.access_token_status = self.validate_and_refresh_access_token()
        self.start_date_dt = None

    def process(self, mode, user_credentials=None):
        """
        :param mode: mode is either 'event' or 'rsvp.
        :param user_credentials: are the credentials of user for
                                    a specific social network in db.

        - Depending upon the mode, here we make the objects of required
            classes (Event Class or RSVP class) and call required methods on
            those objects for importing events or rsvps.

        - This method is called from start() defined in social network manager
            inside social_network_service/manager.py.

        :Example:
                from social_network_service.meetup import Meetup
                sn = Meetup(user_id=1)
                sn.process('event', user_credentials=user_credentials)

        **See Also**
        .. seealso:: start() function defined in social network manager
            inside social_network_service/manager.py.
        """
        try:
            sn_name = self.social_network.name.strip()
            # get_required class under social_network_service/event/ to
            # process events
            event_class = get_class(sn_name, 'event')
            # create object of selected event class
            sn_event_obj = event_class(user_credentials=user_credentials,
                                       social_network=self.social_network,
                                       headers=self.headers)
            if mode == 'event':
                # gets events using respective API of Social Network
                logger.debug('Getting events of %s(UserId: %s) from '
                             '%s website.' % (self.user.name, self.user.id,
                                self.social_network.name))
                self.events = sn_event_obj.get_events()
                logger.debug('Got %s events of %s(UserId: %s) on %s within '
                             'provided time range.'
                             % (len(self.events), self.user.name, self.user.id,
                                self.social_network.name))
                # process events to save in database
                sn_event_obj.process_events(self.events)
            elif mode == 'rsvp':
                sn_event_obj.process_events_rsvps(user_credentials)
        except Exception as e:
            log_exception({'user_id': '',
                           'error': e.message})

    # def process_events(self):
    #     """
    #     This method gets events by calling the respective event's
    #     class in the SocialNetworkService/event directory. So if
    #     we want to retrieve events for Eventbrite then we're basically
    #     doing this.
    #     from event import eventbrite
    #     eventbrite = eventbrite.Eventbrite(self.user, self.social_network)
    #     self.events = eventbrite.get_events(self.social_network)
    #     :return:
    #     """
    #     sn_name = self.social_network.name.strip()
    #     event_class = get_class(sn_name, 'event')
    #     sn_event_obj = event_class(user=self.user,
    #                                social_network=self.social_network,
    #                                headers=self.headers)
    #     self.events = sn_event_obj.get_events()
    #     sn_event_obj.process_events(self.events)
    #
    # def process_rsvps(self, user_credentials=None):
    #     """
    #     This method gets events by calling the respective event's
    #     class in the SocialNetworkService/event directory. So if
    #     we want to retrieve events for Eventbrite then we're basically
    #     doing this.
    #     from event import eventbrite
    #     eventbrite = eventbrite.Eventbrite(self.user, self.social_network)
    #     self.events = eventbrite.get_events(self.social_network)
    #     :return:
    #     """
    #
    #     sn_name = self.social_network.name.strip()
    #     event_class = get_class(sn_name, 'event')
    #     sn_event_obj = event_class(user=self.user,
    #                                social_network=self.social_network,
    #                                headers=self.headers)
    #
    #     sn_rsvp_class = get_class(sn_name, 'rsvp')
    #     sn_rsvp_obj = sn_rsvp_class(social_network=self.social_network,
    #                                 headers=self.headers,
    #                                 user_credentials=user_credentials)
    #
    #     self.events = sn_event_obj.get_events_from_db(sn_rsvp_obj.start_date_dt)
    #
    #     sn_rsvp_obj.process_rsvps(self.events)

    @classmethod
    def get_access_token(cls, data):  # data contains social_network,
                                    # code to get access token, api_relative_url
        """
        When user tries to connect to a social network (eventbrite and meetup
        for now), then after successful redirection, social network returns a
        "code" to exchange for access and refresh tokens. We exchange "code"
        for access and refresh tokens in this method.
        :return:
        """
        # TODO comment after API endpoint works fine
        access_token = None
        refresh_token = None
        auth_url = data['social_network'].auth_url + data['relative_url']
        payload_data = {'client_id': data['social_network'].client_key,
                        'client_secret': data['social_network'].secret_key,
                        'grant_type': 'authorization_code',
                        'redirect_uri': data['social_network'].redirect_uri,
                        'code': data['code']}
        get_token_response = http_request('POST', auth_url, data=payload_data)
        try:
            if get_token_response.ok:
                # access token is used to make API calls, this is what we need
                # to make subsequent calls
                response = get_token_response.json()
                access_token = response.get('access_token')
                # refresh token is used to refresh the access token
                refresh_token = response.get('refresh_token')
            else:
                error_message = get_token_response.json().get('error')
                log_error({'user_id': '',
                           'error': error_message})
        except Exception as e:
            error_message = e.message
            log_exception({'user_id': '',
                           'error': error_message})
        return access_token, refresh_token

    def get_member_id(self, data):
        """
        :param data: data contains the API relative url
                    (which is passed by child classes) to make API call to get
                    member id.

        - Member Id is the id of user on some social network. This is used
            to fetch events or RSVPs of user from social network.

        - This method is called from start() defined in social network manager
            inside social_network_service/manager.py.

        :Example:
                from social_network_service.meetup import Meetup
                sn = Meetup(user_id=1)
                sn.get_member_id(dict(api_relative_url='/member/self'))

        **See Also**
        .. seealso:: start() function defined in social network manager
            inside social_network_service/manager.py.
        """
        try:
            user_credentials = self.user_credentials
            url = self.api_url + data['api_relative_url']
            # Now we have the URL, access token, and header is set too,
            get_member_id_response = http_request('POST', url, headers=self.headers,
                                                  user_id=self.user.id)
            if get_member_id_response.ok:
                member_id = get_member_id_response.json().get('id')
                data = dict(user_id=user_credentials.user_id,
                            social_network_id=user_credentials.social_network_id,
                            member_id=member_id)
                self.save_user_credentials_in_db(data)
            else:
                # Error has been logged inside http_request()
                pass
        except Exception as error:
            error_message = error.message
            log_exception({'user_id': self.user.id,
                           'error': error_message})

    def validate_token(self, payload=None):
        """
        :param payload: contains the access token of Facebook (Child class
            sets the payload) or is None for other social networks.

        - This function is called from validate_and_refresh_access_token()
         social network service base class inside social_network_service/base.py
         to check the validity of the access token of current user for a specific
         social network. We take the access token, make request to social network
         API, and check if it didn't error'ed out.

        :Example:
                from social_network_service.meetup import Meetup
                sn = Meetup(user_id=1)
                sn.validate_token()

        **See Also**
        .. seealso:: __init__() function defined in social network manager
            inside social_network_service/manager.py.

        :return status of of access token either True or False.
        """
        status = False
        relative_url = self.api_relative_url
        url = self.api_url + relative_url
        try:
            response = requests.get(url, headers=self.headers, params=payload)
            if response.ok:
                status = True
            else:
                logger.debug("Access token has expired for %s(UserId:%s)."
                             " Social Network is %s"
                             % (self.user.name, self.user.id,
                                self.social_network.name))
        except requests.RequestException as e:
            error_message = e.message
            log_exception({'user_id': self.user.id,
                           'error': error_message})
        return status

    def refresh_access_token(self):
        """
        - This function is used to refresh the access token. Child class
            will implement this if needed (e.g. meetup for now).

        - This function is called from validate_and_refresh_access_token()
            defined SocialNetworkBase inside social_network_service/base.py

        :Example:
                from social_network_service.meetup import Meetup
                sn = Meetup(user_id=1)
                sn.refresh_access_token()

        **See Also**
        .. seealso:: refresh_access_token() method defined in Meetup class
            inside social_network_service/meetup.py.

        .. seealso:: validate_and_refresh_token() method defined in
            SocialNetworkBase class inside social_network_service/base.py.

        :return True if token has been refreshed successfully, False otherwise.

        """
        return False

    def validate_and_refresh_access_token(self):
        """
        - This validates the access token. if access token has
        expired. It also refreshes it and saves the fresh access token in database.

        - It calls validate_access_token() and refresh_access_token() defined
            in SocialNetworkBase class inside social_network_service/base.py

        :Example:
                from social_network_service.meetup import Meetup
                sn = Meetup(user_id=1)
                sn.validate_and_refresh_access_token()

        **See Also**
        .. seealso:: __init__() method of SocialNetworkBase class
            inside social_network_service/base.py.

        :return the True if token has been refreshed, False otherwise.
        """
        access_token_status = self.validate_token()
        if not access_token_status:  # access token has expired, need to refresh it
            return self.refresh_access_token()
        return access_token_status


    @staticmethod
    def save_user_credentials_in_db(user_credentials):
        """
        - It checks if user_credentials are already in database. If a record
            is found, it updates the record. Otherwise it saves as new record.

        - It is called e.g. from refresh_access_token() inside
            social_network_service/meetup.py

        :Example:
                from social_network_service.meetup import Meetup
                sn = Meetup(user_id=1)
                sn.save_user_credentials_in_db(data)

        **See Also**
        .. seealso:: refresh_access_token() method of Meetup class
            inside social_network_service/meetup.py

        :return the True if db transaction is successful. False otherwise.
        """
        gt_user_in_db = UserCredentials.get_by_user_and_social_network_id(
            user_credentials['user_id'], user_credentials['social_network_id'])
        try:
            if gt_user_in_db:
                gt_user_in_db.update(**user_credentials)
            else:
                UserCredentials.save(**user_credentials)
            return True
        except Exception as e:
            error_message = e.message
            log_exception({'user_id': user_credentials['user_id'],
                           'error': error_message})
        return False

    @classmethod
    def get_access_and_refresh_token(cls, url, payload_data, user_id, social_network):
        """
        This function is used by Social Network API to save 'access_token' and 'refresh_token'
        for specific social network against a user (current user) by sending an POST call
        to respective social network API.
        :param user_id: current user id
        :type user_id: int
        :param social_network: social_network in getTalent database
        :type social_network: common.models.social_network.SocialNetwork
        :param payload_data: dictionary containing required data
                sample data
                payload_data = {'client_id': social_network.client_key,
                                'client_secret': social_network.secret_key,
                                'grant_type': 'authorization_code', # vendor specific
                                'redirect_uri': social_network.redirect_uri,
                                'code': code_to_get_access_token
                                }
        :type payload_data: dict
        :return:
        """
        get_token_response = http_request('POST', url, data=payload_data,
                                          user_id=user_id)
        try:
            if get_token_response.ok:
                # access token is used to make API calls, this is what we need
                # to make subsequent calls
                response = get_token_response.json()
                access_token = response.get('access_token')
                # refresh token is used to refresh the access token
                refresh_token = response.get('refresh_token')
                user_credentials = UserCredentials.get_by_user_and_social_network_id(user_id, social_network.id)
                if user_credentials:
                    user_credentials.update(access_token=access_token,
                                            refresh_token=refresh_token)
                else:
                    user_credentials = UserCredentials(user_id=user_id,
                                                       social_network_id=social_network.id,
                                                       access_token=access_token,
                                                       refresh_token=refresh_token)
                    UserCredentials.save(user_credentials)
            else:
                error_message = get_token_response.json().get('error')
                log_error({'user_id': user_id,
                           'error': error_message})
                raise ApiException('Unable to to get access token for current user')

        except Exception as e:
            error_message = e.message
            log_exception({'user_id': user_id,
                           'error': error_message})
            raise ApiException('Unable to create user credentials for current user')
        return user_credentials
