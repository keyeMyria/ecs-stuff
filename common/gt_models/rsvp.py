from sqlalchemy import Column, Integer, String, DateTime, \
    ForeignKey, and_
from base import ModelBase as Base


class RSVP(Base):
    __tablename__ = 'rsvp'
    id = Column(Integer, primary_key=True)
    socialNetworkRsvpId = Column(String(500))
    candidateId = Column(Integer, ForeignKey("candidate.id"), nullable=False)
    eventId = Column(Integer, ForeignKey("event.id"), nullable=False)
    socialNetworkId = Column(Integer, ForeignKey("social_network.id"), nullable=False)
    status = Column(String(20))
    datetime = Column(DateTime)
    paymentStatus = Column(String(20))

    def __repr__(self):
        return '<RSVP %s>' % self.socialNetworkRsvpId

    @classmethod
    def get_by_vendor_rsvp_id_candidate_id_vendor_id_time(cls, social_network_rsvp_id,
                                                          candidateId,
                                                          social_network_id,
                                                          added_time):
        assert social_network_rsvp_id is not None
        assert candidateId is not None
        assert social_network_id is not None

        return cls.query.filter(
            and_(
                RSVP.socialNetworkRsvpId == social_network_rsvp_id,
                RSVP.candidateId == candidateId,
                RSVP.socialNetworkId == social_network_id,
                RSVP.datetime == added_time,
            )
        ).first()

    @classmethod
    def get_by_vendor_rsvp_id_candidate_id_vendor_id_event_id(cls,
                                                              vendor_rsvp_id,
                                                              candidate_id,
                                                              social_network_id,
                                                              event_id):
        assert vendor_rsvp_id is not None
        assert candidate_id is not None
        assert social_network_id is not None
        assert event_id is not None

        return cls.query.filter(
            and_(
                RSVP.socialNetworkRsvpId == vendor_rsvp_id,
                RSVP.candidateId == candidate_id,
                RSVP.socialNetworkId == social_network_id,
                RSVP.eventId == event_id
            )
        ).first()


class CandidateEventRSVP(Base):
    __tablename__ = 'candidate_event_rsvp'

    id = Column(Integer, primary_key=True)
    candidateId = Column(Integer, ForeignKey('candidate.id'), nullable=False)
    eventId = Column(Integer, ForeignKey('event.id'), nullable=False)
    rsvpId = Column(Integer, ForeignKey('rsvp.id'), nullable=False)

    def __repr__(self):
        return '<CandidateEventRSVP %r %r %r>' % (self.candidateId, self.eventId, self.status)

    @classmethod
    def get_by_id_of_candidate_event_rsvp(cls, candidate_id, event_id, rsvp_id):
        assert candidate_id is not None
        assert event_id is not None
        assert rsvp_id is not None

        return cls.query.filter(
            and_(
                CandidateEventRSVP.candidateId == candidate_id,
                CandidateEventRSVP.eventId == event_id,
                CandidateEventRSVP.rsvpId == rsvp_id,
            )
        ).first()
