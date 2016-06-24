"""
Helper functions for tests written for the candidate_service
"""
import requests, operator
from time import sleep

# Third party
import pycountry as pc
from redo import retrier

# Models
from candidate_service.common.models.user import DomainRole

# User Roles
from candidate_service.common.utils.handy_functions import add_role_to_test_user

# Error handling
from candidate_service.common.error_handling import NotFoundError

from candidate_service.common.routes import CandidateApiUrl
from candidate_service.common.utils.test_utils import response_info


class AddUserRoles(object):
    """
    Class entails functions that will help add specific roles to test-user
    """

    @staticmethod
    def get(user):
        return add_role_to_test_user(user, [DomainRole.Roles.CAN_GET_CANDIDATES])

    @staticmethod
    def add(user):
        return add_role_to_test_user(user, [DomainRole.Roles.CAN_ADD_CANDIDATES])

    @staticmethod
    def edit(user):
        return add_role_to_test_user(user, [DomainRole.Roles.CAN_EDIT_CANDIDATES])

    @staticmethod
    def delete(user):
        return add_role_to_test_user(user, [DomainRole.Roles.CAN_DELETE_CANDIDATES])

    @staticmethod
    def add_and_get(user):
        return add_role_to_test_user(user, [DomainRole.Roles.CAN_ADD_CANDIDATES,
                                            DomainRole.Roles.CAN_GET_CANDIDATES])

    @staticmethod
    def add_and_delete(user):
        return add_role_to_test_user(user, [DomainRole.Roles.CAN_ADD_CANDIDATES,
                                            DomainRole.Roles.CAN_DELETE_CANDIDATES])

    @staticmethod
    def add_get_edit(user):
        return add_role_to_test_user(user, [DomainRole.Roles.CAN_ADD_CANDIDATES,
                                            DomainRole.Roles.CAN_GET_CANDIDATES,
                                            DomainRole.Roles.CAN_EDIT_CANDIDATES])

    @staticmethod
    def all_roles(user):
        return add_role_to_test_user(user, [DomainRole.Roles.CAN_ADD_CANDIDATES,
                                            DomainRole.Roles.CAN_GET_CANDIDATES,
                                            DomainRole.Roles.CAN_EDIT_CANDIDATES,
                                            DomainRole.Roles.CAN_DELETE_CANDIDATES])


def check_for_id(_dict):
    """
    Checks for id-key in candidate_dict and all its nested objects that must have an id-key
    :type _dict:    dict
    :return False if an id-key is missing in candidate_dict or any of its nested objects
    """
    assert isinstance(_dict, dict)
    # Get top level keys
    top_level_keys = _dict.keys()

    # Top level dict must have an id-key
    if not 'id' in top_level_keys:
        return False

    # Remove id-key from top level keys
    top_level_keys.remove('id')

    # Remove contact_history key since it will not have an id-key to begin with
    if 'contact_history' in top_level_keys:
        top_level_keys.remove('contact_history')
    if 'talent_pool_ids' in top_level_keys:
        top_level_keys.remove('talent_pool_ids')

    for key in top_level_keys:
        obj = _dict[key]
        if isinstance(obj, dict):
            # If obj is an empty dict, e.g. obj = {}, continue with the loop
            if not any(obj):
                continue

            check = id_exists(_dict=obj)
            if check is False:
                return check

        if isinstance(obj, list):
            list_of_dicts = obj
            for dictionary in list_of_dicts:
                # Invoke function again if any of dictionary's key's value is a list-of-objects
                for _key in dictionary:
                    if type(dictionary[_key]) == list:
                        for i in range(0, len(dictionary[_key])):
                            check = check_for_id(_dict=dictionary[_key][i])  # recurse
                            if check is False:
                                return check

                check = id_exists(_dict=dictionary)
                if check is False:
                    return check


def id_exists(_dict):
    """
    :return True if id-key is found in _dict, otherwise False
    """
    assert isinstance(_dict, dict)
    check = True
    # Get _dict's keys
    keys = _dict.keys()

    # Ensure id-key exists
    if not 'id' in keys:
        check = False

    return check


def remove_id_key(_dict):
    """
    Function removes the id-key from candidate_dict and all its nested objects
    """
    # Remove contact_history key since it will not have an id-key to begin with
    if 'contact_history' in _dict:
        del _dict['contact_history']
    if 'talent_pool_ids' in _dict:
        del _dict['talent_pool_ids']

    # Remove id-key from top level dict
    if 'id' in _dict:
        del _dict['id']

    # Get dict-keys
    keys = _dict.keys()

    for key in keys:
        obj = _dict[key]

        if isinstance(obj, dict):
            # If obj is an empty dict, e.g. obj = {}, continue with the loop
            if not any(obj):
                continue
            # Remove id-key if found
            if 'id' in obj:
                del obj['id']

        if isinstance(obj, list):
            list_of_dicts = obj
            for dictionary in list_of_dicts:
                # Remove id-key from each dictionary
                if 'id' in dictionary:
                    del dictionary['id']

                # Invoke function again if any of dictionary's key's value is a list-of-objects
                for _key in dictionary:
                    if isinstance(dictionary[_key], list):
                        for i in range(0, len(dictionary[_key])):
                            remove_id_key(_dict=dictionary[_key][i])  # recurse
    return _dict


def get_country_code_from_name(country_name):
    """
    Example: 'United States' = 'US'
    """
    try:
        country = pc.countries.get(name=country_name)
    except KeyError:
        return
    return country.alpha2


def get_int_version(x):
    """
    Function will only return input if it's an integer convertible
    :rtype:  int
    """
    try:
        return int(float(x))
    except ValueError:
        pass
    except TypeError:
        pass


def get_response(access_token, arguments_to_url, expected_count=1, attempts=20, pause=3, comp_operator='>='):
    """
    Function will a send request to cloud search until desired response is obtained.
    Since CS takes sometime to update, multiple attempts may be needed. A 3 seconds sleep time is set
    between each attempt.
    :param access_token: user's access token
    :param arguments_to_url: search params, i.e. "?tag_ids=1,2,3"
    :param expected_count: expected number of candidates that must be returned from CS
    :param attempts: maximum number of attempts that must be made
    :param pause: seconds to wait before making next attempt
    :param comp_operator: the comparison operator used to obtain desired response
    :rtype:  requests.Response
    """

    # Define comparison operator
    def get_comp_operator(comp_op):
        comps = {
            '==': operator.eq,
            '>=': operator.ge,
        }
        assert comp_op in comps, 'comparison operator not recognized'
        return comps[comp_op]

    # Comparison operator object
    comparison_operator = get_comp_operator(comp_op=comp_operator)

    # Cloud Search API URL
    url = CandidateApiUrl.CANDIDATE_SEARCH_URI + arguments_to_url

    headers = {'Authorization': 'Bearer %s' % access_token, 'Content-type': 'application/json'}

    for i in range(0, attempts):
        sleep(pause)
        resp = requests.get(url, headers=headers)
        print response_info(resp)
        if comparison_operator(len(resp.json()['candidates']), expected_count):
            return resp

    raise NotFoundError('Unable to get expected number of candidates')