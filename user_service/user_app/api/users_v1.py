from flask_restful import Resource
from common.models.user import User
from common.utils.validators import is_number
from common.utils.auth_utils import require_oauth
from flask import request


class UserResource(Resource):
    decorators = [require_oauth]

    def get(self, **kwargs):
        """ GET /web/users/:id

        Fetch user object with user's basic info.

        Takes an integer as user_id, assigned to args[0].
        The function will only accept an integer.
        Logged in user must be an admin.

        :return: A dictionary containing user's info from the database except
                 user's password, registration_key, and reset_password_key.
                 Not Found Error if user is not found.
        """

        # If user_id not is provided then use the id of logged in user
        requested_user_id = kwargs.get('id') or request.user.id
        # id must be integer
        if not is_number(requested_user_id):
            print is_number(requested_user_id)
            return {'error': {'code': 4, 'message': 'ID must be an integer'}}, 400

        requested_user = User.query.get(requested_user_id)
        if not requested_user:
            return {'error': {'message': 'User not found'}}, 404

        return {'user': {
            'id': requested_user_id,
            'domain_id': requested_user.domain_id,
            'email': requested_user.email,
            'first_name': requested_user.first_name,
            'last_name': requested_user.last_name,
            'phone': requested_user.phone,
            'dice_user_id': requested_user.dice_user_id
        }}

