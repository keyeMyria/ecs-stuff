"""
    Run Celery Worker

For Celery to run from command line, script runs as separate process with celery command

 Usage: open terminal cd to talent-flask-services directory

 Run the following command to start celery worker:

    $ celery -A email_campaign_service.email_campaign_app.celery_app worker --concurrency=4 --loglevel=info
"""

# Service Specific
from email_campaign_service.email_campaign_app import celery_app, logger, app
from email_campaign_service.common.talent_config_manager import TalentConfigKeys
from email_campaign_service.common.campaign_services.campaign_utils import CampaignUtils

try:
    celery_app.start(argv=['celery', 'worker', '-l', 'info', '-Q', CampaignUtils.EMAIL])
except Exception as e:
    logger.exception("Couldn't start Celery app for email_campaign_service in "
                     "%s environment." % (app.config[TalentConfigKeys.ENV_KEY]))
