"""
This module contains model classes that are related to push campaign service.

    - PushCampaign
        Used to handle campaign objects for Push Campaign Service

    - PushCampaignBlast
        Every time a campaign is sent, a blast is created which contains stats for that campaign.

    - PushCampaignSend
        When a campaign is sent to a candidate a send entry is created.

    - PushCampaignSmartlist
        Used to associate smartlist with a campaign

    - PushCampaignSendUrlConversion
        When a campaign is send to a candidate, a UrlConversion is created which is associated
        to a campaign send via this table

"""
import datetime
from db import db
from sqlalchemy.orm import relationship
from candidate import Candidate

__author__ = 'Zohaib Ijaz <mzohaib.qc@gmail.com>'


class PushCampaign(db.Model):
    """
    A push campaign has a title/name, body_text and information about campaign start,
    end, frequency etc.
    OneSignal is being used to actually send these campaigns to candidates.
    """
    __tablename__ = 'push_campaign'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50))
    body_text = db.Column(db.String(500))
    url = db.Column(db.String(255))
    scheduler_task_id = db.Column(db.String(50))
    added_datetime = db.column(db.DateTime)
    start_datetime = db.column(db.DateTime)
    end_datetime = db.column(db.DateTime)
    frequency_id = db.Column(db.Integer, db.ForeignKey('frequency.id'))
    user_id = db.Column(db.Integer, db.ForeignKey('user.Id', ondelete='CASCADE'))

    # Relationships

    blasts = relationship('PushCampaignBlast', cascade='all, delete-orphan',
                          passive_deletes=True, backref='campaign', lazy='dynamic')

    smartlists = relationship('PushCampaignSmartlist', cascade='all, delete-orphan',
                              passive_deletes=True, backref='campaign', lazy='dynamic')

    def __repr__(self):
        return "<PushCampaign ( = %r)>" % self.body_text

    @classmethod
    def get_by_user_id(cls, user_id):
        assert isinstance(user_id, (int, long)) and user_id > 0, 'User id is not valid integer'
        return cls.query.filter_by(user_id=user_id).all()

    @classmethod
    def get_by_id_and_user_id(cls, _id, user_id):
        assert isinstance(_id, (int, long)) and _id > 0, 'PushCampaign id is not valid integer'
        assert isinstance(user_id, (int, long)) and user_id > 0, 'User id is not valid integer'
        return cls.query.filter_by(id=_id, user_id=user_id).first()


class PushCampaignBlast(db.Model):
    """
    Every time a campaign is sent to some candidates, a blast entry is created which
    contains campaign's stats.
    """
    __tablename__ = 'push_campaign_blast'
    id = db.Column(db.Integer, primary_key=True)
    sends = db.Column(db.Integer, default=0)
    clicks = db.Column(db.Integer, default=0)
    campaign_id = db.Column(db.Integer, db.ForeignKey('push_campaign.id', ondelete='CASCADE'))
    updated_time = db.Column(db.TIMESTAMP, default=datetime.datetime.now())

    # Relationships
    blast_sends = relationship('PushCampaignSend', cascade='all, delete-orphan',
                               passive_deletes=True, backref='blast', lazy='dynamic')

    def __repr__(self):
        return "<PushCampaignBlast (Sends: %s, Clicks: %s)>" % (self.sends, self.clicks)


class PushCampaignSend(db.Model):
    """
    When a campaign is sent to a candidate, a send entry is created which information like
    candidate_id, send datetime and associated campaign.
    """
    __tablename__ = 'push_campaign_send'
    id = db.Column(db.Integer, primary_key=True)
    candidate_id = db.Column(db.Integer, db.ForeignKey('candidate.Id', ondelete='CASCADE'))
    sent_datetime = db.Column(db.DateTime, default=datetime.datetime.now())
    blast_id = db.Column(db.Integer, db.ForeignKey("push_campaign_blast.id", ondelete='CASCADE'),
                         nullable=False)

    # Relationships
    push_campaign_sends_url_conversions = relationship('PushCampaignSendUrlConversion',
                                                       cascade='all,delete-orphan',
                                                       passive_deletes=True,
                                                       backref='send')

    def __repr__(self):
        return "<PushCampaignSend (candidate_id: %s,  sent_datetime: %s)>" \
               % (self.candidate_id, self.sent_datetime)


class PushCampaignSmartlist(db.Model):
    """
    PushCampaignSmartlist associates a smartlist to a push campaign.
    """
    __tablename__ = 'push_campaign_smartlist'
    id = db.Column(db.Integer, primary_key=True)
    smartlist_id = db.Column(db.Integer, db.ForeignKey("smart_list.Id", ondelete='CASCADE'),
                             nullable=False)
    campaign_id = db.Column(db.Integer, db.ForeignKey("push_campaign.id", ondelete='CASCADE'), nullable=False)
    updated_datetime = db.Column(db.TIMESTAMP, default=datetime.datetime.now())

    def __repr__(self):
        return '<PushCampaignSmartlist (id = %s, smartlist_id: %s)>' % (self.id, self.smartlist_id)

    @classmethod
    def get_by_campaign_id(cls, campaign_id):
        assert isinstance(campaign_id, (int, long)) and campaign_id > 0, \
            'PushCampaign Id should be a valid positive number'
        return cls.query.filter_by(campaign_id=campaign_id).all()

    @classmethod
    def get_by_campaign_id_and_smartlist_id(cls, campaign_id, smartlist_id):
        assert isinstance(campaign_id, (int, long)) and campaign_id > 0, \
            'PushCampaign Id should be a valid positive number'
        assert isinstance(smartlist_id, (int, long)) and smartlist_id > 0, \
            'Smartlist Id should be a valid positive number'
        return cls.query.filter_by(campaign_id=campaign_id,
                                   smartlist_id=smartlist_id).first()


class PushCampaignSendUrlConversion(db.Model):
    """
    PushCampaignSendUrlConversion associates push campaign send to UrlConversion object.
    """
    __tablename__ = 'push_campaign_send_url_conversion'
    id = db.Column(db.Integer, primary_key=True)
    send_id = db.Column(db.Integer,
                        db.ForeignKey("push_campaign_send.id", ondelete='CASCADE'),
                        nullable=False)
    url_conversion_id = db.Column(db.Integer,
                                  db.ForeignKey("url_conversion.Id", ondelete='CASCADE'),
                                  nullable=False)

    def __repr__(self):
        return '<PushCampaignSendUrlConversion (id = %s , send_id = %s)>' % (self.id, self.send_id)

    @classmethod
    def get_by_campaign_send_id_and_url_conversion_id(cls,
                                                      campaign_send_id,
                                                      url_conversion_id):
        assert campaign_send_id, 'No campaign_send_id given'
        assert url_conversion_id, 'No url_conversion_id given'
        return cls.query.filter(
            push_campaign_send_id=campaign_send_id,
            url_conversion_id=url_conversion_id
        ).first()

    @classmethod
    def get_by_campaign_send_id(cls, campaign_send_id):
        assert campaign_send_id, 'No campaign_send_id given'
        return cls.query.filter_by(push_campaign_send_id=campaign_send_id).first()
