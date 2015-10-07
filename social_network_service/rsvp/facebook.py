import requests

from datetime import datetime, timedelta
from common.models.event import Event
from social_network_service.rsvp.base import RSVPBase
from social_network_service.utilities import Attendee, log_exception, \
    import_from_dist_packages, log_error

# Here we import facebook-sdk python module making sure it doesn't import
# our local facebook.py modules
facebook = import_from_dist_packages('facebook')


class Facebook(RSVPBase):
    """
    - This class is inherited from RSVPBase class.
    - This implements the following abstract methods

        1- get_rsvps() and
        2- get_attendee() defined in interface.

    :Example:

        - To process rsvp of an facebook event (via social network manager) you
            have to do following steps:

        1- Crete the object of this class by providing required parameters.
            sn_rsvp_obj = sn_rsvp_class(social_network=self.social_network,
                                        headers=self.headers,
                                        user_credentials=user_credentials)

        2. Get events of user from db within specified date range
            self.events = self.get_events_from_db(sn_rsvp_obj.start_date_dt)

        3. Get rsvps of all events using API of meetup
            self.rsvps = sn_rsvp_obj.get_all_rsvps(self.events)

        4. Call method process_rsvp() on rsvp object to process RSVPs
            sn_rsvp_obj.process_rsvps(self.rsvps)

        **See Also**
            .. seealso:: process_events_rsvps() method in
            social_network_service/event/base.py for more insight.

        .. note::
            You can learn more about meetup API from following link
            - https://developers.facebook.com/docs/graph-api
    """

    def __init__(self, *args, **kwargs):
        """
        - Here we set the date range to get events from database.
        :param args:
        :param kwargs:
        :return:
        """
        super(Facebook, self).__init__(*args, **kwargs)
        self.start_date = (datetime.now() - timedelta(days=3000)).strftime("%Y-%m-%d")
        self.end_date = (datetime.now() + timedelta(days=60)).strftime("%Y-%m-%d")
        self.start_date_dt = datetime.strptime(self.start_date, "%Y-%m-%d")
        self.end_date_dt = datetime.strptime(self.end_date, "%Y-%m-%d")
        self.graph = None

    def get_rsvps(self, event):
        """
        :param event: event is a db model object of model "Event".

        - We get RSVPs of given event from Graph API of Facebook

        - We use this method while importing RSVPs through social network
            manager.

        :Example:

        - Create RSVP class object as

        sn_rsvp_obj = sn_rsvp_class(social_network=self.social_network,
                                    headers=self.headers,
                                    user_credentials=user_credentials)

        - Then call get_all_rsvps() on sn_rsvp_obj by passing events in
        parameters as follow

            self.rsvps = sn_rsvp_obj.get_all_rsvps(self.events)

        - Inside get_all_rsvps(), we call get_rsvps() on class object.

        - It appends rsvps of an events in a list and returns it

        **See Also**
            .. seealso:: get_all_rsvps() method in RSVPBase class
            inside social_network_service/rsvp/base.py for more insight.

        :return: list of rsvps
        """
        rsvps = []
        try:
            self.graph = facebook.GraphAPI(access_token=self.access_token)
            url = 'v2.4/%s' % str(event.social_network_event_id) + '/'
            # Get list of people surely attending
            confirm_attendees = self.graph.get_object(url + 'attending')
        except facebook.GraphAPIError as error:
            error_message = "Couldn't get 'attending' RSVPs (Facebook). %s" % error.message
            log_exception({'user_id': self.user.id,
                           'error': error_message})
            raise
        rsvps += confirm_attendees['data']
        self.get_all_pages(confirm_attendees, rsvps)
        # Get list of people who aren't certain
        try:
            expected_attendees = self.graph.get_object(url + 'maybe')
        except facebook.GraphAPIError as error:
            error_message = "Couldn't get 'maybe' RSVPs (Facebook). %s" % error.message
            log_exception({'user_id': self.user.id,
                           'error': error_message})
            raise
        rsvps += expected_attendees['data']
        self.get_all_pages(expected_attendees, rsvps)
        # Get list of people who declined
        try:
            declined_attendees = self.graph.get_object(url + 'declined')
        except facebook.GraphAPIError as error:
            error_message = "Couldn't get 'Declined' RSVPs (Facebook). %s" % error.message
            log_exception({'user_id': self.user.id,
                           'error': error_message})
            raise
        rsvps += declined_attendees['data']
        self.get_all_pages(declined_attendees, rsvps)
        for rsvp in rsvps:
            rsvp.update({'vendor_event_id': str(event.social_network_event_id)})
        return rsvps

    def get_all_pages(self, response, target_list):
        """
         :param response: rsvp is likely the dict we get from the response
            of Graph API of Facebook.

        - This function is used to get the data of candidate related
          to given rsvp. It attaches all the information in attendee object.
          attendees is a utility object we share in calls that contains
          pertinent data.

        - This method is called from process_rsvps() present in
          RSVPBase class.

        :Example:

            attendee = self.get_attendee(rsvp)

        **See Also**
            .. seealso:: process_rsvps() method in RSVPBase class inside
            social_network_service/rsvp/base.py for more insight.

        :return: attendee object which contains data about the candidate
        :param response:
        :param target_list:
        :return:
        """
        while True:
            try:
                response = requests.get(response['paging']['next'])
                if response.ok:
                    response = response.json()
                # #TODO following if sohuld be removed
                if response and response['data']:
                    target_list.extend(response['data'])
            except KeyError:
                break
            except requests.HTTPError as error:
                error_message_dict = dict(url=response['paging']['next'],
                                          error_message=error.message)
                error_message = "Couldn't get data while paginating over Facebook records. " \
                                "URL: %(url)s, %(error_message)s" % error_message_dict
                log_exception({'user_id': self.user.id,
                              'error': error_message})
                raise

    def get_attendee(self, rsvp):
        """
        :param rsvp: rsvp is likely the dict we get from the response
            of Graph API of Facebook.

        - This function is used to get the data of candidate related
          to given rsvp. It attaches all the information in attendee object.
          attendees is a utility object we share in calls that contains
          pertinent data.

        - This method is called from process_rsvps() present in
          RSVPBase class.

        :Example:

            attendee = self.get_attendee(rsvp)

        **See Also**
            .. seealso:: process_rsvps() method in RSVPBase class inside
            social_network_service/rsvp/base.py for more insight.

        :return: attendee object which contains data about the candidate
        """
        try:
            data = self.graph.get_object('v2.4/' + rsvp['id'],
                                         fields='first_name, last_name, name, '
                                                'email, location, address, link, picture')
        except facebook.GraphAPIError as error:
            error_message = "Couldn't get Facebook's attendee info. %s" % error.message
            log_exception({'user_id': self.user.id,
                          'error': error_message})
            raise
        if 'location' in data:
            try:
                location = self.graph.get_object('v2.4/'
                                                 + data['location']['id'],
                                                 fields='location')
            except facebook.GraphAPIError as error:
                error_message = " Couldn't get location info (Facebook). %s" % error.message
                log_exception({'user_id': self.user.id,
                               'error': error_message})
                raise
            if 'location' in location:
                location = location['location']
        else:
            location = {}
        if data:
            try:
                attendee = Attendee()
                attendee.first_name = data.get('first_name', '')
                attendee.last_name = data.get('last_name', '')
                attendee.full_name = data.get('name', '')
                attendee.email = data.get('email', '')
                attendee.city = location.get('city', '')
                attendee.country = location.get('country', '')
                attendee.latitude = location.get('latitude')
                attendee.longitude = location.get('longitude')
                attendee.zip = location.get('zip')
                attendee.profile_url = data.get('link', '')
                # TODO also check in following if 'data' and 'url' keys are there as well
                attendee.picture_url = data['picture']['data']['url'] if 'picture' in data else ''
                attendee.gt_user_id = self.user.id
                attendee.social_network_id = self.social_network.id
                attendee.vendor_rsvp_id = rsvp['id']  # we are using profile_id
                # here as we do not have any rsvp_id for this vendor
                #TODO cannot we do datetime.now() for added_time
                attendee.added_time = ' '
                attendee.vendor_img_link = "<img class='pull-right' " \
                                           "style='width:60px;height:30px' " \
                                           "src='/web/static/images/activities/facebook_logo.png'/>"
                vendor_event_id = rsvp['vendor_event_id']
                if rsvp['rsvp_status'].strip() == 'attending' \
                        or rsvp['rsvp_status'].strip() == 'maybe':
                    attendee.rsvp_status = 'yes'
                else:
                    attendee.rsvp_status = 'no'
                event = Event.get_by_user_id_social_network_id_vendor_event_id(
                    self.user.id, self.social_network.id, vendor_event_id)
                if event:
                    attendee.event = event
                else:
                    error_message = 'Event is not present in db, VendorEventId is %s' \
                                    % vendor_event_id
                    log_error({'user_id': self.user.id,
                               'error': error_message})
                return attendee
            except Exception as e:
                error_message = e.message
                log_exception({'user_id': self.user.id,
                               'error': error_message})
                raise

