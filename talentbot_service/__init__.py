"""
Getting app and logger from common services
"""
from talentbot_service.common.utils.models_utils import init_talent_app

app, logger = init_talent_app(__name__)