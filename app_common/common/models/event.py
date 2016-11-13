from sqlalchemy.orm import relationship
from db import db
from rsvp import RSVP


class Event(db.Model):
    __tablename__ = 'event'
    id = db.Column(db.Integer, primary_key=True)
    social_network_event_id = db.Column('socialNetworkEventId', db.String(1000))
    title = db.Column(db.String(500))
    description = db.Column(db.String(1000))
    social_network_id = db.Column('socialNetworkId', db.Integer, db.ForeignKey('social_network.Id'), nullable=False)
    user_id = db.Column('userId', db.BIGINT, db.ForeignKey('user.Id'), nullable=False)
    organizer_id = db.Column('organizerId', db.Integer, db.ForeignKey('event_organizer.id'), nullable=True)
    venue_id = db.Column('venueId', db.Integer, db.ForeignKey('venue.Id'), nullable=False)
    social_network_group_id = db.Column('socialNetworkGroupId', db.String(100))
    group_url_name = db.Column('groupUrlName', db.String(500))
    url = db.Column(db.String(500))
    start_datetime = db.Column('startDatetime', db.DateTime)
    end_datetime = db.Column('endDatetime', db.DateTime)
    registration_instruction = db.Column('registrationInstruction', db.String(1000))
    cost = db.Column(db.Float)
    currency = db.Column(db.String(20))
    timezone = db.Column(db.String(100))
    max_attendees = db.Column('maxAttendees', db.Integer)
    tickets_id = db.Column('ticketsId', db.Integer, nullable=True)

    # Relationship
    rsvps = relationship('RSVP', lazy='dynamic', cascade='all, delete-orphan', passive_deletes=True, backref='event')

    def __ne__(self, other_event):
        return (self.social_network_event_id != other_event.social_network_event_id and
                self.user_id != other_event.user_id)

    def __eq__(self, other_event):
        return (self.social_network_event_id == other_event.social_network_event_id and
                self.user_id == other_event.user_id and
                self.organizer_id == other_event.organizer_id and
                self.venue_id == other_event.venue_id and
                self.start_datetime == other_event.start_datetime)

    @classmethod
    def get_by_domain_id(cls, domain_id):
        """
        This returns Query object for all the events in user's domain(given domain_id)
        :param int|long domain_id: Id of domain of user
        """
        assert domain_id, 'domain_id is required param'
        from user import User  # This has to be here to avoid circular import
        return cls.query.join(User).filter(User.domain_id == domain_id)

    @classmethod
    def get_by_event_id_and_domain_id(cls, event_id, domain_id):
        """
        This searches given event_id in given domain_id of user
        """
        assert event_id and domain_id
        from user import User  # This has to be here to avoid circular import
        return cls.query.filter_by(id=event_id).join(User).filter(User.domain_id == domain_id).first()

    @classmethod
    def get_by_user_and_social_network_event_id(cls, user_id, social_network_event_id):
        assert user_id and social_network_event_id
        return cls.query.filter(
            db.and_(
                Event.user_id == user_id,
                Event.social_network_event_id == social_network_event_id
            )).first()

    @classmethod
    def get_by_user_id_vendor_id_start_date(cls, user_id, social_network_id, start_date):
        assert user_id and social_network_id and start_date
        return cls.query.filter(
            db.and_(
                Event.user_id == user_id,
                Event.social_network_id == social_network_id,
                Event.start_datetime >= start_date
            )).all()

    @classmethod
    def get_by_user_id_social_network_id_vendor_event_id(cls, user_id,
                                                         social_network_id,
                                                         social_network_event_id):
        assert social_network_id and social_network_event_id and user_id
        return cls.query.filter(
            db.and_(
                Event.user_id == user_id,
                Event.social_network_id == social_network_id,
                Event.social_network_event_id == social_network_event_id
            )
        ).first()

    @classmethod
    def get_by_user_id_event_id_social_network_event_id(cls, user_id,
                                                         _id, social_network_event_id):
        assert _id and social_network_event_id and user_id
        return cls.query.filter(
            db.and_(
                Event.user_id == user_id,
                Event.id == _id,
                Event.social_network_event_id == social_network_event_id
            )
        ).first()

    @classmethod
    def get_by_user_and_event_id(cls, user_id, event_id):
        assert user_id and event_id
        return cls.query.filter(
            db.and_(
                Event.user_id == user_id,
                Event.id == event_id
            )).first()


class MeetupGroup(db.Model):
    __tablename__ = 'meetup_group'
    id = db.Column(db.Integer, primary_key=True)
    group_id = db.Column(db.String(100), unique=True)
    user_id = db.Column('userId', db.BIGINT, db.ForeignKey('user.Id'), nullable=False)
    name = db.Column(db.String(500))
    url_name = db.Column(db.String(500))
    description = db.Column(db.String(1000))
    visibility = db.Column(db.String(20))
    country = db.Column(db.String(20))
    state = db.Column(db.String(20))
    city = db.Column(db.String(30))
    timezone = db.Column(db.String(100))
    created_datetime = db.Column(db.DateTime)

    @classmethod
    def get_by_group_id(cls, group_id):
        return cls.query.filter_by(group_id=group_id).first()

    @classmethod
    def get_by_user_id_and_group_id(cls, user_id, group_id):
        return cls.query.filter_by(user_id=user_id, group_id=group_id).first()
