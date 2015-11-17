__author__ = 'erik@getTalent.com'
# Standard Library
import datetime
# Third party
from _mysql_exceptions import IntegrityError
import pytest
# Module Specific
from flask import current_app
from resume_service.common.models.email import EmailLabel
from resume_service.common.models.misc import Country
from resume_service.common.models.misc import Culture
from resume_service.common.models.misc import Organization
from resume_service.common.models.misc import Product
from resume_service.common.models.phone import PhoneLabel
from resume_service.common.models.user import Client
from resume_service.common.models.user import Domain
from resume_service.common.models.user import Token
from resume_service.common.models.user import User
from resume_service.common.utils.db_utils import get_or_create
from resume_service.common.utils.handy_functions import random_word
from resume_service.resume_parsing_app import db


def require_integrity(func):
    def wrapped(*args, **kwargs):
        try:
            print 'OH HAI {} - {} - {}'.format( func.__name__, args, kwargs)
            func(*args, **kwargs)
        except IntegrityError:
            db.session.rollback()
    return wrapped


@pytest.fixture(autouse=True)
def org_fixture(request):
    org_attrs = dict(name='Rocket League All Stars - {}'.format(random_word(8)))
    org, created = get_or_create(db.session, Organization, defaults=None, **org_attrs)
    if created:
        db.session.add(org)
        db.session.commit()
    @require_integrity
    def fin():
        db.session.delete(org)
        db.session.commit()
    request.addfinalizer(fin)
    return org


@pytest.fixture(autouse=True)
def culture_fixture(request):
    # culture_attrs = dict(description='Foo {}'.format(random_word(12)), code=random_word(5))
    culture_attrs = dict(id=1)
    culture, created = get_or_create(db.session, Culture, defaults=None, **culture_attrs)
    if created:
        db.session.add(culture)
        db.session.commit()
    @require_integrity
    def fin():
        db.session.delete(culture)
        db.session.commit()
    request.addfinalizer(fin)
    return culture


@pytest.fixture(autouse=True)
def domain_fixture(culture_fixture, org_fixture, request):
    domain = Domain(name=random_word(40), usage_limitation=0,
                         expiration=datetime.datetime(2050, 4, 26),
                         added_time=datetime.datetime(2050, 4, 26),
                         organization_id=org_fixture.id, is_fair_check_on=False, is_active=1,
                         default_tracking_code=1, default_from_name=(random_word(100)),
                         default_culture_id=culture_fixture.id,
                         settings_json=random_word(55), updated_time=datetime.datetime.now())

    db.session.add(domain)
    db.session.commit()
    @require_integrity
    def fin():
       db.session.delete(domain)
       db.session.commit()
    request.addfinalizer(fin)
    return domain


@pytest.fixture(autouse=True)
def user_fixture(domain_fixture, request):
    user = User(domain_id=domain_fixture.id, first_name='Jamtry', last_name='Jonas',
                     password='password', email='jamtry@{}.com'.format(random_word(8)),
                     added_time=datetime.datetime(2050, 4, 26))
    db.session.add(user)
    db.session.commit()
    @require_integrity
    def fin():
        db.session.delete(user)
        db.session.commit()
    request.addfinalizer(fin)
    return user


@pytest.fixture(autouse=True)
def client_fixture(request):
    client = Client(client_id=random_word(12), client_secret=random_word(12))
    db.session.add(client)
    db.session.commit()
    @require_integrity
    def fin():
        db.session.query(Client).delete()
        db.session.commit()
    request.addfinalizer(fin)
    return client


@pytest.fixture(autouse=True)
def token_fixture(user_fixture, client_fixture, request):
    token = Token(client_id=client_fixture.client_id, user_id=user_fixture.id, token_type='bearer', access_token=random_word(8),
                       refresh_token=random_word(8), expires=datetime.datetime(2050, 4, 26))
    db.session.add(token)
    db.session.commit()
    @require_integrity
    def fin():
        db.session.query(Token).delete()
        db.session.commit()
    request.addfinalizer(fin)
    return token


@pytest.fixture(autouse=True)
def email_label_fixture(request):
    label_attrs = dict(id=1, description='Primary', updated_time=datetime.datetime.now())
    label, created = get_or_create(db.session, EmailLabel, label_attrs)
    if created:
        db.session.commit()
    return label


@pytest.fixture(autouse=True)
def country_fixture(request):
    country_attrs = dict(id=1, name='United States', code='US')
    country, created = get_or_create(db.session, Country, defaults=None, **country_attrs)
    if created:
        db.session.add(country)
        db.session.commit()
    @require_integrity
    def fin():
        db.session.delete(country)
        db.session.commit()
    request.addfinalizer(fin)
    return country


@pytest.fixture(autouse=True)
def phone_label_fixture(request):
    phone_labels = [
        PhoneLabel(description='primary'),
        PhoneLabel(description='home'),
        PhoneLabel(description='work'),
        PhoneLabel(description='cell'),
    ]
    db.session.bulk_save_objects(phone_labels)
    db.session.commit()

    #needs to delete candidate phone
    # def fin():
    #     db.session.query(PhoneLabel).delete()
    #     db.session.commit()
    # request.addfinalizer(fin)
    return phone_labels


@pytest.fixture(autouse=True)
def product_fixture(request):
    product_attrs = dict(id=2, name='Web')
    product, created = get_or_create(db.session, Product, defaults=None, **product_attrs)
    if created:
        db.session.add(product)
        db.session.commit()

    # def fin():
    #     db.session.delete(product)
    #     db.session.commit()
    # request.addfinalizer(fin)
    return product
