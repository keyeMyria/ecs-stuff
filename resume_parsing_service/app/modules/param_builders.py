"""Code for building params dict from multiple types of requests objects."""
__author__ = 'erik@gettalent.com'
# pylint: disable=wrong-import-position, fixme, import-error
# Standard Library
import re
# Third Party
from contracts import contract
# Module Specific
from resume_parsing_service.app import logger
from resume_parsing_service.app.constants import error_constants
from resume_parsing_service.common.error_handling import InvalidUsage
from resume_parsing_service.common.models.misc import Product
from resume_parsing_service.common.utils.validators import get_json_data_if_validated
from resume_parsing_service.json_schemas.resumes_post_schema import create_candidate_schema


@contract
def build_params_from_json(request):
    """
    Takes in flask request object with content-type of 'application/json' and returns params used
    in resume processing functions.
    :param flask_request request:
    :return: Parsing parameters extracted from the requests JSON.
    :rtype: dict
    """
    NON_DEFAULT_JSON_KEYS = ('filepicker_key', 'source_id', 'talent_pool_ids', 'source_product_id')
    request_json = get_json_data_if_validated(
        request,
        create_candidate_schema,
        custom_msg=error_constants.JSON_SCHEMA_ERROR['message'],
        custom_error_code=error_constants.JSON_SCHEMA_ERROR['code'])
    logger.info('Beginning parsing with JSON params: {}'.format(request_json))

    params = {'resume_file': None}
    for k in NON_DEFAULT_JSON_KEYS:
        params[k] = request_json.get(k)

    params['create_candidate'] = request_json.get('create_candidate', False)
    params['filename'] = request_json.get('resume_file_name', params.get('filepicker_key'))

    return params


@contract
def build_params_from_form(request):
    """
    Takes in flask request object with content-type of 'multipart/form-data' and returns params
    used in resume processing functions.
    :param flask_request request:
    :return: Parsing parameters extracted from the requests form data.
    :rtype: dict
    """
    resume_file = request.files.get('resume_file')
    resume_file_name = request.form.get('resume_file_name')
    talent_pool_ids = None
    if not (resume_file and resume_file_name):
        raise InvalidUsage(
            error_message=error_constants.INVALID_ARGS_MOBILE['message'],
            error_code=error_constants.INVALID_ARGS_MOBILE['code'], )

    # create_candidate is passed as a string from a form so this extra processing is needed.
    create_mode = request.form.get('create_candidate', 'false')
    create_candidate = True if create_mode.lower() == 'true' else False
    filepicker_key = None
    talent_pool_ids_raw = request.form.get('talent_pool_ids')
    if talent_pool_ids_raw:
        talent_pool_ids = [int(x) for x in re.findall(r'\d+', talent_pool_ids_raw)]

    return {
        'create_candidate': create_candidate,
        'filename': resume_file_name,
        'filepicker_key': filepicker_key,
        'resume_file': resume_file,
        'source_product_id': Product.MOBILE,
        'talent_pool_ids': talent_pool_ids
    }
