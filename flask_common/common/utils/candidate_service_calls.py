"""File contains handy functions which can be used to call frequently used candidate_service API calls."""

from flask_common.common.routes import CandidateApiUrl
from flask_common.common.error_handling import InternalServerError
import requests
import json

__author__ = 'jitesh'


def search_candidates_from_params(search_params, access_token):
    """
    Calls the search service with given search criteria and returns the search result.
    :param search_params: Search params or search criteria upon which candidates would be filtered.
    :param access_token: User access token TODO: Change once server to server trusted calls are implemented.
    :return: search result based on search criteria.
    """
    return requests.get(
        url=CandidateApiUrl.SEARCH,
        params=search_params,
        headers={'Authorization': access_token if 'Bearer' in access_token else 'Bearer %s' % access_token}
    ).json()


def update_candidates_on_cloudsearch(access_token, candidate_ids):
    """
    Calls candidate search service to upload candidate documents for given candidate ids
    :param access_token: User's access token
    :type access_token: basestring
    :param candidate_ids: List of candidate ids
    :type candidate_ids: list
    """
    # Update Candidate Documents in Amazon Cloud Search
    headers = {'Authorization': access_token if 'Bearer' in access_token else 'Bearer %s' % access_token,
               'Content-Type': 'application/json'}
    response = requests.post(CandidateApiUrl.CANDIDATES_DOCUMENTS_URI, headers=headers,
                             data=json.dumps({'candidate_ids': candidate_ids}))

    if response.status_code != 204:
        raise InternalServerError("Error occurred while uplaoding candidates on cloudsearch. Status Code: %s Response: %s" % (response.status_code, response.json()))
