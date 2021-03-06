"""
Here are the models for creating a base campaign. Event, EmailCampaigns, SMS Campaigns or Push Campaigns
needs to be associated with base campaign for new design.
"""
__author__ = 'basit'

# Packages
from datetime import datetime
from contracts import contract
from sqlalchemy.orm import relationship

# Application Specific
from db import db
from event import Event
from email_campaign import EmailCampaign


class BaseCampaign(db.Model):
    __tablename__ = 'base_campaign'
    id = db.Column('id', db.Integer, primary_key=True)
    user_id = db.Column('UserId', db.BIGINT, db.ForeignKey('user.Id', ondelete='CASCADE'))
    name = db.Column('name', db.String(127), nullable=False)
    description = db.Column('description', db.Text(65535))
    added_datetime = db.Column('added_datetime', db.DateTime, default=datetime.utcnow)

    # Relationships
    base_campaign_events = relationship('BaseCampaignEvent', lazy='dynamic', cascade='all, delete-orphan',
                                        passive_deletes=True)
    email_campaigns = relationship('EmailCampaign', lazy='dynamic', cascade='all, delete-orphan',
                                   passive_deletes=True, backref='base_campaign')

    @classmethod
    @contract
    def search_by_id_in_domain(cls, base_campaign_id, domain_id):
        """
        This returns all base campaigns for given name in given domain.
        :param positive base_campaign_id: Id of base campaign
        :param positive domain_id: Id of domain
        """
        from user import User  # This has to be here to avoid circular import
        return cls.query.filter_by(id=base_campaign_id).join(User).filter(User.domain_id == domain_id).first()


class BaseCampaignEvent(db.Model):
    __tablename__ = 'base_campaign_event'
    id = db.Column(db.Integer, primary_key=True)
    base_campaign_id = db.Column('base_campaign_id', db.Integer, db.ForeignKey('base_campaign.id',
                                                                               ondelete='CASCADE'))
    event_id = db.Column('event_id', db.Integer, db.ForeignKey('event.id', ondelete='CASCADE'))
    added_datetime = db.Column('added_datetime', db.DateTime, default=datetime.utcnow)

    # Relationship
    event = relationship('Event', backref='base_campaign_event')
    base_campaign = relationship('BaseCampaign', backref='base_campaign_event')
