"""
This module contains SmsCampaignBase class inherited from CampaignBase.
This is used to send sms campaign to candidates.
This implements abstract methods of CampaignBase class and defines its own
methods like
     - save()
     - buy_twilio_mobile_number()
     - create_or_update_user_phone()
     - process_send()
     - process_link_in_body_text()
     - transform_body_text()
     - send_sms_campaign_to_candidate()
     - send_sms()
     - process_url_redirect()
     - process_candidate_reply() etc.
"""

# Standard Library
from datetime import datetime

# Application Specific
from sms_campaign_service import logger
from sms_campaign_service.common.models.misc import UrlConversion
from sms_campaign_service.common.models.user import UserPhone, User
from sms_campaign_service.common.error_handling import ResourceNotFound
from sms_campaign_service.common.utils.campaign_utils import CampaignBase
from sms_campaign_service.config import SMS_URL_REDIRECT, PHONE_LABEL_ID, TWILIO, IS_DEV
from sms_campaign_service.common.models.candidate import PhoneLabel, Candidate, \
    CandidatePhone
from sms_campaign_service.common.models.sms_campaign import SmsCampaign,\
    SmsCampaignSend, SmsCampaignBlast, SmsCampaignSmartList, SmsCampaignSendUrlConversion, \
    SmsCampaignReply
from sms_campaign_service.utilities import TwilioSMS, search_link_in_text, url_conversion
from sms_campaign_service.common.utils.activity_utils import CAMPAIGN_SMS_CLICK,\
    CAMPAIGN_SMS_REPLY, CAMPAIGN_SMS_SEND, CAMPAIGN_SEND, CAMPAIGN_SMS_CREATE


class SmsCampaignBase(CampaignBase):
    """
    - This is the base class for sending sms campaign to candidates and  to keep track
        of their responses. It uses Twilio API to send sms.

    - This is inherited from CampaignBase defined inside
        flask_common/common/utils/campaign_utils.py. It implements abstract
        methods of base class and defines its own methods also.

    This class contains following methods:

    * __init__()
        This method is called by creating the class object.

        - It takes "user_id" as keyword argument.
        - It calls super class __init__ to set user_id.
        - It then gets the user_phone row from "user_phone" db table using
            provided "user_id".
        - Sets total_sends to 0.

    *  get_all_campaigns(self)
       This gets all the campaigns created by current user

    *  delete_all_campaigns(self)
        This deletes all the campaigns of a user from database

    * save(self, form_data)
        This method is used to save the campaign in db table 'sms_campaign' and
        returns the ID of fresh record in db.

    * campaign_create_activity(self, sms_campaign)
        This creates activity that SMS campaign created by xyz user

    * buy_twilio_mobile_number(self, phone_label_id=None)
        To send sms_campaign, we need to reserve a unique number for each user.
        This method is used to reserve a unique number for getTalent user.

    * create_or_update_user_phone(self, phone_number, phone_label_id=None)
        This method is used to create/update user_phone record.

    * process_send(self, campaign_id=None)
        This method is used send the campaign to candidates.

    * process_link_in_body_text(self, candidate_id)
        If "body_text" contains any link in it, then we need to transform the
        "body_text" by replacing long url with shorter version using Google's Shorten
        URL API. If body text does does not contain any link, it returns the body_text
        as it is.

    * transform_body_text(self, link_in_body_text, short_url)
        This replaces the original URL present in "body_text" with the shorted URL.

    * send_sms_campaign_to_candidate(self, candidate)
        This does the sending part and update "sms_campaign_blast" and "sms_campaign_send".

    * create_or_update_sms_campaign_blast(campaign_id=None, send=0, clicks=0, replies=0,
                            sends_update=False, clicks_update=False, replies=False): [static]
        For each campaign, here we create/update stats of that particular campaign.

    * send_sms(self, candidate_phone_value)
        This finally sends the sms to candidate using Twilio API.

    * create_or_update_sms_campaign_send(campaign_blast_id=None,
                                        candidate_id=None, sent_time=None): [static]
        For each sms, send, here we add an entry that abc campaign has been sent to xyz candidate
        at this time.

    * create_or_update_sms_send_url_conversion(campaign_send_id, url_conversion_id): [static]
        This adds an entry in db table "sms_campaign_send_url_conversion" for
        each sms send.

    * create_sms_send_activity(self, candidate, source_id=None)
        Here we set params and type to be saved in db table 'Activity' for each sent sms.
        Activity will appear as
            "SMS Campaign <b>%(campaign_name)s</b> has been sent to %(candidate_name)s.".

    * create_campaign_send_activity(self, num_candidates)
        Once the campaign has been sent to all candidates, here we set params and type
        to be saved in db table 'Activity' that campaign has been sent to (say)
        40(num_candidates) candidates.
        Activity will appear as "%(campaign_name)s has been sent to %(num_candidates)s.".

    * process_url_redirect(self, campaign_id=None, url_conversion_id=None)
        When a candidate clicks on the link present in the body text of sms, this code is
        hit and it updates "clicks" in "sms_campaign_blast" table and "hit_count" in
        "url_conversion" table. Finally it returns the destination url to redirect the
        candidate to actual link provided by recruiter.

    *  create_campaign_url_click_activity(self, candidate)
        If candidate clicks on link present in sms body text, we create an activity,
        Activity will appear as
            "%(candidate_name)s clicked on SMS Campaign <b>%(campaign_name)s</b>."

    * process_candidate_reply(self, candidate)
        When a candidate replies to a recruiter's number, here we do the necessary processing.

    * save_candidate_reply(self, candidate)
        In this method, we save the reply of candidate in db table 'sms_campaign_reply"

    * create_campaign_reply_activity(self, candidate)
        When a candidate replies to a recruiter's phone number, we create an activity that
        "%(candidate_name)s replied <b>%(reply_text)s</b> on SMS campaign %(campaign_name)s.".

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
        """
        Here we set the "user_id" by calling super constructor and "user_phone" by
        calling get_user_phone() method,
        :param args:
        :param kwargs:
        :return:
        """
        # sets the user_id
        super(SmsCampaignBase, self).__init__(*args, **kwargs)
        self.user_phone = self.get_user_phone()
        self.modified_body_text = None
        self.sms_campaign_blast_id = None
        self.url_conversion_id = None
        self.total_sends = 0

    def get_all_campaigns(self):
        """
        This gets all the campaigns created by current user
        :return: all campaigns associated to with user
        :rtype: list
        """
        return SmsCampaign.get_by_user_phone_id(self.user_phone.id)

    def delete_all_campaigns(self):
        """
        This deletes all the campaigns of a user from database table "sms_campaign"
        :return:
        """
        campaigns = self.get_all_campaigns()
        status_list = [SmsCampaign.delete(campaign) for campaign in campaigns]
        if all(status_list):
            return True
        else:
            return False

    def save(self, form_data):
        """
        This saves the campaign in database table sms_campaign in following steps:

            1- Save campaign in database
            2 Create activity that
                "%(user_name)s created an SMS campaign: '%(campaign_name)s'"

        :param form_data: data from UI
        :type form_data: dict
        :return: id of sms_campaign in db
        :rtype: int
        """
        if form_data:
            # Save Campaign in database table "sms_campaign"
            sms_campaign = self.create_or_update_sms_campaign(form_data)
            # Create Activity
            self.campaign_create_activity(sms_campaign)
            return sms_campaign.id
        else:
            logger.error('save: No data received from UI.')

    def create_or_update_sms_campaign(self, sms_campaign_data, campaign_id=None):
        """
        - Here we save/update sms_campaign in db.

        - This method is called from save() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :param sms_campaign_data: data of sms campaign to save
        :param campaign_id: id of "sms_campaign" row, default None
        :type sms_campaign_data: dict
        :type campaign_id: int
        :return: "sms_campaign" row
        :rtype: row

        **See Also**
        .. see also:: save() method in SmsCampaignBase class.
        """
        data = dict(name=sms_campaign_data.get('name'),
                    user_phone_id=self.user_phone.id,
                    sms_body_text=sms_campaign_data.get('sms_body_text'),
                    frequency_id=sms_campaign_data.get('frequency_id'),
                    added_time=datetime.now(),
                    send_time=sms_campaign_data.get('send_time'),
                    stop_time=sms_campaign_data.get('stop_time'))
        if campaign_id:
            try:
                sms_campaign = SmsCampaign.get_by_campaign_id(campaign_id)
            except:
                logger.error('create_or_update_sms_campaign: '
                             'Campaign(id=%s) not found.' % campaign_id)
                raise ResourceNotFound
            for key, value in data.iteritems():
                # update old values with new ones if provided, else preserve old ones.
                data[key] = value if value else getattr(sms_campaign, key)
            sms_campaign.update(**data)
        else:
            sms_campaign = SmsCampaign(**data)
            SmsCampaign.save(sms_campaign)
        return sms_campaign

    def campaign_create_activity(self, source):
        """
        - Here we set "params" and "type" of activity to be stored in db table "Activity"
            for Campaign create.

        - Activity will appear as
           "%(user_name)s created an SMS campaign: '%(campaign_name)s'"

        - This method is called from save() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :param source: "sms_campaign" row
        :type source: row

        **See Also**
        .. see also:: save() method in SmsCampaignBase class.
        """
        # get User row
        user = User.get_by_id(self.user_id)
        # set params
        params = {'user_name': user.name,
                  'campaign_name': source.name}

        self.create_activity(user_id=self.user_id,
                             type_=CAMPAIGN_SMS_CREATE,
                             source_id=source.id,
                             source_table='',
                             params=params)

    def get_user_phone(self):
        """
        Her we check if current user has twilio number in "user_phone" table.
        If user has no twilio number associated, we buy a new number for this user,
        saves it in database and returns it.

        - This method is called from __int__() method of class SmsCampaignBase inside
            sms_campaign_service/sms_campaign_base.py.

        :return: UserPhone row
        """
        phone_label_id = PhoneLabel.phone_label_id_from_phone_label(TWILIO)
        try:
            user_phone = UserPhone.get_by_user_id_and_phone_label_id(self.user_id,
                                                                     phone_label_id)
            assert user_phone.value
            return user_phone
        except:
            # User has no associated twilio number, need to buy one
            logger.debug('get_user_phone: User(id:%s) has no Twilio number '
                         'associated.' % self.user_id)
            return self.buy_twilio_mobile_number(phone_label_id=phone_label_id)

    def buy_twilio_mobile_number(self, phone_label_id=None):
        """
        Here we use Twilio API to first get available numbers by calling
        get_available_numbers() of class TwilioSMS inside utilities.py. We select a number
        from the result of get_available_numbers() and call purchase_twilio_number() to
        buy that number.

        - This method is called from get_user_phone() method of class SmsCampaignBase inside
            sms_campaign_service/sms_campaign_base.py.

        :param phone_label_id: id of phone label
        :type phone_label_id: int
        :return: UserPhone row
        """
        twilio_obj = TwilioSMS()
        available_phone_numbers = twilio_obj.get_available_numbers()
        if available_phone_numbers:
            if IS_DEV:
                # Do not "actually" buy a number.
                number_to_buy = '1234'
            else:
                logger.debug('buy_twilio_mobile_number: Going to buy Twilio number for '
                             'user(id:%s).' % self.user_id)
                number_to_buy = available_phone_numbers[0]
                twilio_obj.purchase_twilio_number(available_phone_numbers[0])
            user_phone = self.create_or_update_user_phone(number_to_buy,
                                                          phone_label_id=phone_label_id)
            return user_phone

    def create_or_update_user_phone(self, phone_number, phone_label_id=None):
        """
        - For each user (recruiter) we need to reserve a unique phone number to send
            sms campaign. Here we create a new user_phone record or update the previous
            record.

        - This method is called from buy_twilio_mobile_number() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :param phone_label_id: id of "phone_label" record
        :param phone_number: The number we want to reserve for user
        :type phone_label_id: int
        :type phone_number: str
        :return: "user_phone" row

        **See Also**
        .. see also:: __int__() method of SmsCampaignBase class.
        """
        data = {'user_id': self.user_id,
                'phone_label_id': phone_label_id,
                'value': phone_number}
        user_phone_row = UserPhone.get_by_user_id_and_phone_label_id(self.user_id,
                                                                     phone_label_id)
        if user_phone_row:
            user_phone_row.update(**data)
        else:
            user_phone_row = UserPhone(**data)
            UserPhone.save(user_phone_row)
        return user_phone_row

    def process_send(self, campaign_id=None):
        """
        :param campaign_id: id of sms_campaign
        :type campaign_id: int
        :return: number of sends
        :rtype: int
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
            logger.debug('process_send: SMS Campaign(id:%s) is being sent.' % campaign_id)
            self.campaign = SmsCampaign.get_by_campaign_id(campaign_id)
            self.body_text = self.campaign.sms_body_text.strip()

            # Get smart_lists of this campaign
            smart_lists = SmsCampaignSmartList.get_by_campaign_id(self.campaign.id)
            all_candidates = []
            for smart_list in smart_lists:
                self.smart_list_id = smart_list.id
                # get candidates associated with smart list
                candidates = self.get_candidates(smart_list_id=smart_list.id)
                if candidates:
                    all_candidates.extend(candidates)
                else:
                    logger.error('process_send: No Candidate found. Smart list id is %s.'
                                 % smart_list.id)
            if all_candidates:
                logger.debug('process_send: SMS Campaign(id:%s) will be sent to %s candidate(s).'
                             % (campaign_id, len(all_candidates)))
                # create sms campaign blast
                self.sms_campaign_blast_id = self.create_or_update_sms_campaign_blast(
                    campaign_id=self.campaign.id)
                self.send_campaign_to_candidates(all_candidates)
                self.create_campaign_send_activity(self.total_sends) if self.total_sends else ''
                logger.debug('process_send: SMS Campaign(id:%s) has been sent to %s candidate(s).'
                             % (campaign_id, self.total_sends))
                return self.total_sends
            else:
                logger.error('process_send: No Candidate associated to SMS campaign(id:%s).'
                             % self.campaign.id)
        else:
            logger.error('process_send: SMS Campaign id is not given.')

    def process_link_in_body_text(self, candidate_id):
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

        - This method is called from process_send() method of class SmsCampaignBase inside
            sms_campaign_service/sms_campaign_base.py.

        **See Also**
        .. see also:: process_send() method in SmsCampaignBase class.
        """
        logger.debug('process_link_in_body_text: Processing any link present in sms_body_text for '
                     'SMS Campaign(id:%s) and Candidate(id:%s)' % (self.campaign.id, candidate_id))
        link_in_body_text = search_link_in_text(self.body_text)
        if len(link_in_body_text) == 1:
            # We have only one link in body text which needs to shortened.
            self.url_conversion_id = self.create_or_update_url_conversion(
                destination_url=link_in_body_text[0])
            # URL to redirect candidates to our end point
            long_url = (SMS_URL_REDIRECT+'?candidate_id={}').format(self.campaign.id,
                                                                    self.url_conversion_id,
                                                                    candidate_id)
            # Use Google's API to shorten the long Url
            short_url = url_conversion(long_url)
            # update the "url_conversion" record
            self.create_or_update_url_conversion(url_conversion_id=self.url_conversion_id,
                                                 source_url=long_url)
            self.modified_body_text = self.transform_body_text(link_in_body_text[0], short_url)
        elif len(link_in_body_text) > 1:
            # Got multiple links in body text
            logger.info('Got %s links in body text. Body text is %s.'
                        % (len(link_in_body_text), self.body_text))
        else:
            # No link is present in body text
            self.modified_body_text = self.body_text

    def transform_body_text(self, link_in_body_text, short_url):
        """
        - This replaces the url provided in "body_text" with the "shortened url"
            to be sent via sms campaign.

        - This method is called from process_link_in_body_text() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :param link_in_body_text: link present in body text
        :param short_url: shortened url to redirect candidate to our app
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

    def send_campaign_to_candidate(self, candidate):
        """
        For each candidate, we do the followings:
            1- Get phone number(s) of candidate to which we need to send the sms.
            2- Send sms
            3- Create sms campaign send
            4- Update sms campaign blast
            5- Add activity (%(candidate_name)s received sms of campaign %(campaign_name)s")

        - This method is called from send_sms_campaign_to_candidates() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :param candidate: Candidate row

        **See Also**
        .. see also:: send_sms_campaign_to_candidates() method in SmsCampaignBase class.
        """
        super(SmsCampaignBase, self).send_campaign_to_candidate(candidate)

        # get candidate phones
        candidate_phones = candidate.candidate_phones
        # filter only mobile numbers
        candidate_mobile_phone = filter(lambda candidate_phone:
                                        candidate_phone.phone_label_id == PHONE_LABEL_ID,
                                        candidate_phones)
        if len(candidate_mobile_phone) == 1:
            # Transform body text to be sent in sms
            self.process_link_in_body_text(candidate.id)
            assert self.modified_body_text
            # send sms
            message_sent_time = self.send_sms(candidate_mobile_phone[0].value)
            # Create sms_campaign_send
            sms_campaign_send_id = self.create_or_update_sms_campaign_send(
                campaign_blast_id=self.sms_campaign_blast_id,
                candidate_id=candidate.id,
                sent_time=message_sent_time)
            # create sms_send_url_conversion entry
            self.create_or_update_sms_send_url_conversion(sms_campaign_send_id,
                                                          self.url_conversion_id)
            # update sms campaign blast
            self.create_or_update_sms_campaign_blast(campaign_id=self.campaign.id,
                                                     sends_update=True)
            self.create_sms_send_activity(candidate, source_id=sms_campaign_send_id)
            self.total_sends += 1
            logger.info('send_sms_campaign_to_candidate: SMS has been sent to candidate(id:%s).'
                        ' Campaign(id:%s).' % (candidate.id, self.campaign.id))
        elif len(candidate_mobile_phone) > 1:
            logger.error('send_sms_campaign_to_candidate: SMS cannot be sent as candidate(id:%s) '
                         'has multiple mobile phone numbers. Campaign(id:%s).'
                         % (candidate.id, self.campaign.id))
        else:
            logger.error('send_sms_campaign_to_candidate: SMS cannot be sent as candidate(id:%s) '
                         'has no phone number associated. Campaign(id:%s).'
                         % (candidate.id, self.campaign.id))

    @staticmethod
    def create_or_update_sms_campaign_blast(campaign_id=None,
                                            sends=0, clicks=0, replies=0,
                                            clicks_update=False, sends_update=False,
                                            replies_update=False):
        """
        - Here we create sms blast for a campaign. We also use this to update
            record with every new send. This gives the statistics about a campaign.

        - This method is called from process_send() and send_sms_campaign_to_candidates()
            methods of class SmsCampaignBase inside
            sms_campaign_service/sms_campaign_base.py.

        :param campaign_id: id of "sms_campaign"
        :param sends: numbers of sends, default 0
        :param clicks: number of clicks on a sent sms, default 0
        :param replies: number of replies on a sent sms, default 0
        :param sends_update: True if sends to be updated ,False otherwise
        :param clicks_update: True if clicks to be updated ,False otherwise
        :param replies_update: True if replies to be updated ,False otherwise
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
        record_in_db = SmsCampaignBlast.get_by_campaign_id(campaign_id)
        data = {'sms_campaign_id': campaign_id,
                'sends': sends,
                'clicks': clicks,
                'replies': replies,
                'sent_time': datetime.now()}
        if record_in_db:
            data['sends'] = record_in_db.sends + 1 if sends_update else record_in_db.sends
            data['clicks'] = record_in_db.clicks + 1 if clicks_update else record_in_db.clicks
            data['replies'] = record_in_db.replies + 1 if replies_update else record_in_db.replies
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

        - This method is called from send_sms_campaign_to_candidates() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :param candidate_phone_value: Candidate mobile phone number.
        :type candidate_phone_value: str
        :return: sent message time
        :rtype: datetime

        **See Also**
        .. see also:: send_sms_campaign_to_candidates() method in SmsCampaignBase class.
        """
        if IS_DEV:
            # Do not "actually" send sms.
            return datetime.now()
        else:
            twilio_obj = TwilioSMS()
            message_response = twilio_obj.send_sms(body_text=self.modified_body_text,
                                                   sender_phone=self.user_phone.value,
                                                   receiver_phone=candidate_phone_value)
            return message_response.date_created

    @staticmethod
    def create_or_update_sms_campaign_send(campaign_blast_id=None,
                                           candidate_id=None, sent_time=None):
        """
        - Here we add an entry in "sms_campaign_send" db table for each sms send.

        - This method is called from send_sms_campaign_to_candidates() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

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

        - This method is called from send_sms_campaign_to_candidates() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

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

        - Activity will appear as
            "SMS Campaign <b>%(campaign_name)s</b> has been sent to %(candidate_name)s."

        - This method is called from send_sms_campaign_to_candidates() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

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
        self.create_activity(user_id=self.user_id,
                             type_=CAMPAIGN_SMS_SEND,
                             source_id=source_id,
                             source_table='sms_campaign_send',
                             params=params)

    def create_campaign_send_activity(self, num_candidates):
        """
        - Here we set "params" and "type" of activity to be stored in db table "Activity"
            for Campaign sent.

        - Activity will appear as "%(campaign_name)s has been sent to %(num_candidates)s".

        - This method is called from send_sms_campaign_to_candidates() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :param num_candidates: number of candidates to which campaign is sent
        :type num_candidates: int

        **See Also**
        .. see also:: send_sms_campaign_to_candidates() method in SmsCampaignBase class.
        """
        params = {'name': self.campaign.name,
                  'num_candidates': num_candidates}
        self.create_activity(user_id=self.user_id,
                             type_=CAMPAIGN_SEND,
                             source_id=self.campaign.id,
                             source_table='sms_campaign',
                             params=params)

    def process_url_redirect(self, campaign_id=None, url_conversion_id=None,
                             candidate_id=None):
        """
        This does the following steps to send campaign to candidates.

        1- Get the "url_conversion" row from db.
        2- Get the "sms_campaign_blast" row from db.
        3- Increase "hit_count" by 1 for "url_conversion" record.
        4- Increase "clicks" by 1 for "sms_campaign_blast" record.
        5- Add activity that abc candidate clicked on xyz campaign.
            "%(candidate_name)s clicked url of campaign %(campaign_name)s"
        6- return the destination url where we want our candidate to be redirected.

        :Example:

            1- Create class object
                from sms_campaign_service.sms_campaign_base import SmsCampaignBase
                camp_obj = SmsCampaignBase(user_id=1)

            2- Call method process_send with campaign_id
                redirection_url = camp_obj.process_url_redirect(campaign_id=1, url_conversion_id=1)

        :param campaign_id: id of sms_campaign
        :param url_conversion_id: id of url_conversion record
        :type campaign_id: int
        :type url_conversion_id: int
        :return: URL where to redirect the candidate
        :rtype: str
        """
        if campaign_id and url_conversion_id:
            logger.debug('process_url_redirect: Processing for URL redirection.')

            # Update sms campaign blast
            self.create_or_update_sms_campaign_blast(campaign_id=campaign_id,
                                                     clicks_update=True)
            # Update hit count
            self.create_or_update_url_conversion(url_conversion_id=url_conversion_id,
                                                 hit_count_update=True)
            # Create Activity
            self.campaign = SmsCampaign.get_by_campaign_id(campaign_id)
            candidate = Candidate.get_by_id(candidate_id)
            self.create_campaign_url_click_activity(candidate)
            # Get Url to redirect candidate to actual url
            url_conversion_row = UrlConversion.get_by_id(url_conversion_id)
            logger.error('process_url_redirect: candidate(id:%s) clicked on sms '
                         'campaign(id:%s)' % (candidate_id, self.campaign.id))
            return url_conversion_row.destination_url
        else:
            logger.error('process_url_redirect: campaign_id or url_conversion_id '
                         'is not provided.')
            return None

    def create_campaign_url_click_activity(self, candidate):
        """
        - Here we set "params" and "type" of activity to be stored in db table "Activity"
            for Campaign URL click.

        - Activity will appear as
            "%(candidate_name)s clicked on SMS Campaign <b>%(campaign_name)s</b>."

        - This method is called from process_url_redirect() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :param candidate: Candidate row

        **See Also**
        .. see also:: process_url_redirect() method in SmsCampaignBase class.
        """
        assert candidate
        params = {'candidate_name': candidate.first_name + ' ' + candidate.last_name,
                  'campaign_name': self.campaign.name}
        self.create_activity(user_id=self.user_id,
                             type_=CAMPAIGN_SMS_CLICK,
                             source_id=self.campaign.id,
                             source_table='sms_campaign',
                             params=params)

    @classmethod
    def process_candidate_reply(cls, reply_data):
        """
        When candidate replies to user'phone number, we do the following at our
            redirected endpoint.

            1- Gets "user_phone" record
            2- Gets "candidate_phone" record
            3- Gets latest campaign sent to given candidate
            4- Gets "sms_campaign_blast" row for "sms_campaign_send" found in step-3
            5- Saves candidate's reply in db table "sms_campaign_reply"
            6- Creates Activity that "abc" candidate has replied "123" to campaign "xyz"
            7- Updates the count of replies in "sms_campaign_blast" by 1

        :param reply_data:
        :type reply_data: dict
        :return:
        """
        candidate_phone_value = reply_data.get('From')
        user_phone_value = reply_data.get('To')
        reply_body_text = reply_data.get('Body')
        if all([candidate_phone_value, user_phone_value]):
            # get "user_phone" row
            user_phone = UserPhone.get_by_phone_value(user_phone_value)
            # get "candidate_phone" row
            candidate_phone = CandidatePhone.get_by_phone_value(candidate_phone_value)
            # get latest campaign send
            sms_campaign_send = SmsCampaignSend.get_by_candidate_id(candidate_phone.candidate_id)
            # get sms campaign blast
            sms_campaign_blast = SmsCampaignBlast.get_by_id(sms_campaign_send.sms_campaign_blast_id)
            # save candidate reply
            sms_campaign_reply = cls.save_candidate_reply(
                campaign_blast_id=sms_campaign_blast.id,
                candidate_phone_id=candidate_phone.id,
                reply_body_text=reply_body_text)
            # create Activity
            cls.create_campaign_reply_activity(sms_campaign_reply,
                                               sms_campaign_blast,
                                               candidate_phone.candidate_id,
                                               user_id=user_phone.user_id)
            # get/update sms campaign blast
            cls.create_or_update_sms_campaign_blast(campaign_id=sms_campaign_blast.sms_campaign_id,
                                                    replies_update=True)
            logger.debug('Candidate(id:%s) replied "%s" to Campaign(id:%s).'
                         % (candidate_phone.candidate_id, reply_body_text,
                            sms_campaign_blast.sms_campaign_id))

    @classmethod
    def save_candidate_reply(cls, campaign_blast_id=None, candidate_phone_id=None,
                             reply_body_text=None):
        """
        - Here we save the reply of candidate in db table "sms_campaign_reply"

        :param campaign_blast_id: id of "sms_campaign_blast" record
        :param candidate_phone_id: id of "candidate_phone" record
        :param reply_body_text: reply_body_text
        :type campaign_blast_id: int
        :type candidate_phone_id: int
        :type reply_body_text: str
        :return:
        """
        data = {'sms_campaign_blast_id': campaign_blast_id,
                'candidate_phone_id': candidate_phone_id,
                'reply_body_text': reply_body_text,
                'added_time': datetime.now()}
        record_in_db = SmsCampaignReply.get_by_blast_id_and_candidate_phone_id(campaign_blast_id,
                                                                               candidate_phone_id)
        if record_in_db:
            record_in_db.update(**data)
            sms_campaign_reply_row = record_in_db
        else:
            sms_campaign_reply_row = SmsCampaignReply(**data)
            SmsCampaignReply.save(sms_campaign_reply_row)
        return sms_campaign_reply_row

    @classmethod
    def create_campaign_reply_activity(cls, sms_campaign_reply, campaign_blast,
                                       candidate_id, user_id=None):
        """
        - Here we set "params" and "type" of activity to be stored in db table "Activity"
            for Campaign reply.

        - Activity will appear as
            "%(candidate_name)s replied <b>%(reply_text)s</b> on SMS campaign %(campaign_name)s.".

        - This method is called from process_candidate_reply() method of class
            SmsCampaignBase inside sms_campaign_service/sms_campaign_base.py.

        :param sms_campaign_reply: "sms_campaign_reply" row
        :param campaign_blast: "sms_campaign_blast" row
        :param candidate_id: id of Candidate
        :type sms_campaign_reply: row
        :type campaign_blast: row
        :type candidate_id: int

        **See Also**
        .. see also:: process_candidate_reply() method in SmsCampaignBase class.
        """
        # get Candidate
        candidate = Candidate.get_by_id(candidate_id)
        campaign = SmsCampaign.get_by_campaign_id(campaign_blast.sms_campaign_id)
        params = {'candidate_name': candidate.first_name + ' ' + candidate.last_name,
                  'reply_text': sms_campaign_reply.reply_body_text,
                  'campaign_name': campaign.name}

        cls.create_activity(user_id=user_id,
                            type_=CAMPAIGN_SMS_REPLY,
                            source_id=sms_campaign_reply.id,
                            source_table='sms_campaign_reply',
                            params=params)
