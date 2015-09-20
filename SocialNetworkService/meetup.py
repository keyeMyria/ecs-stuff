import json
from datetime import datetime, timedelta
from base import SocialNetworkBase
from utilities import http_request, logger, log_error, log_exception


class Meetup(SocialNetworkBase):

    def __init__(self, *args, **kwargs):

        super(Meetup, self).__init__(*args, **kwargs)
        # token validity is checked here
        # if token is expired, we refresh it here
        self.validate_and_refresh_access_token()
        self.start_date = kwargs.get('start_date') or (datetime.now() - timedelta(days=90))
        self.end_date = kwargs.get('end_date') or (datetime.now() + timedelta(days=90))
        self.start_date_dt = self.start_date
        self.end_date_dt = self.end_date

    @classmethod
    def get_access_token(cls, code_to_get_access_token, relative_url=None):
        """
        This function is called from process_access_token() inside controller
        user.py. Here we get the access token from provided user_credentials
        and auth code for fetching access token by making API call.
        :return:
        """
        api_relative_url = "/access"
        super(Meetup, cls).get_access_token(code_to_get_access_token,
                                            relative_url=api_relative_url)

    def get_member_id(self):
        """
        This function is called from process_access_token() inside controller
        user.py. Here we get the access token from provided user_credentials
        and auth code for fetching access token by making API call.
        :return:
        """
        self.api_relative_url = '/member/self'
        super(Meetup, self).get_member_id()

    def get_groups(self):
        """
        This function returns the groups of Meetup for which the current user
        is an organizer to be shown in drop down while creating event on Meetup
        through Event Creation Form.
        """
        self.message_to_log.update({'functionName': 'get_groups()'})
        url = self.api_url + '/groups/'
        params = {'member_id': 'self'}
        response = self.get_data(url, params)
        if response.ok:
            meta_data = json.loads(response.text)['meta']
            member_id = meta_data['url'].split('=')[1].split('&')[0]
            data = json.loads(response.text)['results']
            groups = filter(lambda item: item['organizer']['member_id'] == int(member_id), data)
            return groups

    def validate_token(self, payload=None):
        self.api_relative_url = '/member/self'
        return super(Meetup, self).validate_token()

    def refresh_access_token(self):
        """
        When user authorize to Meetup account, we get a refresh token
        and access token. Access token expires in one hour.
        Here we refresh the access_token using refresh_token without user
        involvement and save in user_credentials db table
        :return:
        """
        function_name = 'refresh_access_token()'
        message_to_log = self.message_to_log.update({'function_name': function_name})
        status = False
        user_refresh_token = self.user_credentials.refreshToken
        auth_url = self.social_network.authUrl + "/access?"
        client_id = self.social_network.clientKey
        client_secret = self.social_network.secretKey
        payload_data = {'client_id': client_id,
                        'client_secret': client_secret,
                        'grant_type': 'refresh_token',
                        'refresh_token': user_refresh_token}
        response = http_request('POST', auth_url, data=payload_data,
                                message_to_log=message_to_log)
        try:
            if response.ok:
                self.access_token = response.json().get('access_token')
                refresh_token = response.json().get('refresh_token')
                data = dict(userId=self.user_credentials.userId,
                            socialNetworkId=self.user_credentials.socialNetworkId,
                            accessToken=self.access_token,
                            refreshToken=refresh_token,
                            memberId=self.user_credentials.memberId)
                status = self.save_token_in_db(data)
                logger.info("Access Token has been refreshed")
            else:
                error_message = response.json().get('error')
                message_to_log.update({'error': error_message})
                log_error(message_to_log)
        except Exception as e:
            error_message = "Error occurred while refreshing access token. Error is: " \
                            + e.message
            message_to_log.update({'error': error_message})
            log_exception(message_to_log)
        return status

    def get_rsvps(self, event):
        """
        Here we call MeetupRsvp class method get_rsvps
        :param event:
        :return:
        """
        rsvp_object = self.helper_class(**self.dict_to_pass)
        rsvps = rsvp_object.get_rsvps(event)
        return rsvps

    def get_attendee(self, rsvp):
        """
        Here we call MeetupRsvp class method get_attendee
        :param rsvp:
        :return:
        """
        rsvp_object = self.helper_class(**self.dict_to_pass)
        attendee = rsvp_object.get_attendee(rsvp)
        return attendee, rsvp_object

