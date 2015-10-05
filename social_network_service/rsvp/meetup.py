from datetime import datetime, timedelta
from common.models.event import Event
from base import RSVPBase
from social_network_service.utilities import http_request, Attendee, \
    milliseconds_since_epoch_to_dt, log_exception, log_error


class Meetup(RSVPBase):
    """
    Here we implement the code related to RSVPs of meetup event
    """
    def __init__(self, *args, **kwargs):
        super(Meetup, self).__init__(*args, **kwargs)
        self.start_date = kwargs.get('start_date') or (datetime.now() - timedelta(days=90))
        self.end_date = kwargs.get('end_date') or (datetime.now() + timedelta(days=90))
        self.start_date_dt = self.start_date
        self.end_date_dt = self.end_date

    def get_rsvps(self, event):
        """
        Here is the functionality of getting rsvp for an Meetup Event.
        :param event:
        :return:
        """
        rsvps = []
        social_network_id = event.social_network_id
        assert social_network_id is not None
        events_url = self.api_url + '/rsvps/?sign=true&page=100'
        params = {'event_id': event.social_network_event_id}
        response = http_request('GET', events_url, params=params, headers=self.headers,
                                user_id=self.user.id)
        if response.ok:
            data = response.json()
            rsvps.extend(data['results'])
            # next_url determines the pagination, this variable keeps
            # appearing in response if there are more pages and stops
            # showing when there are no more. We have almost the same
            # code for events' pagination, might consolidate it.
            next_url = data['meta']['next'] or None
            while next_url:
                # attach the key before sending the request
                response = http_request('GET', next_url + '&sign=true',
                                        user_id=self.user.id)
                if response.ok:
                    data = response.json()
                    rsvps.extend(data['results'])
                    next_url = data['meta']['next'] or None
                    if not next_url:
                        break
            return rsvps
        # TODO why not check for other status
        elif response.status_code == 401:
            # This is the error code for Not Authorized user(Expired Token)
            # if this error code occurs, we return None and RSVPs are not
            # processed further
            return None

    def get_attendee(self, rsvp):
        """
        RSVP data return from Meetup looks like
        {
                'group': {
                    'group_lat': 24.860000610351562, 'created': 1439953915212,
                    'join_mode': 'open', 'group_lon': 67.01000213623047,
                    'urlname': 'Meteor-Karachi', 'id': 17900002
                }, 'created': 1438040123000, 'rsvp_id': 1562651661, 'mtime': 1438040194000,
                'event': {
                    'event_url': 'http://www.meetup.com/Meteor-Karachi/events/223588917/',
                    'time': 1440252000000, 'name': 'Welcome to Karachi - Meteor', 'id': '223588917'
                }, 'member': {
                    'name': 'kamran', 'member_id': 190405794
                }, 'guests': 1, 'member_photo': {
                    'thumb_link':
                    'http://photos3.meetupstatic.com/photos/member/c/b/1/0/thumb_248211984.jpeg',
                    'photo_id': 248211984, 'highres_link':
                    'http://photos3.meetupstatic.com/photos/member/c/b/1/0/highres_248211984.jpeg',
                    'photo_link':
                    'http://photos3.meetupstatic.com/photos/member/c/b/1/0/member_248211984.jpeg'
                }, 'response': 'yes'
        }
        So we will get the member data and issue a member call to get more info
        about member so we can later save him as a candidate
        :param rsvp:
        :return:
        """
        events_url = self.api_url + '/member/' \
                     + str(rsvp['member']['member_id']) \
                     + '?sign=true'
        response = http_request('GET', events_url, headers=self.headers,
                                user_id=self.user.id)
        attendee = None
        if response.ok:
            try:
                data = response.json()
                attendee = Attendee()
                attendee.first_name = data['name'].split(" ")[0]
                if len(data['name'].split(" ")) > 1:
                    attendee.last_name = data['name'].split(" ")[1]
                else:
                    attendee.last_name = ' '
                attendee.full_name = data['name']
                attendee.city = data['city']
                attendee.email = ''
                attendee.country = data['country']
                attendee.profile_url = data['link']
                # attendee.picture_url = data['photo']['photo_link']
                attendee.gt_user_id = self.user.id
                attendee.social_network_id = self.social_network_id
                attendee.rsvp_status = rsvp['response']
                attendee.vendor_rsvp_id = rsvp['rsvp_id']
                attendee.vendor_img_link = "<img class='pull-right' " \
                                           "style='width:60px;height:30px'" \
                                           " src='/web/static/images" \
                                           "/activities/meetup_logo.png'/>"
                # get event from database
                social_network_event_id = rsvp['event']['id']
                epoch_time = rsvp['created']
                dt = milliseconds_since_epoch_to_dt(epoch_time)
                attendee.added_time = dt
                assert social_network_event_id is not None
                event = Event.get_by_user_id_social_network_id_vendor_event_id(
                    self.user.id, self.social_network_id, social_network_event_id)
                if event:
                    attendee.event = event
                else:
                    error_message = 'Event is not present in db, VendorEventId is %s' \
                                    % social_network_event_id
                    log_error({'user_id': self.user.id,
                               'error': error_message})
            except Exception as e:
                error_message = e.message
                log_exception({'user_id': self.user.id,
                               'error': error_message})
                # TODO should we not raise
            return attendee
