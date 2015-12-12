"""Candidate Search Service APIs"""
from flask import request
from flask_restful import Resource
from candidate_service.common.utils.auth_utils import require_oauth
from candidate_service.modules.validators import validate_and_format_data
from candidate_service.modules.talent_cloud_search import search_candidates


class CandidateSearch(Resource):
    decorators = [require_oauth]

    def get(self):
        """
        Search candidates based on the given filter criteria
        """
        request_vars = validate_and_format_data(request.args)

        # Get domain_id from auth_user
        domain_id = request.user.domain_id
        limit = request_vars.get('limit')
        search_limit = int(limit) if limit else 15

        # If limit is not requested then the Search limit would be taken as 15, the default value
        candidate_search_results = search_candidates(domain_id, request_vars, search_limit)

        return candidate_search_results


class CandidateSearch(Resource):
    decorators = [require_oauth]

    def get(self):
        """
        Search candidates based on the given filter criteria
        """

        request_vars = validate_and_format_data(request.args)

        # If user wants to provide two of more set of search_params then we'll validate each dictionary of search_params
        # in search_params_list
        if 'search_params' in request_vars:
            search_params_list = request_vars.get('search_params')
            for index, search_params in enumerate(search_params_list):
                request_vars['search_params'][index] = validate_and_format_data(search_params)

        # Get domain_id from auth_user
        domain_id = request.user.domain_id
        limit = request_vars.get('limit')
        search_limit = int(limit) if limit else 15

        # If limit is not requested then the Search limit would be taken as 15, the default value
        candidate_search_results = search_candidates(domain_id, request_vars, search_limit)

        return candidate_search_results
