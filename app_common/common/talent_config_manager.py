# -*- coding: utf-8 -*-
"""Class to manage property keys and values specific to the application environment (e.g. prod, staging, local).

In a developer's local environment, the file given by the below LOCAL_CONFIG_PATH contains the property keys and values.

﻿In prod and staging environments, the above config file does not exist.
Rather, the properties are obtained from ECS environment variables and a private S3 bucket.
"""

import logging
import logging.config
import os
import tempfile

# Load logging configuration file
APP_ROOT = os.path.dirname(os.path.abspath(__file__))
LOGGING_CONF = os.path.join(APP_ROOT, 'logging.conf')
logging.config.fileConfig(LOGGING_CONF)

# Kindly refer to following url for sample web.cfg
# https://github.com/gettalent/talent-flask-services/wiki/Local-environment-setup#local-configurations
CONFIG_FILE_NAME = "web.cfg"
LOCAL_CONFIG_PATH = ".talent/%s" % CONFIG_FILE_NAME
STAGING_CONFIG_FILE_S3_BUCKET = "gettalent-private-staging"
PROD_CONFIG_FILE_S3_BUCKET = "gettalent-private"


class TalentConfigKeys(object):
    CS_REGION_KEY = "CLOUD_SEARCH_REGION"
    CS_DOMAIN_KEY = "CLOUD_SEARCH_DOMAIN"
    EMAIL_KEY = "EMAIL"
    ENV_KEY = "GT_ENVIRONMENT"
    S3_BUCKET_KEY = "S3_BUCKET_NAME"
    S3_REGION_KEY = "S3_BUCKET_REGION"
    S3_FILE_PICKER_BUCKET_KEY = "S3_FILEPICKER_BUCKET_NAME"
    AWS_KEY = "AWS_ACCESS_KEY_ID"
    AWS_SECRET = "AWS_SECRET_ACCESS_KEY"
    SECRET_KEY = "SECRET_KEY"
    REDIS_URL_KEY = "REDIS_URL"
    LOGGER = "LOGGER"


def load_gettalent_config(app_config):
    """
    Load configuration variables from env vars, conf file, or S3 bucket (if QA/prod)
    :param flask.config.Config app_config: Flask configuration object
    :return: None
    """
    app_config.root_path = os.path.expanduser('~')

    # Load up config from file on local filesystem (for local dev & Jenkins only).
    app_config.from_pyfile(LOCAL_CONFIG_PATH, silent=True)  # silent=True avoids errors in CI/QA/prod envs

    # Make sure that the environment and AWS credentials are defined
    for config_field_key in (TalentConfigKeys.ENV_KEY, TalentConfigKeys.AWS_KEY, TalentConfigKeys.AWS_SECRET):
        app_config[config_field_key] = app_config.get(config_field_key) or os.environ.get(config_field_key)
        if not app_config.get(config_field_key):
            raise Exception("Loading getTalent config: Missing required environment variable: %s" % config_field_key)
    app_config[TalentConfigKeys.ENV_KEY] = app_config[TalentConfigKeys.ENV_KEY].strip().lower()
    app_config[TalentConfigKeys.LOGGER] = logging.getLogger("flask_service.%s" % app_config[TalentConfigKeys.ENV_KEY])

    # Load up config from private S3 bucket, if environment is qa or prod
    if app_config[TalentConfigKeys.ENV_KEY] in ('qa', 'prod'):
        # Open S3 connection to default region & use AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY env vars
        from boto.s3.connection import S3Connection
        s3_connection = S3Connection()
        bucket_name = PROD_CONFIG_FILE_S3_BUCKET if app_config[TalentConfigKeys.ENV_KEY] == 'prod' else \
            STAGING_CONFIG_FILE_S3_BUCKET
        bucket_obj = s3_connection.get_bucket(bucket_name)
        app_config[TalentConfigKeys.LOGGER].info("Loading getTalent config from private S3 bucket %s", bucket_name)

        # Download into temporary file & load config
        tmp_config_file = tempfile.NamedTemporaryFile()
        bucket_obj.get_key(key_name=CONFIG_FILE_NAME).get_contents_to_file(tmp_config_file)
        app_config.from_pyfile(tmp_config_file.name)
        tmp_config_file.close()

    # Load up hardcoded app config values
    _set_environment_specific_configurations(app_config[TalentConfigKeys.ENV_KEY], app_config)

    # Verify that all the TalentConfigKeys have been defined in the app config (one way or another)
    if not verify_all_config_keys_defined(app_config):
        raise Exception("Some required app config keys not defined. app config: %s" % app_config)
    app_config['LOGGER'].info("App configuration successfully loaded with %s keys: %s", len(app_config), app_config.keys())
    app_config['LOGGER'].debug("App configuration: %s", app_config)


def _set_environment_specific_configurations(environment, app_config):
    app_config['DEBUG'] = False

    if environment == 'dev':
        app_config['SQLALCHEMY_DATABASE_URI'] = 'mysql://talent_web:s!loc976892@127.0.0.1/talent_local'
        app_config['CELERY_RESULT_BACKEND_URL'] = app_config['REDIS_URL'] = 'redis://localhost:6379'
        app_config['DEBUG'] = True
        app_config['OAUTH2_PROVIDER_TOKEN_EXPIRES_IN'] = 7200  # 2 hours expiry time for bearer token
    elif environment == 'jenkins':
        app_config['DEBUG'] = True
        app_config['SQLALCHEMY_DATABASE_URI'] = \
            'mysql://talent-jenkins:s!jenkins976892@jenkins.gettalent.com/talent_jenkins'
        app_config['CELERY_RESULT_BACKEND_URL'] = app_config['REDIS_URL'] = \
            'redis://:s!jenkinsRedis974812@jenkins.gettalent.com:6379'
        app_config['OAUTH2_PROVIDER_TOKEN_EXPIRES_IN'] = 7200  # 2 hours expiry time for bearer token
    elif environment == 'qa':
        # TODO: Figure out why Staging services don't load from the gettalent-private-staging bucket!
        app_config['SQLALCHEMY_DATABASE_URI'] = "mysql://talent_web:s!web976892@devdb.gettalent.com/talent_staging"
        app_config['CELERY_RESULT_BACKEND_URL'] = "redis://dev-redis-vpc.znj3iz.0001.usw1.cache.amazonaws.com:6379"
        app_config['REDIS_URL'] = "redis://dev-redis-vpc.znj3iz.0001.usw1.cache.amazonaws.com:6379"
        app_config['CLOUD_SEARCH_DOMAIN'] = "gettalent-webdev"
        app_config['CLOUD_SEARCH_REGION'] = "us-west-1"
        app_config['S3_BUCKET_NAME'] = "tcs-staging"
        app_config['S3_FILEPICKER_BUCKET_NAME'] = "gettalent-filepicker"
        app_config['S3_BUCKET_REGION'] = "us-west-1"
        app_config['EMAIL'] = "osman.masood@dice.com"
        app_config['ACCOUNT_ID'] = "528222547498"
        app_config['DEBUG'] = False
        app_config['OAUTH2_PROVIDER_TOKEN_EXPIRES_IN'] = 7200
        app_config['SECRET_KEY'] = "422a1a6961a450b94860ced1f55c3be8c8b4654c9af7534f"


def verify_all_config_keys_defined(app_config):
    """
    If any TalentConfigKey is not defined, will return False.

    :rtype: bool
    """

    # Filter out all private methods/fields of the object class
    all_config_keys = filter(lambda possible_config_key: not possible_config_key.startswith("__"),
                             dir(TalentConfigKeys))

    for config_key in all_config_keys:
        app_config_field_name = getattr(TalentConfigKeys, config_key)
        if not app_config.get(app_config_field_name):
            return False
    return True
