__author__ = 'basit'


from apis.email_campaigns import email_campaign_blueprint
from email_campaign_service.email_campaign_app import app

# Register API endpoints
app.register_blueprint(email_campaign_blueprint)