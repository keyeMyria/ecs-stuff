"""
This module contains SmsCampaignBase class inherited from CampaignBase.
This is used to send sms campaign to candidates.
This implements abstract methods of CampaignBase class and defines its own
methods like
    - process_link_in_body_text()
    - transform_body_text()
    - create_activity()
- send_sms() etc.
"""

# Standard Library
import json

# Application Specific
from sms_campaign_service import logger
from sms_campaign_service.config import REDIRECT_URL, CAMPAIGN_SMS_SEND, CAMPAIGN_SEND, \
    ACTIVITY_SERVICE_API_URL, AUTH_HEADER, PHONE_LABEL_ID
from sms_campaign_service.common.models.user import UserPhone
from sms_campaign_service.common.models.misc import UrlConversion
from sms_campaign_service.common.models.candidate import Candidate
from sms_campaign_service.common.models.smart_list import SmartListCandidate
from sms_campaign_service.common.models.sms_campaign import SmsCampaign,\
    SmsCampaignSend, SmsCampaignBlast, SmsCampaignSmartList, SmsCampaignSendUrlConversion
from sms_campaign_service.common.utils.campaign_utils import CampaignBase
from sms_campaign_service.utilities import TwilioSMS, search_link_in_text, url_conversion
from social_network_service.utilities import http_request


class SmsCampaignBase(CampaignBase):
    """
    - This is the base class for sending sms campaign to candidates. It uses
        Twilio API to send sms.

    - This is inherited from CampaignBase defined inside
        flask_common/common/utils/campaign_utils.py. It implements abstract
        methods of base class and defines its own methods also.

    This class contains following methods:

    * __init__():
        This method is called by creating the class object.

        - It takes "user_id" as keyword argument.
        - It calls super class __init__ to set user_id.
        - It then gets the user_phone row from "user_phone" db table using
            provided "user_id".

    * save(self, mode, form_data):
        This method is used to save the campaign in db table 'sms_campaign' and
        returns the ID of fresh record in db.

    * get_campaign_data(self):
        This will basically get the campaign data from UI and separate it from
        scheduling data.

    * process_send(self, campaign_id=None):
        This method is used send the campaign to candidates.

    * get_candidates(smart_list_id): [static]
        This method gets the candidates associated with the given smart_list_id.
        It may search candidates in database/cloud.

    * process_link_in_body_text(self):
        If "body_text" contains any link in it, then we need to transform the
        "body_text" by replacing long url with shorter version using Google's Shorten
        URL API. If body text does does not contain any link, it returns the body_text
        as it is.

    * transform_body_text(self, link_in_body_text, short_url):
        This replaces the original URL present in "body_text" with the shorted URL.

    * save_or_update_url_conversion(link_in_body_text, source_url=None, hit_count=0): [static]
        Here we save/update record of url_conversion in db table "url_conversion".

    * send_sms_campaign_to_candidates(self, candidates, sends=0):
        This does the sending part and update "sms_campaign_blast" and "sms_campaign_send".

    * create_or_update_sms_send_url_conversion(campaign_send_id, url_conversion_id): [static]
        This adds an entry in db table "sms_campaign_send_url_conversion" for
        each sms send.

    * create_or_update_sms_campaign_blast(campaign_id=None, send=0, clicks=0, replies=0): [static]
        For each campaign, here we create/update stats of that particular campaign.

    * send_sms(self, candidate_phone_value):
        This finally sends the sms to candidate using Twilio API.

    * create_or_update_sms_campaign_send(campaign_blast_id=None,
                                        candidate_id=None, sent_time=None): [static]
        For each sms, send, here we add an entry that abc campaign has been sent to xyz candidate
        at this time.

    * create_sms_send_activity(self, candidate, source_id=None):
        Here we set params and type to be saved in db table 'Activity' for each sent sms.

    * create_sms_campaign_activity(self, num_candidates):
        Once the campaign has been sent to all candidates, here we set params and type
        to be saved in db table 'Activity' that campaign has been sent to (say)
        40(num_candidates) candidates.

    * create_activity(self, type_=None, source_table=None, source_id=None, params=None):
        This makes HTTP POST call to "activity_service" to create activity in database.

    - An example of sending campaign to candidates will be like this.
        :Example:

        1- Create class object
            from sms_campaign_service.sms_campaign_base import SmsCampaignBase
            camp_obj = SmsCampaignBase(user_id=1)

        2- Call method process_send with campaign_id
            camp_obj.process(campaign_id=1)

    **See Also**
        .. see also:: CampaignBase class in flask_common/common/utils/campaign_utils.py.
    """

    def __init__(self,  *args, **kwargs):
        # sets the user_id
        super(SmsCampaignBase, self).__init__(*args, **kwargs)
        self.user_phone = UserPhone.get_by_user_id(self.user_id)
        self.modified_body_text = None
        self.sms_campaign_blast_id = None
        self.url_conversion_id = None

    @staticmethod
    def save(self, form_data):
        """
        This saves the campaign in database table sms_campaign
        :return:
        """
        campaign_data = self.get_campaign_data(form_data)
        pass

    @staticmethod
    def get_campaign_data(self):
        """
        This will get the data from the UI for sms campaign.
        :return:
        """
        pass

    def process_send(self, campaign_id=None):
        """
        This does the following steps to send campaign to candidates.

        1- Transform the body text to be sent in sms, add entry in
            url_conversion and sms_campaign_url_conversion db tables.
        2- Get selected smart lists for the campaign to be sent from sms_campaign_smart_list.
        3- Loop over all the smart lists and do the followings:

            3-1- Get candidates and their phone number(s) to which we need to send the sms.
            3-2- Create sms campaign blast
            3-3- Loop over list of candidate_ids found in step-3-1 and do the followings:

                3-3-1- Send sms
                3-3-2- Create sms campaign send
                3-3-3- Update sms campaign blast
                3-3-4- Add activity (%(candidate_name)s received sms of campaign %(campaign_name)s")
        4- Add activity (Campaign %(campaign_name)s was sent to %(num_candidates)s candidates")
        :Example:

            1- Create class object
                from sms_campaign_service.sms_campaign_base import SmsCampaignBase
                camp_obj = SmsCampaignBase(user_id=1)

            2- Call method process_send with campaign_id
                camp_obj.process(campaign_id=1)
        :return:
        """
        if campaign_id:
            logger.debug('process_send: Campaign(id:%s) is being sent.' % campaign_id)
            self.campaign = SmsCampaign.get_by_campaign_id(campaign_id)
            self.body_text = self.campaign.sms_body_text.strip()

            # Transform body text to be sent in sms
            self.process_link_in_body_text()
            assert self.modified_body_text

            # Get smart_lists of this campaign
            smart_lists = SmsCampaignSmartList.get_by_campaign_id(self.campaign.id)
            all_candidates = []
            for smart_list in smart_lists:
                # get candidates associated with smart list
                candidates = self.get_candidates(smart_list.id)
                if candidates:
                    all_candidates.extend(candidates)
                else:
                    logger.error('process_send: No Candidate found. Smart list id is %s'
                                 % smart_list.id)
            if all_candidates:
                logger.debug('process_send: Campaign(id:%s) will be sent to %s candidate(s)'
                             % (campaign_id, len(all_candidates)))
                sends_total = 0
                # create sms campaign blast
                self.sms_campaign_blast_id = self.create_or_update_sms_campaign_blast(
                    campaign_id=self.campaign.id,
                    sends=sends_total)
                if all_candidates:
                    sends_total += self.send_sms_campaign_to_candidates(all_candidates,
                                                                        sends=0)
                self.create_campaign_send_activity(sends_total) if sends_total else ''
                logger.debug('process_send: Campaign(id:%s) has been sent to %s candidate(s).'
                             % (campaign_id, sends_total))
            else:
                logger.error('process_send: No Candidate associated to campaign(id:%s)'
                             % self.campaign.id)
        else:
            logger.error('process_send: Campaign id is not given.')

    @staticmethod
    def get_candidates(smart_list_id):
        """
        This will get the candidates associated to a provided smart list.

        :param smart_list_id: id of smart list.
        :type smart_list_id: int
        :return: Returns array of candidates in the campaign's smart_lists.
        :rtype: list

        :Example:
                SmsCampaignBase.get_candidates(1)

        **See Also**
        .. see also:: process_send() method in SmsCampaignBase class.
        """
        # get candidate ids
        records = SmartListCandidate.get_by_smart_list_id(smart_list_id)
        candidates = [Candidate.get_by_id(record.candidate_id) for record in records]
        return candidates

    def process_link_in_body_text(self):
        """
        - Once we have the body text of sms to be sent via sms campaign,
            we check if it contains any link in it.
            If it has any link, we do the followings:

                1- Save that link in db table "url_conversion".
                2- Checks if the db record has source url or not. If it has no source url,
                   we convert the url(to redirect to our app) into shortened url and update
                   the db record. Otherwise we move on to transform body text.
                3. Replace the link in original body text with the shortened url
                    (which we created in step 2)
                4. Return the updated body text

            Otherwise we save the body text in self.modified_body_text

        **See Also**
        .. see also:: process_send() method in SmsCampaignBase class.
        """
        logger.debug('process_link_in_body_text: Processing any link present in sms_body_text. '
                     'Campaign id is %s' % self.campaign.id)
        link_in_body_text = search_link_in_text(self.body_text)
        if len(link_in_body_text) == 1:
            # We have only one link in body text which needs to shortened.
            self.url_conversion_id = self.save_or_update_url_conversion(link_in_body_text[0])
            url_conversion_record = UrlConversion.get_by_id(self.url_conversion_id)
            if not url_conversion_record.source_url:
                short_url, long_url = url_conversion(REDIRECT_URL +
                                                     '?campaign_id=%s&url_conversion_id=%s'
                                                     % (self.campaign.id, self.url_conversion_id))
                self.save_or_update_url_conversion(link_in_body_text[0], source_url=long_url)
            else:
                short_url = url_conversion_record.source_url
            self.modified_body_text = self.transform_body_text(link_in_body_text[0], short_url)
        elif len(link_in_body_text) > 1:
            # Got multiple links in body text
            logger.info('Got %s links in body text. Body text is %s'
                        % (len(link_in_body_text), self.body_text))
        else:
            # No link is present in body text
            self.modified_body_text = self.body_text

    def transform_body_text(self, link_in_body_text, short_url):
        """
        - This replaces the url provided in "body_text" with the "shortened url"
            to be sent via sms campaign.

        :param link_in_body_text: link present in body text
        :param short_url: shortened url
        :type short_url: str
        :return: transformed body text to be sent via sms campaign
        :rtype: str

        **See Also**
        .. see also:: process_link_in_body_text() method in SmsCampaignBase class.
        """
        text_split = self.body_text.split(' ')
        index = 0
        for word in text_split:
            if word == link_in_body_text:
                text_split[index] = short_url
                break
            index += 1
        return ' '.join(text_split)

    @staticmethod
    def save_or_update_url_conversion(link_in_body_text, source_url=None, hit_count=0):
        """
        - Here we save the source_url(provided in body text) and the shortened_url
            to redirect to our endpoint in db table "url_conversion".

        :param link_in_body_text: link present in body text
        :param source_url: shortened url of the link present in body text
        :param hit_count: Count of hits
        :type link_in_body_text: str
        :type source_url: str
        :type hit_count: int
        :return: id of the url_conversion record in database
        :rtype: int

        **See Also**
        .. see also:: process_link_in_body_text() method in SmsCampaignBase class.
        """
        data = {'destination_url': link_in_body_text,
                'source_url': source_url if source_url else '',
                'hit_count': hit_count}
        record_in_db = UrlConversion.get_by_destination_url(link_in_body_text)
        if record_in_db:
            record_in_db.update(**data)
            url_conversion_id = record_in_db.id
        else:
            new_record = UrlConversion(**data)
            UrlConversion.save(new_record)
            url_conversion_id = new_record.id
        return url_conversion_id

    def send_sms_campaign_to_candidates(self, candidates, sends=0):
        """
        Once we have the candidates, we iterate them and do the followings:

            1- Get phone number(s) of candidates to which we need to send the sms.
            2- Create sms campaign blast
            3- Loop over list of candidate_ids found in step-3-1 and do the followings:

                3-1- Send sms
                3-2- Create sms campaign send
                3-3- Update sms campaign blast
                3-4- Add activity (%(candidate_name)s received sms of campaign %(campaign_name)s")
        :param candidates: Candidates associated to a smart list
        :param sends: count of sent sms
        :type candidates: list
        :type sends: int
        :return: number of sms sends
        :rtype: int

        **See Also**
        .. see also:: process_send() method in SmsCampaignBase class.
        """
        for candidate in candidates:
            # get candidate phones
            candidate_phones = candidate.candidate_phones
            # filter only mobile numbers
            candidate_mobile_phone = filter(lambda candidate_phone:
                                            candidate_phone.phone_label_id == PHONE_LABEL_ID,
                                            candidate_phones)
            if len(candidate_mobile_phone) == 1:
                # send sms
                message_response = self.send_sms(candidate_mobile_phone[0].value)
                # Create sms_campaign_send
                sms_campaign_send_id = self.create_or_update_sms_campaign_send(
                    campaign_blast_id=self.sms_campaign_blast_id,
                    candidate_id=candidate.id,
                    sent_time=message_response['sent_time'])
                # create sms_send_url_conversion entry
                self.create_or_update_sms_send_url_conversion(sms_campaign_send_id,
                                                              self.url_conversion_id)
                sends += 1
                # update sms campaign blast
                self.create_or_update_sms_campaign_blast(campaign_id=self.campaign.id,
                                                         sends=sends)
                self.create_sms_send_activity(candidate, source_id=sms_campaign_send_id)
            elif len(candidate_mobile_phone) > 1:
                logger.error('process_send: SMS cannot be sent as candidate(id:%s) '
                             'has multiple mobile phone numbers.' % candidate.id)
            else:
                logger.error('process_send: SMS cannot be sent as candidate(id:%s) '
                             'has no phone number associated.' % candidate.id)
        return sends

    @staticmethod
    def create_or_update_sms_campaign_blast(campaign_id=None,
                                            sends=0, clicks=0, replies=0):
        """
        - Here we create sms blast for a campaign. We also use this to update
            record with every new send. This gives the statistics about a campaign.

        :param campaign_id: id of "sms_campaign"
        :param sends: numbers of sends
        :param clicks: number of clicks on a sent sms
        :param replies: number of replies on a sent sms
        :type campaign_id: int
        :type sends: int
        :type clicks: int
        :type replies: int
        :return: id of "sms_campaign_blast" record
        :rtype: int

        **See Also**
        .. see also:: process_send() method in SmsCampaignBase class.

        .. see also:: send_sms_campaign_to_candidates() method in SmsCampaignBase class.
        """
        data = {'sms_campaign_id': campaign_id,
                'sends': sends,
                'clicks': clicks,
                'replies': replies}
        record_in_db = SmsCampaignBlast.get_by_campaign_id(campaign_id)
        if record_in_db:
            record_in_db.update(**data)
            sms_campaign_blast_id = record_in_db.id
        else:
            new_record = SmsCampaignBlast(**data)
            SmsCampaignBlast.save(new_record)
            sms_campaign_blast_id = new_record.id
        return sms_campaign_blast_id

    def send_sms(self, candidate_phone_value):
        """
        - This uses Twilio API to send sms to a given phone number of candidate.

        :param candidate_phone_value: Candidate mobile phone number.
        :type candidate_phone_value: str
        :return: sent message object
        :rtype: dict

        **See Also**
        .. see also:: send_sms_campaign_to_candidates() method in SmsCampaignBase class.
        """
        twilio_obj = TwilioSMS()
        return twilio_obj.send_sms(body_text=self.modified_body_text,
                                   sender_phone=self.user_phone.value,
                                   receiver_phone=candidate_phone_value)

    @staticmethod
    def create_or_update_sms_campaign_send(campaign_blast_id=None,
                                           candidate_id=None, sent_time=None):
        """
        - Here we add an entry in "sms_campaign_send" db table for each sms send.

        :param campaign_blast_id: id of sms_campaign_blast
        :param candidate_id: id of candidate to which sms is supposed to be sent
        :param sent_time: Time of sent sms
        :type campaign_blast_id: int
        :type candidate_id: int
        :type sent_time: datetime
        :return: id of "sms_campaign_send" record
        :rtype: int

        **See Also**
        .. see also:: send_sms_campaign_to_candidates() method in SmsCampaignBase class.
        """
        data = {'sms_campaign_blast_id': campaign_blast_id,
                'candidate_id': candidate_id,
                'sent_time': sent_time}
        record_in_db = SmsCampaignSend.get_by_blast_id_and_candidate_id(campaign_blast_id,
                                                                        candidate_id)
        if record_in_db:
            record_in_db.update(**data)
            sms_campaign_send_id = record_in_db.id
        else:
            new_record = SmsCampaignSend(**data)
            SmsCampaignSend.save(new_record)
            sms_campaign_send_id = new_record.id
        return sms_campaign_send_id

    @staticmethod
    def create_or_update_sms_send_url_conversion(campaign_send_id, url_conversion_id):
        """
        - For each sms send, here we add an entry in db table "sms_campaign_send_url_conversion"
            db table.

        :param campaign_send_id: id of campaign_send record
        :param url_conversion_id: id of url_conversion record

        **See Also**
        .. see also:: send_sms_campaign_to_candidates() method in SmsCampaignBase class.
        """
        data = {'sms_campaign_send_id': campaign_send_id,
                'url_conversion_id': url_conversion_id}
        record_in_db = SmsCampaignSendUrlConversion.get_by_campaign_sned_id_and_url_conversion_id(
            campaign_send_id, url_conversion_id)
        if record_in_db:
            record_in_db.update(**data)
        else:
            new_record = SmsCampaignSendUrlConversion(**data)
            SmsCampaignSendUrlConversion.save(new_record)

    def create_sms_send_activity(self, candidate, source_id=None):
        """
        - Here we set "params" and "type" of activity to be stored in db table "Activity"
            for each send.

        :param candidate: Candidate row
        :param source_id: id of source
        :type candidate: models.candidate.Candidate
        :type source_id: int
        :return:

        **See Also**
        .. see also:: send_sms_campaign_to_candidates() method in SmsCampaignBase class.
        """
        params = {'candidate_name': candidate.first_name + ' ' + candidate.last_name,
                  'campaign_name': self.campaign.name}
        self.create_activity(type_=CAMPAIGN_SMS_SEND,
                             source_id=source_id,
                             source_table='sms_campaign_send',
                             params=params)

    def create_campaign_send_activity(self, num_candidates):
        """
        - Here we set "params" and "type" of activity to be stored in db table "Activity"
            for Campaign sent.

        :param num_candidates: number of candidates to which campaign is sent
        :type num_candidates: int

        **See Also**
        .. see also:: send_sms_campaign_to_candidates() method in SmsCampaignBase class.
        """
        params = {'campaign_name': self.campaign.name,
                  'num_candidates': num_candidates}
        self.create_activity(type_=CAMPAIGN_SEND,
                             source_id=self.campaign.id,
                             source_table='sms_campaign',
                             params=params)

    def create_activity(self, type_=None, source_table=None, source_id=None, params=None):
        """
        - Once we have all the parameters to save the activity, we call "activity_service"'s
            endpoint /activities/ with HTTP POST call to save the activity in db.

        :param type_: type of activity
        :param source_table: source table name of activity
        :param source_id: source id of activity
        :param params: params to store for activity
        :type type_; int
        :type source_table: str
        :type source_id: int
        :type params: dict

        **See Also**
        .. see also:: send_sms_campaign_to_candidates() method in SmsCampaignBase class.
        """
        data = {'source_table': source_table,
                'source_id': source_id,
                'type': type_,
                'user_id': self.user_id,
                'params': json.dumps(params)}
        # POST call to activity service to create activity
        url = ACTIVITY_SERVICE_API_URL + '/activities/'
        http_request('POST', url,
                     headers=AUTH_HEADER,
                     data=data,
                     user_id=self.user_id)

if __name__ == '__main__':
    camp_obj = SmsCampaignBase(user_id=1)
    camp_obj.process_send(campaign_id=1)
