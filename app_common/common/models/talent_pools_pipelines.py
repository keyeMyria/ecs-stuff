
__author__ = 'ufarooqi'

import json
from db import db
from datetime import datetime, timedelta
from user import Domain, UserGroup, User
from candidate import Candidate
from app_common.common.error_handling import NotFoundError
# 3rd party imports
from sqlalchemy import or_, and_, extract
from sqlalchemy.dialects.mysql import TINYINT


class TalentPool(db.Model):
    __tablename__ = 'talent_pool'
    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column(db.Integer, db.ForeignKey('domain.Id', ondelete='CASCADE'), nullable=False)
    user_id = db.Column(db.BIGINT, db.ForeignKey('user.Id', ondelete='CASCADE'), nullable=False)
    name = db.Column(db.String(50), nullable=False)
    simple_hash = db.Column(db.String(8))
    description = db.Column(db.TEXT)
    added_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    domain = db.relationship('Domain', backref=db.backref('talent_pool', cascade="all, delete-orphan"))
    user = db.relationship('User', backref=db.backref('talent_pool', cascade="all, delete-orphan"))

    def __repr__(self):
        return "<TalentPool (id = %r)>" % self.id

    def get_id(self):
        return unicode(self.id)

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    @classmethod
    def get_talent_pools_in_user_domain(cls, user_id):
        """
        This method returns talent pools in a user's domain
        :param int user_id: User Id
        :rtype: list
        """
        domain_id = User.get_domain_id(user_id)
        return cls.query.filter(cls.domain_id == domain_id).all()


class TalentPoolCandidate(db.Model):
    __tablename__ = 'talent_pool_candidate'
    id = db.Column(db.Integer, primary_key=True)
    talent_pool_id = db.Column(db.Integer, db.ForeignKey('talent_pool.id', ondelete='CASCADE'), nullable=False)
    candidate_id = db.Column(db.BIGINT, db.ForeignKey('candidate.Id', ondelete='CASCADE'), nullable=False)
    added_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_time = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    # Relationships
    candidate = db.relationship('Candidate', backref=db.backref('talent_pool_candidate', cascade="all, delete-orphan"))
    talent_pool = db.relationship('TalentPool',
                                  backref=db.backref('talent_pool_candidate', cascade="all, delete-orphan"))

    def __repr__(self):
        return "<TalentPoolCandidate: (talent_pool_id = {})>".format(self.talent_pool_id)

    @classmethod
    def get(cls, candidate_id, talent_pool_id):
        return cls.query.filter_by(candidate_id=candidate_id, talent_pool_id=talent_pool_id).first()

    @classmethod
    def candidates_added_last_month(cls, user_name, talent_pool_list, user_specific_date, user_id):
        """
        Returns number of candidate added by a user in a talent pool during a specific time interval
        :param str|None user_name: User name
        :param int user_id: User Id
        :param list|None talent_pool_list: Talent pool name
        :param datetime|None|basestring user_specific_date: Datetime this should be later than or equal to updated_time
        or added_time
        :rtype: int|str
        """
        if isinstance(user_specific_date, datetime):
            if user_name and talent_pool_list:
                users = User.get_by_name(user_id, user_name)
                if users:
                    user = users[0]
                    return cls.query.filter(cls.talent_pool_id == TalentPool.id) \
                        .filter(or_((cls.added_time >= user_specific_date),
                                    (cls.updated_time >= user_specific_date))).filter(
                        and_(TalentPool.user_id == user.id, TalentPool.name.in_(talent_pool_list))).distinct().count()
                raise NotFoundError
            if user_name and talent_pool_list is None:
                user = User.get_by_id(user_id)
                if user:
                    return cls.query.filter(cls.talent_pool_id == TalentPool.id) \
                        .filter(or_((cls.added_time >= user_specific_date), (
                         cls.updated_time >= user_specific_date))). \
                        filter(User.id == TalentPool.user_id). \
                        filter(and_(or_(User.first_name == user_name, User.last_name == user_name), TalentPool.domain_id == user.domain_id)). \
                        distinct().count()
            if talent_pool_list and user_name is None:
                user = User.get_by_id(user_id)
                if user:
                    return cls.query.filter(cls.talent_pool_id == TalentPool.id) \
                        .filter(or_((cls.added_time >= user_specific_date), (
                         cls.updated_time >= user_specific_date))). \
                        filter(and_(TalentPool.name.in_(talent_pool_list), TalentPool.domain_id == user.domain_id)). \
                        distinct().count()
            if talent_pool_list is None and user_name is None:
                user = User.get_by_id(user_id)
                if user:
                    return cls.query.filter(cls.talent_pool_id == TalentPool.id) \
                        .filter(or_((cls.added_time >= user_specific_date), (
                         cls.updated_time >= user_specific_date))).filter(TalentPool.domain_id == user.domain_id). \
                        distinct().count()
        if isinstance(user_specific_date, basestring):
            if user_name and talent_pool_list:
                users = User.get_by_name(user_id, user_name)
                if users:
                    user = users[0]
                    return cls.query.filter(cls.talent_pool_id == TalentPool.id) \
                        .filter(or_((extract("year", cls.added_time) == user_specific_date), (
                         extract("year", cls.updated_time) == user_specific_date))). \
                        filter(
                        and_(TalentPool.user_id == user.id, TalentPool.name.in_(talent_pool_list))).distinct().count()
                raise NotFoundError
            if user_name and talent_pool_list is None:
                user = User.get_by_id(user_id)
                if user:
                    return cls.query.filter(cls.talent_pool_id == TalentPool.id) \
                        .filter(or_((extract("year", cls.added_time) == user_specific_date), (
                         extract("year", cls.updated_time) == user_specific_date))). \
                        filter(User.id == TalentPool.user_id). \
                        filter(and_(or_(User.first_name == user_name, User.last_name == user_name), TalentPool.domain_id == user.domain_id)). \
                        distinct().count()
            if talent_pool_list and user_name is None:
                user = User.get_by_id(user_id)
                if user:
                    return cls.query.filter(cls.talent_pool_id == TalentPool.id) \
                        .filter(or_((extract("year", cls.added_time) == user_specific_date), (
                         extract("year", cls.updated_time) == user_specific_date))). \
                        filter(and_(TalentPool.name.in_(talent_pool_list), TalentPool.domain_id == user.domain_id)). \
                        distinct().count()
            if talent_pool_list is None and user_name is None:
                user = User.get_by_id(user_id)
                if user:
                    return cls.query.filter(cls.talent_pool_id == TalentPool.id) \
                        .filter(or_((extract("year", cls.added_time) == user_specific_date), (
                         extract("year", cls.updated_time) == user_specific_date))).\
                        filter(TalentPool.domain_id == user.domain_id). \
                        distinct().count()
        if user_specific_date is None:
            if user_name and talent_pool_list:
                users = User.get_by_name(user_id, user_name)
                if users:
                    user = users[0]
                    return cls.query.filter(cls.talent_pool_id == TalentPool.id). \
                        filter(
                        and_(TalentPool.user_id == user.id, TalentPool.name.in_(talent_pool_list))).distinct().count()
                raise NotFoundError
            if user_name and talent_pool_list is None:
                users = User.get_by_name(user_id, user_name)
                if users:
                    user = users[0]
                    return cls.query.filter(cls.talent_pool_id == TalentPool.id) \
                        .filter(TalentPool.user_id == user.id). \
                        distinct().count()
                raise NotFoundError
            if user_name is None and talent_pool_list:
                user = User.get_by_id(user_id)
                if user:
                    return cls.query.filter(cls.talent_pool_id == TalentPool.id). \
                        filter(and_(TalentPool.name.in_(talent_pool_list), TalentPool.domain_id == user.domain_id)). \
                        distinct().count()
            if not user_name and not talent_pool_list:
                user = User.get_by_id(user_id)
                if user:
                    return cls.query.filter(cls.talent_pool_id == TalentPool.id) \
                        .filter(TalentPool.domain_id == user.domain_id).distinct() \
                        .count()
        return "Something went wrong cant find any imports"


class TalentPoolGroup(db.Model):
    __tablename__ = 'talent_pool_group'
    id = db.Column(db.Integer, primary_key=True)
    talent_pool_id = db.Column(db.Integer, db.ForeignKey('talent_pool.id', ondelete='CASCADE'), nullable=False)
    user_group_id = db.Column(db.Integer, db.ForeignKey('user_group.Id', ondelete='CASCADE'), nullable=False)

    # Relationships
    talent_pool = db.relationship('TalentPool', backref=db.backref('talent_pool_group', cascade="all, delete-orphan"))
    user_group = db.relationship('UserGroup', backref=db.backref('talent_pool_group', cascade="all, delete-orphan"))

    def __repr__(self):
        return "<TalentPoolGroup: (talent_pool_id = {})>".format(self.talent_pool_id)

    @classmethod
    def get(cls, talent_pool_id, user_group_id):
        return cls.query.filter_by(talent_pool_id=talent_pool_id, user_group_id=user_group_id).first()

    def delete(self):
        db.session.delete(self)
        db.session.commit()


class TalentPipeline(db.Model):
    __tablename__ = 'talent_pipeline'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.TEXT)
    positions = db.Column(db.Integer, default=1, nullable=False)
    date_needed = db.Column(db.DateTime, nullable=False)
    user_id = db.Column(db.BIGINT, db.ForeignKey('user.Id', ondelete='CASCADE'), nullable=False)
    talent_pool_id = db.Column(db.Integer, db.ForeignKey('talent_pool.id'), nullable=False)
    search_params = db.Column(db.TEXT)
    is_hidden = db.Column(TINYINT, default='0', nullable=False)
    added_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_time = db.Column(db.TIMESTAMP, default=datetime.utcnow, onupdate=datetime.utcnow,
                             nullable=False)

    # Relationships
    user = db.relationship('User', backref=db.backref('talent_pipeline', cascade="all, delete-orphan"))
    talent_pool = db.relationship('TalentPool', backref=db.backref('talent_pipeline', cascade="all, delete-orphan"))

    def __repr__(self):
        return "TalentPipeline (id = {})".format(self.id)

    def get_id(self):
        return unicode(self.id)

    @classmethod
    def get_by_user_id_in_desc_order(cls, user_id):
        """
        Returns a list of TalentPipelines ordered by their creation time
        :type user_id:  int | long
        :rtype:  list[TalentPipeline]
        """
        return cls.query.filter_by(user_id=user_id).order_by(cls.added_time.desc()).all()

    def get_email_campaigns(self, page=1, per_page=20):
        from candidate_pool_service.common.models.email_campaign import EmailCampaign, EmailCampaignSmartlist
        from candidate_pool_service.common.models.smartlist import Smartlist
        return EmailCampaign.query.distinct(EmailCampaign.id).join(EmailCampaignSmartlist).join(Smartlist). \
            join(TalentPipeline).filter(TalentPipeline.id == self.id).paginate(page=page, per_page=per_page,
                                                                               error_out=False).items

    def get_email_campaigns_count(self):
        from candidate_pool_service.common.models.email_campaign import EmailCampaign, EmailCampaignSmartlist
        from candidate_pool_service.common.models.smartlist import Smartlist
        return EmailCampaign.query.distinct(EmailCampaign.id).join(EmailCampaignSmartlist).join(Smartlist).\
            join(TalentPipeline).filter(TalentPipeline.id == self.id).count()

    def delete(self):
        db.session.delete(self)
        db.session.commit()

    def to_dict(self, include_stats=False, get_stats_function=None, include_growth=False, interval=None,
                get_growth_function=None, include_candidate_count=False, get_candidate_count=None,
                email_campaign_count=False):

        talent_pipeline = {
            'id': self.id,
            'name': self.name,
            'description': self.description,
            'user_id': self.user_id,
            'positions': self.positions,
            'search_params': json.loads(
                self.search_params) if self.search_params else None,
            'talent_pool_id': self.talent_pool_id,
            'date_needed': self.date_needed.isoformat() if self.date_needed else None,
            'is_hidden': self.is_hidden,
            'added_time': self.added_time.isoformat(),
            'updated_time': self.updated_time.isoformat()
        }
        if email_campaign_count:
            talent_pipeline['total_email_campaigns'] = self.get_email_campaigns_count()
        if include_candidate_count and get_candidate_count:
            talent_pipeline['total_candidates'] = get_candidate_count(self, datetime.utcnow())
        if include_growth and interval and get_growth_function:
            talent_pipeline['growth'] = get_growth_function(self, int(interval))
        if include_stats and get_stats_function:
            # Include Last 30 days stats in response body
            to_date = datetime.utcnow() - timedelta(days=1)
            to_date = to_date.replace(hour=23, minute=59, second=59)
            from_date = to_date - timedelta(days=29)
            talent_pipeline['stats'] = [] if self.added_time.date() == datetime.utcnow().date() else \
                get_stats_function(self, 'TalentPipeline', None, from_date.isoformat(), to_date.isoformat(), offset=0)

        return talent_pipeline

    @classmethod
    def get_by_user_and_talent_pool_id(cls, user_id, talent_pool_id):
        """
        This returns talent-pipeline object for particular user and talent_pool_id
        :param user_id: id of user object
        :param talent_pool_id: id of talent_pool object
        :rtype: TalentPipeline | None
        """
        assert user_id, 'user_id not provided'
        assert talent_pool_id, 'talent_pool_id not provided'
        return cls.query.filter_by(user_id=user_id, talent_pool_id=talent_pool_id).first()
