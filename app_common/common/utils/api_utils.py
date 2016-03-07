"""
This modules contains helper methods and classes which we are using in e.g. Social Network API app.

        * ApiResponse:
            This class is used to create API response object to return json response.

"""
__author__ = 'basit'

# Standard Library
import json

# Third Part
from flask import Response

# Application Specific
from models_utils import to_json
from ..error_handling import InvalidUsage
from .handy_functions import JSON_CONTENT_TYPE_HEADER

DEFAULT_PAGE = 1
DEFAULT_PAGE_SIZE = 10
MAX_PAGE_SIZE = 50


class ApiResponse(Response):
    """
    Override default_mimetype to 'application/json' to return proper json api response
    """
    def __init__(self, response, status=200, content_type=JSON_CONTENT_TYPE_HEADER['content-type'],
                 headers=None):
        if isinstance(response, dict):
            response = json.dumps(response)
        super(Response, self).__init__(response, status=status,
                                       content_type=content_type,
                                       headers=headers)


def api_route(self, *args, **kwargs):
    """
    This method helps to make api endpoints to look similar to normal flask routes.
    Simply use it as a decorator on api endpoint method.

        :Example:

            @api.route('/events/')
            class Events(Resource):

                def get(*args, **kwargs):
                    do stuff here for GET request

                def post(*args, **kwargs):
                    do stuff here for POST request

    """
    def wrapper(cls):
        self.add_resource(cls, *args, **kwargs)
        return cls
    return wrapper


def get_pagination_params(request):
    """
    This function helps to extract pagination query parameters "page" and "per_page" values.
    It validates the values for these params and raises InvalidUsage if given values or not
     valid number or returns default values (page=1, per_page=10) if no values are given.
    :param request: request object to get query params
    :return: page, per_page
    :rtype: tuple
    """
    page = request.args.get('page', DEFAULT_PAGE)
    per_page = request.args.get('per_page', DEFAULT_PAGE_SIZE)

    if not(str(page).isdigit() and int(page) > 0):
        raise InvalidUsage('page value should a positive number. Given %s' % page)

    if not(str(per_page).isdigit() and int(per_page) <= MAX_PAGE_SIZE):
        raise InvalidUsage('per_page should be a number with maximum value %s. Given %s'
                           % (MAX_PAGE_SIZE, per_page))

    return int(page), int(per_page)


def get_paginated_response(key, query, page=DEFAULT_PAGE, per_page=DEFAULT_PAGE_SIZE):
    """
    This function takes query object and then returns ApiResponse object containing
    JSON serializable list of objects by applying pagination on query using given
    constraints (page, per_page) as response body.
    Response object has extra pagination headers like
        X-Total    :  Total number of results found
        X-Per_page :  Number of items in one page
        X-Page     :  Page Number that is being sent

    List of object is packed in a dictionary where key is specified by user/developer.
    :param key: final dictionary will contain this key where value will be list if items.
    :param query: A query object on which pagination will be applied.
    :param page: page number
    :param per_page: page size
    :return: dictionary containing list of items

    :Example:
        >>> query = PushCampaign.query
        >>> page, per_page = 1, 10
        >>> response = get_paginated_response('campaigns', query, 1, 10)
        >>> response
        {
            "count": 10,
            "campaigns": [
                {
                    "name": "getTalent",
                    "body_text": "Abc.....xyz",
                    "url": "https://www.google.com"
                },
                .....
                .....
                .....
                {
                    "name": "Hiring New Talent",
                    "body_text": "Abc.....xyz",
                    "url": "https://www.gettalent.com/career"
                }
            ]
        }
    """
    assert key and isinstance(key, basestring), "key must be a valid string"
    # error_out=false, do nor raise error if these is nop object to return but return an empty list
    results = query.paginate(page, per_page, error_out=False)

    # convert model objects to serializable dictionaries
    items = [to_json(item) for item in results.items]
    headers = {
        'X-Total': results.total,
        'X-Per-Page': per_page,
        'X-Page': page
    }
    response = {
        key: items,
        'count': len(items)
    }
    return ApiResponse(response, headers=headers, status=200)
