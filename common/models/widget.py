__author__ = 'erikfarmer'
from db import db


class WidgetPage(db.Model):
    __tablename__ = 'widget_page'
    id = db.Column('Id', db.Integer, primary_key=True)
    candidate_source_id = db.Column('CandidateSourceId', db.Integer, db.ForeignKey('candidate_source.id'))
    domain_uuid = db.Column('domain_uuid', db.String(127))
    email_source = db.Column('EmailSource', db.String(255))
    page_views = db.Column('PageViews', db.Integer)
    reply_address = db.Column('ReplyAddress', db.String(255))
    request_email_html = db.Column('RequestEmailHtml', db.String)
    request_email_subject = db.Column('RequestEmailSubject', db.String())
    request_email_text = db.Column('RequestEmailText', db.String())
    sign_ups = db.Column('SignUps', db.Integer)
    template_name = db.Column('template_name', db.String(127))
    updated_time = db.Column('updatedTime', db.DateTime)
    url = db.Column('Url', db.String(500))
    user_id = db.Column('UserId', db.Integer, db.ForeignKey('user.id'))
    widget_name = db.Column('WidgetName', db.String(63))
    welcome_email_text = db.Column('WelcomeEmailText', db.String())
    welcome_email_html = db.Column('WelcomeEmailHtml', db.String())
    welcome_email_subject = db.Column('WelcomeEmailSubject', db.String())
