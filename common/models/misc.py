from db import db
import datetime
from sqlalchemy.orm import relationship
import time
import candidate


class Activity(db.Model):
    __tablename__ = 'activity'
    id = db.Column(db.Integer, primary_key=True)
    added_time = db.Column('AddedTime', db.DateTime, default=datetime.datetime.now())
    source_table = db.Column('SourceTable', db.String(127))
    source_id = db.Column('SourceID', db.Integer)
    type = db.Column('Type', db.Integer)
    user_id = db.Column('UserId', db.Integer, db.ForeignKey('user.id'))
    params = db.Column(db.Text)


class AreaOfInterest(db.Model):
    __tablename__ = 'area_of_interest'
    id = db.Column(db.BigInteger, primary_key=True)
    domain_id = db.Column('DomainId', db.Integer, db.ForeignKey('domain.id'))
    description = db.Column('Description', db.String(255))
    parent_id = db.Column('ParentId', db.BigInteger, db.ForeignKey('area_of_interest.id'))
    updated_time = db.Column('UpdatedTime', db.TIMESTAMP, default=datetime.datetime.now())

    def __repr__(self):
        return "<AreaOfInterest (parent_id=' %r')>" % self.parent_id


#TODO verify this is removed.
# class ClassificationType(db.Model):
#     __tablename__ = 'classification_type'
#     id = db.Column(db.Integer, primary_key=True)
#     code = db.Column('Code', db.String(100))
#     description = db.Column('Description', db.String(250))
#     notes = db.Column('Notes', db.String(500))
#     list_order = db.Column('ListOrder', db.Integer)
#     updated_time = db.Column('UpdatedTime', db.TIMESTAMP, default=datetime.datetime.now())


class Country(db.Model):
    __tablename__ = 'country'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column('Name', db.String(100), nullable=False)
    code = db.Column('Code', db.String(20), nullable=False)

    # Relationships
    candidate_military_services = relationship('CandidateMilitaryService', backref='country')
    patent_details = relationship('PatentDetail', backref='country')
    candidate_addresses = relationship('CandidateAddress', backref='country')
    candidate_educations = relationship('CandidateEducation', backref='country')
    candidate_experiences = relationship('CandidateExperience', backref='country')

    def __repr__(self):
        return "<Country (name=' %r')>" % self.name


# Even though the table name is major I'm keeping the model class singular.
class Major(db.Model):
    __tablename__ = 'majors'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column('Name', db.String(100), nullable=False)
    domain_id = db.Column('DomainId', db.Integer, db.ForeignKey('domain.id'))
    updated_time = db.Column('UpdatedTime', db.TIMESTAMP, default=datetime.datetime.now())

    def serialize(self):
        return {
            'id': self.id,
        }


class Organization(db.Model):
    __tablename__ = 'organization'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column('Name', db.String(500), unique=True)
    notes = db.Column('Notes', db.String(1000))

    def __repr__(self):
        return "<Organization (name=' %r')>" % self.name


class ZipCode(db.Model):
    __tablename__ = 'zipcode'
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column('Name', db.String(100))
    notes = db.Column('Notes', db.String(500))
    updated_time = db.Column('UpdatedTime', db.DateTime, default=time.time())

    def __repr__(self):
        return "<Zipcode (code=' %r')>" % self.code


class CustomField(db.Model):
    __tablename__ = 'custom_field'
    id = db.Column(db.Integer, primary_key=True)
    domain_id = db.Column('DomainId', db.Integer, db.ForeignKey('domain.id'))
    name = db.Column('Name', db.String(255))
    type = db.Column('Type', db.String(127))
    category_id = db.Column('CategoryId', db.Integer)
    added_time = db.Column('AddedTime', db.DateTime)
    updated_time = db.Column('UpdatedTime', db.TIMESTAMP, default=datetime.datetime.now())

    # Relationship
    candidate_custom_fields = relationship('CandidateCustomField', backref='custom_field')

    def __repr__(self):
        return "<CustomField (name = %r)>" % self.name
