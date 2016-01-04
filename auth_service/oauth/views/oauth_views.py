__author__ = 'ufarooqi'

from auth_service.oauth import app
from auth_service.oauth import gt_oauth
from auth_service.oauth import logger
from flask import request, jsonify
from auth_service.common.error_handling import *
from flask.ext.cors import CORS


# Enable CORS
CORS(app, resources={
    r'/(oauth2|roles|users)/*': {
        'origins': '*',
        'allow_headers': ['Content-Type', 'Authorization']
    }
})

gt_oauth.grantgetter(lambda *args, **kwargs: None)
gt_oauth.grantsetter(lambda *args, **kwargs: None)


@app.route('/v1/oauth2/token', methods=['POST'])
@gt_oauth.token_handler
def access_token(*args, **kwargs):
    """ Create a new access_token for a user and store it in Token table """
    return None


@app.route('/v1/oauth2/revoke', methods=['POST'])
@gt_oauth.revoke_handler
def revoke_token():
    """ Revoke or delete an access_token from Token table """
    pass


@app.route('/v1/oauth2/authorize')
@gt_oauth.require_oauth()
def authorize():
    """ Authorize an access token which is stored in Authorization header """
    if hasattr(request.oauth, 'error_message'):
        error_message = request.oauth.error_message or ''
        if error_message:
            error_code = request.oauth.error_code or None
            raise UnauthorizedError(error_message=error_message, error_code=error_code)
    user = request.oauth.user
    logger.info('User %s has been authorized to access getTalent api', user.id)
    return jsonify(user_id=user.id)
