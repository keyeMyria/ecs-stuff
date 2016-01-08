"""
This file entails Candidate-restful-services for CRUD operations
"""
# Flask specific
from flask import request
from flask_restful import Resource

# Database connection
from candidate_service.common.models.db import db

# Validators
from candidate_service.common.utils.validators import (is_valid_email)
from candidate_service.modules.validators import (
    does_candidate_belong_to_user, is_custom_field_authorized,
    is_area_of_interest_authorized
)
from candidate_service.modules.json_schema import (
    candidates_resource_schema_post, candidates_resource_schema_patch,
    candidates_resource_schema_get
)
from jsonschema import validate, FormatChecker

# Decorators
from candidate_service.common.utils.auth_utils import require_oauth

# Error handling
from candidate_service.common.error_handling import ForbiddenError, InvalidUsage, NotFoundError
from candidate_service.custom_error_codes import CandidateCustomErrors as custom_error

# Models
from candidate_service.common.models.candidate import (
    Candidate, CandidateAddress, CandidateEducation, CandidateEducationDegree,
    CandidateEducationDegreeBullet, CandidateExperience, CandidateExperienceBullet,
    CandidateWorkPreference, CandidateEmail, CandidatePhone, CandidateMilitaryService,
    CandidatePreferredLocation, CandidateSkill, CandidateSocialNetwork, CandidateCustomField
)
from candidate_service.common.models.misc import AreaOfInterest, CustomField
from candidate_service.common.models.associations import CandidateAreaOfInterest

# Module
from candidate_service.modules.talent_candidates import (
    fetch_candidate_info, get_candidate_id_from_candidate_email,
    create_or_update_candidate_from_params, fetch_candidate_edits, fetch_candidate_views,
    _add_candidate_view
)
from candidate_service.modules.talent_cloud_search import upload_candidate_documents, delete_candidate_documents

from candidate_service.modules.talent_openweb import find_candidate_from_openweb


class CandidatesResource(Resource):
    decorators = [require_oauth()]

    def get(self, **kwargs):
        """
        Endpoint:   GET /v1/candidates
        :return     List of Candidate(s)
        :rtype      [str]
        """
        # Authenticated user
        authed_user = request.user

        get_all_domain_candidates = False

        # Parse request body & validate data
        body_dict = request.get_json()
        try:
            validate(instance=body_dict, schema=candidates_resource_schema_get)
        except Exception as e:
            raise InvalidUsage(error_message=e.message, error_code=custom_error.INVALID_INPUT)

        if not body_dict:
            get_all_domain_candidates = True

        if get_all_domain_candidates:  # Retrieve user's candidates
            candidates = authed_user.candidates

            retrieved_candidates = []
            for candidate in candidates:

                # If Candidate is web hidden, it is assumed "deleted"
                if candidate.is_web_hidden:
                    raise NotFoundError(error_message='Candidate not found',
                                        error_code=custom_error.CANDIDATE_IS_HIDDEN)

                retrieved_candidates.append(fetch_candidate_info(candidate))

        else:  # Retrieve via a list of candidate IDs
            candidate_ids = body_dict.get('candidate_ids')

            retrieved_candidates = []
            for candidate_id in candidate_ids:
                candidate = Candidate.get_by_id(candidate_id=candidate_id)
                if not candidate:
                    raise NotFoundError(error_message='Candidate not found',
                                        error_code=custom_error.CANDIDATE_NOT_FOUND)

                # If Candidate is web hidden, it is assumed "deleted"
                if candidate.is_web_hidden:
                    raise NotFoundError(error_message='Candidate not found',
                                        error_code=custom_error.CANDIDATE_NOT_FOUND)

                # Candidate ID must belong to user and its domain
                if not does_candidate_belong_to_user(authed_user, candidate_id):
                    raise ForbiddenError(error_message='Not authorized',
                                         error_code=custom_error.CANDIDATE_FORBIDDEN)

                retrieved_candidates.append(fetch_candidate_info(candidate))

        return {'candidates': retrieved_candidates}

    def post(self, **kwargs):
        """
        POST /v1/candidates
        input: {'candidates': [candidateObject1, candidateObject2, ...]}

        Creates new candidate(s).

        Takes a JSON dict containing:
            - a candidates key and a list of candidate-object(s) as values
        Function only accepts JSON dict.
        JSON dict must contain candidate's email address(s).

        :return: {'candidates': [{'id': candidate_id}, {'id': candidate_id}, ...]}
        """
        # Authenticate user
        authed_user = request.user
        body_dict = request.get_json(force=True)

        # Validate json data
        try:
            validate(instance=body_dict, schema=candidates_resource_schema_post,
                     format_checker=FormatChecker())
        except Exception as e:
            raise InvalidUsage(error_message=e.message, error_code=custom_error.INVALID_INPUT)

        created_candidate_ids = []
        for candidate_dict in body_dict.get('candidates'):

            emails = [{'label': email.get('label'), 'address': email.get('address'),
                       'is_default': email.get('is_default')} for email in candidate_dict.get('emails')]

            # Validate email addresses' format
            if filter(lambda email: not is_valid_email(email['address']), emails):
                raise InvalidUsage(error_message="Invalid email address/format",
                                   error_code=custom_error.INVALID_EMAIL)

            # Prevent user from adding custom field(s) to other domains
            custom_fields = candidate_dict.get('custom_fields') or []
            custom_field_ids = [custom_field.get('id') for custom_field in custom_fields]
            is_authorized = is_custom_field_authorized(custom_field_ids=custom_field_ids,
                                                       user_domain_id=authed_user.domain_id)
            if not is_authorized:
                raise ForbiddenError(error_message="Unauthorized custom field IDs",
                                     error_code=custom_error.CUSTOM_FIELD_FORBIDDEN)

            # Prevent user from adding area(s) of interest to other domains
            areas_of_interest = candidate_dict.get('areas_of_interest') or []
            area_of_interest_ids = [area_of_interest.get('id') for area_of_interest in areas_of_interest]
            is_authorized = is_area_of_interest_authorized(area_of_interest_ids=area_of_interest_ids,
                                                           user_domain_id=authed_user.domain_id)
            if not is_authorized:
                raise ForbiddenError(error_message="Unauthorized area of interest IDs",
                                     error_code=custom_error.AOI_FORBIDDEN)

            resp_dict = create_or_update_candidate_from_params(
                    user_id=authed_user.id,
                    is_creating=True,
                    first_name=candidate_dict.get('first_name'),
                    middle_name=candidate_dict.get('middle_name'),
                    last_name=candidate_dict.get('last_name'),
                    formatted_name=candidate_dict.get('full_name'),
                    status_id=candidate_dict.get('status_id'),
                    emails=emails,
                    phones=candidate_dict.get('phones'),
                    addresses=candidate_dict.get('addresses'),
                    educations=candidate_dict.get('educations'),
                    military_services=candidate_dict.get('military_services'),
                    areas_of_interest=areas_of_interest,
                    custom_fields=custom_fields,
                    social_networks=candidate_dict.get('social_networks'),
                    work_experiences=candidate_dict.get('work_experiences'),
                    work_preference=candidate_dict.get('work_preference'),
                    preferred_locations=candidate_dict.get('preferred_locations'),
                    skills=candidate_dict.get('skills'),
                    dice_social_profile_id=candidate_dict.get('openweb_id'),
                    dice_profile_id=candidate_dict.get('dice_profile_id'),
                    added_time=candidate_dict.get('added_time'),
                    source_id=candidate_dict.get('source_id'),
                    objective=candidate_dict.get('objective'),
                    summary=candidate_dict.get('summary'),
                    talent_pool_ids=candidate_dict.get('talent_pool_ids', {'add': [], 'delete': []})
            )
            created_candidate_ids.append(resp_dict['candidate_id'])

        # Add candidates to cloud search
        upload_candidate_documents(created_candidate_ids)

        return {'candidates': [{'id': candidate_id} for candidate_id in created_candidate_ids]}, 201

    def patch(self, **kwargs):
        """
        PATCH /v1/candidates
        Function can update candidate(s).

        Takes a JSON dict containing:
            - a candidates key and a list of candidate-object(s) as values
        Function only accepts JSON dict.
        JSON dict must contain candidate's ID.

        :return: {'candidates': [{'id': candidate_id}, {'id': candidate_id}, ...]}
        """
        # Authenticated user
        authed_user = request.user
        body_dict = request.get_json(force=True)

        # Validate json data
        try:
            validate(instance=body_dict, schema=candidates_resource_schema_patch,
                     format_checker=FormatChecker())
        except Exception as e:
            raise InvalidUsage(error_message=e.message, error_code=custom_error.INVALID_INPUT)

        updated_candidate_ids = []
        for candidate_dict in body_dict.get('candidates'):

            emails = candidate_dict.get('emails')
            if emails:
                emails = [{'id': email.get('id'), 'label': email.get('label'), 'address': email.get('address'),
                           'is_default': email.get('is_default')} for email in candidate_dict.get('emails')]

                # Validate email addresses' format
                if filter(lambda email: not is_valid_email(email['address']), emails):
                    raise InvalidUsage(error_message="Invalid email address/format",
                                       error_code=custom_error.INVALID_EMAIL)

            # Prevent user from updating custom field(s) from other domains
            custom_fields = candidate_dict.get('custom_fields') or []
            custom_field_ids = [custom_field.get('id') for custom_field in custom_fields]
            is_authorized = is_custom_field_authorized(custom_field_ids=custom_field_ids,
                                                       user_domain_id=authed_user.domain_id)
            if not is_authorized:
                raise ForbiddenError(error_message="Unauthorized custom field IDs",
                                     error_code=custom_error.CUSTOM_FIELD_FORBIDDEN)

            # Retrieve areas_of_interest
            areas_of_interest = candidate_dict.get('areas_of_interest') or []
            area_of_interest_ids = [area_of_interest.get('id') for area_of_interest in areas_of_interest]

            # If AreaOfInterest ID is not provided, assume it needs to be created
            if not any(area_of_interest_ids):
                pass

            # Prevent user from updating area(s) of interest from other domains
            is_authorized = is_area_of_interest_authorized(authed_user.domain_id, area_of_interest_ids)
            if not is_authorized:
                raise ForbiddenError(error_message="Unauthorized area of interest IDs",
                                     error_code=custom_error.AOI_FORBIDDEN)

            resp_dict = create_or_update_candidate_from_params(
                    user_id=authed_user.id,
                    is_updating=True,
                    candidate_id=candidate_dict.get('id'),
                    first_name=candidate_dict.get('first_name'),
                    middle_name=candidate_dict.get('middle_name'),
                    last_name=candidate_dict.get('last_name'),
                    formatted_name=candidate_dict.get('full_name'),
                    status_id=candidate_dict.get('status_id'),
                    emails=emails,
                    phones=candidate_dict.get('phones'),
                    addresses=candidate_dict.get('addresses'),
                    educations=candidate_dict.get('educations'),
                    military_services=candidate_dict.get('military_services'),
                    areas_of_interest=areas_of_interest,
                    custom_fields=custom_fields,
                    social_networks=candidate_dict.get('social_networks'),
                    work_experiences=candidate_dict.get('work_experiences'),
                    work_preference=candidate_dict.get('work_preference'),
                    preferred_locations=candidate_dict.get('preferred_locations'),
                    skills=candidate_dict.get('skills'),
                    dice_social_profile_id=candidate_dict.get('openweb_id'),
                    dice_profile_id=candidate_dict.get('dice_profile_id'),
                    added_time=candidate_dict.get('added_time'),
                    source_id=candidate_dict.get('source_id'),
                    objective=candidate_dict.get('objective'),
                    summary=candidate_dict.get('summary'),
                    talent_pool_ids=candidate_dict.get('talent_pool_id', {'add': [], 'delete': []})
            )
            updated_candidate_ids.append(resp_dict['candidate_id'])

        # Update candidates in cloud search
        upload_candidate_documents(updated_candidate_ids)

        return {'candidates': [{'id': updated_candidate_id}
                               for updated_candidate_id in updated_candidate_ids]}


class CandidateResource(Resource):
    decorators = [require_oauth()]

    def get(self, **kwargs):
        """
        Endpoints can do these operations:
            1. Fetch a candidate via two methods:
                I.  GET /v1/candidates/:id
                    Takes an integer as candidate's ID, parsed from kwargs

                OR
                II. GET /v1/candidates/:email
                    Takes a valid email address, parsed from kwargs

        :return:    A dict of candidate info
                    404 status if candidate is not found
        """
        # Authenticated user
        authed_user = request.user

        # Either candidate_id or candidate_email must be provided
        candidate_id, candidate_email = kwargs.get('id'), kwargs.get('email')

        if candidate_email:
            # Email address must be valid
            if not is_valid_email(candidate_email):
                raise InvalidUsage(error_message="A valid email address is required",
                                   error_code=custom_error.INVALID_EMAIL)

            # Get candidate ID from candidate's email
            candidate_id = get_candidate_id_from_candidate_email(candidate_email)
            if not candidate_id:
                raise NotFoundError(error_message='Candidate email not recognized',
                                    error_code=custom_error.CANDIDATE_NOT_FOUND)

        candidate = Candidate.get_by_id(candidate_id=candidate_id)
        if not candidate:
            raise NotFoundError(error_message='Candidate email not recognized',
                                error_code=custom_error.CANDIDATE_NOT_FOUND)

        # If Candidate is web hidden, it is assumed "deleted"
        if candidate.is_web_hidden:
            raise NotFoundError(error_message='Candidate not found',
                                error_code=custom_error.CANDIDATE_IS_HIDDEN)

        # Candidate must belong to user, and must be in the same domain as the user's domain
        if not does_candidate_belong_to_user(user_row=authed_user, candidate_id=candidate_id):
            raise ForbiddenError(error_message="Not authorized",
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        candidate_data_dict = fetch_candidate_info(candidate=candidate)

        # Add to CandidateView
        _add_candidate_view(user_id=authed_user.id, candidate_id=candidate_id)

        return {'candidate': candidate_data_dict}

    def delete(self, **kwargs):
        """
        Endpoints can do these operations:
            1. Delete a candidate via two methods:
                I.  DELETE /v1/candidates/:id
                OR
                II. DELETE /v1/candidates/:email

        Caveats:
        - Only candidate's owner can hide the Candidate.
        - Candidate must be in the same domain as authenticated user
        """
        # Authenticate user
        authed_user = request.user

        # candidate_id or candidate_email must be provided
        candidate_id, candidate_email = kwargs.get('id'), kwargs.get('email')
        if not candidate_id and not candidate_email:  # TODO: Flask already handles this, write test
            raise InvalidUsage(error_message="Candidate's ID or candidate's email must be provided.")

        if candidate_email:
            # Email address must be valid
            if not is_valid_email(candidate_email):
                raise InvalidUsage(error_message="A valid email address is required",
                                   error_code=custom_error.INVALID_EMAIL)

            # Get candidate ID from candidate's email
            candidate_id = get_candidate_id_from_candidate_email(candidate_email)
            if not candidate_id:
                raise NotFoundError(error_message='Candidate not found',
                                    error_code=custom_error.CANDIDATE_NOT_FOUND)

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message="Not authorized",
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        # Hide Candidate
        Candidate.set_is_web_hidden_to_true(candidate_id=candidate_id)

        # Delete candidate from cloud search
        delete_candidate_documents([candidate_id])
        return


class CandidateAddressResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoints:
             i. DELETE /v1/candidates/:candidate_id/addresses
            ii. DELETE /v1/candidates/:candidate_id/addresses/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        addresses or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id and address_id
        candidate_id, address_id = kwargs.get('candidate_id'), kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message="Not authorized",
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        if address_id:  # Delete specified address
            candidate_address = CandidateAddress.get_by_id(_id=address_id)
            if not candidate_address:
                raise NotFoundError(error_message='Candidate address not found',
                                    error_code=custom_error.ADDRESS_NOT_FOUND)

            # Address must belong to Candidate
            if candidate_address.candidate_id != candidate_id:
                raise ForbiddenError(error_message='Not authorized',
                                     error_code=custom_error.ADDRESS_FORBIDDEN)

            db.session.delete(candidate_address)

        else:  # Delete all of candidate's addresses
            candidate = Candidate.get_by_id(candidate_id)
            for address in candidate.candidate_addresses:
                db.session.delete(address)

        db.session.commit()
        return '', 204


class CandidateAreaOfInterestResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoints:
             i. DELETE /v1/candidates/:candidate_id/areas_of_interest
            ii. DELETE /v1/candidates/:candidate_id/areas_of_interest/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        areas of interest or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id and area_of_interest_id
        candidate_id, area_of_interest_id = kwargs.get('candidate_id'), kwargs.get('id')

        # Candidate must belong to user's domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        # Prevent user from deleting area_of_interest of candidates outside of its domain
        is_authorized = is_area_of_interest_authorized(authed_user.domain_id, [area_of_interest_id])
        if not is_authorized:
            raise ForbiddenError(error_message="Unauthorized area of interest IDs",
                                 error_code=custom_error.AOI_FORBIDDEN)

        if area_of_interest_id:  # Delete specified area of interest
            # Area of interest must be associated with candidate's CandidateAreaOfInterest
            candidate_aoi = CandidateAreaOfInterest.get_areas_of_interest(candidate_id,
                                                                          area_of_interest_id)
            if not candidate_aoi:
                raise ForbiddenError(error_message="Unauthorized area of interest IDs",
                                     error_code=custom_error.AOI_FORBIDDEN)

            # Delete CandidateAreaOfInterest
            db.session.delete(candidate_aoi)

        else:  # Delete all of Candidate's areas of interest
            domain_aois = AreaOfInterest.get_domain_areas_of_interest(domain_id=authed_user.domain_id)
            areas_of_interest_id = [aoi.id for aoi in domain_aois]
            for aoi_id in areas_of_interest_id:
                candidate_aoi = CandidateAreaOfInterest.get_areas_of_interest(candidate_id, aoi_id)
                if not candidate_aoi:
                    raise NotFoundError(error_message='Candidate area of interest not found',
                                        error_code=custom_error.AOI_NOT_FOUND)

                db.session.delete(candidate_aoi)

        db.session.commit()
        return '', 204


class CandidateCustomFieldResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoints:
             i. DELETE /v1/candidates/:candidate_id/custom_fields
            ii. DELETE /v1/candidates/:candidate_id/custom_fields/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        custom fields or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id and can_cf_id (candidate custom field ID, i.e. CandidateCustomField.id)
        candidate_id, can_cf_id = kwargs.get('candidate_id'), kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        # Custom fields must belong to user's domain
        if not is_custom_field_authorized(authed_user.domain_id, [can_cf_id]):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CUSTOM_FIELD_FORBIDDEN)

        if can_cf_id:  # Delete specified custom field
            candidate_custom_field = CandidateCustomField.get_by_id(_id=can_cf_id)
            if not candidate_custom_field:
                raise NotFoundError(error_message='Candidate custom field not found',
                                    error_code=custom_error.CUSTOM_FIELD_NOT_FOUND)

            db.session.delete(candidate_custom_field)

        else:  # Delete all of Candidate's custom fields
            domain_custom_fields = CustomField.get_domain_custom_fields(domain_id=authed_user.domain_id)
            custom_field_ids = [custom_field.id for custom_field in domain_custom_fields]
            for cf_id in custom_field_ids:
                candidate_custom_field = CandidateCustomField.get_custom_field(candidate_id, cf_id)
                if not candidate_custom_field:
                    raise NotFoundError(error_message='Candidate custom field not found',
                                        error_code=custom_error.CUSTOM_FIELD_NOT_FOUND)

                db.session.delete(candidate_custom_field)

        db.session.commit()
        return '', 204


class CandidateEducationResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoints:
              i. DELETE /v1/candidates/:candidate_id/educations
             ii. DELETE /v1/candidates/:candidate_id/educations/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        educations or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id and education_id
        candidate_id, education_id = kwargs.get('candidate_id'), kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        if education_id:  # Delete specified Candidate's education
            can_education = CandidateEducation.get_by_id(_id=education_id)
            if not can_education:
                raise NotFoundError(error_message='Education not found',
                                    error_code=custom_error.EDUCATION_NOT_FOUND)

            # Education must belong to Candidate
            if can_education.candidate_id != candidate_id:
                raise ForbiddenError(error_message='Not authorized',
                                     error_code=custom_error.EDUCATION_FORBIDDEN)

            db.session.delete(can_education)

        else:  # Delete all of Candidate's educations
            can_educations = db.session.query(CandidateEducation). \
                filter_by(candidate_id=candidate_id).all()
            for can_education in can_educations:
                db.session.delete(can_education)

        db.session.commit()
        return '', 204


class CandidateEducationDegreeResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoints:
             i. DELETE /v1/candidates/:candidate_id/educations/:education_id/degrees
            ii. DELETE /v1/candidates/:candidate_id/educations/:education_id/degrees/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        education-degrees or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id, education_id, and degree_id
        candidate_id, education_id = kwargs.get('candidate_id'), kwargs.get('education_id')
        degree_id = kwargs.get('id')

        # Candidate must belong to user's domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        if degree_id:  # Delete specified degree
            # Verify that degree belongs to education, and education belongs to candidate
            candidate_degree = db.session.query(CandidateEducation).join(CandidateEducationDegree). \
                filter(CandidateEducation.candidate_id == candidate_id). \
                filter(CandidateEducationDegree.id == degree_id).first()
            if not candidate_degree:
                raise NotFoundError(error_message='Education degree not found',
                                    error_code=custom_error.DEGREE_NOT_FOUND)

            db.session.delete(candidate_degree)

        else:  # Delete all degrees
            education = CandidateEducation.get_by_id(_id=education_id)
            if not education:
                raise NotFoundError(error_message='Education not found',
                                    error_code=custom_error.EDUCATION_NOT_FOUND)

            # Education must belong to candidate
            if education.candidate_id != candidate_id:
                raise ForbiddenError(error_message='Not Authorized',
                                     error_code=custom_error.EDUCATION_FORBIDDEN)

            degrees = education.candidate_education_degrees
            for degree in degrees:
                db.session.delete(degree)

        db.session.commit()
        return '', 204


class CandidateEducationDegreeBulletResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoints:
             i. DELETE /v1/candidates/:candidate_id/educations/:education_id/degrees/:degree_id/bullets
            ii. DELETE /v1/candidates/:candidate_id/educations/:education_id/degrees/:degree_id/bullets/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        education-degree-bullets or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get required IDs
        candidate_id, education_id = kwargs.get('candidate_id'), kwargs.get('education_id')
        degree_id, bullet_id = kwargs.get('degree_id'), kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        if bullet_id:  # Delete specified bullet
            # degree_bullet must belongs to degree; degree must belongs to education;
            # and education must belong to candidate
            candidate_degree_bullet = db.session.query(CandidateEducationDegreeBullet). \
                join(CandidateEducationDegree).join(CandidateEducation). \
                filter(CandidateEducation.candidate_id == candidate_id). \
                filter(CandidateEducation.id == education_id). \
                filter(CandidateEducationDegree.id == degree_id). \
                filter(CandidateEducationDegreeBullet.id == bullet_id).first()
            if not candidate_degree_bullet:
                raise NotFoundError(error_message='Degree bullet not found',
                                    error_code=custom_error.DEGREE_NOT_FOUND)

            db.session.delete(candidate_degree_bullet)

        else:  # Delete all bullets
            education = CandidateEducation.get_by_id(_id=education_id)
            if not education:
                raise NotFoundError(error_message='Candidate education not found',
                                    error_code=custom_error.EDUCATION_NOT_FOUND)

            # Education must belong to Candidate
            if education.candidate_id != candidate_id:
                raise ForbiddenError(error_message='Not authorized',
                                     error_code=custom_error.EDUCATION_FORBIDDEN)

            degree = db.session.query(CandidateEducationDegree).get(degree_id)
            if not degree:
                raise NotFoundError(error_message='Candidate education degree not found',
                                    error_code=custom_error.DEGREE_NOT_FOUND)

            degree_bullets = degree.candidate_education_degree_bullets
            if not degree_bullets:
                raise NotFoundError(error_message='Candidate education degree bullet not found',
                                    error_code=custom_error.DEGREE_BULLET_NOT_FOUND)

            for degree_bullet in degree_bullets:
                db.session.delete(degree_bullet)

        db.session.commit()
        return '', 204


class CandidateExperienceResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoints:
             i. DELETE /v1/candidates/:candidate_id/experiences
            ii. DELETE /v1/candidates/:candidate_id/experiences/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        work_experiences or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id and experience_id
        candidate_id, experience_id = kwargs.get('candidate_id'), kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        if experience_id:  # Delete specified experience
            experience = CandidateExperience.get_by_id(_id=experience_id)
            if not experience:
                raise NotFoundError(error_message='Candidate experience not found',
                                    error_code=custom_error.EXPERIENCE_NOT_FOUND)

            # Experience must belong to Candidate
            if experience.candidate_id != candidate_id:
                raise ForbiddenError(error_message='Not authorized',
                                     error_code=custom_error.EXPERIENCE_FORBIDDEN)

            db.session.delete(experience)

        else:  # Delete all experiences
            experiences = db.session.query(CandidateExperience). \
                filter_by(candidate_id=candidate_id).all()
            for experience in experiences:
                db.session.delete(experience)

        db.session.commit()
        return '', 204


class CandidateExperienceBulletResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoints:
             i. DELETE /v1/candidates/:candidate_id/experiences/:experience_id/bullets
            ii. DELETE /v1/candidates/:candidate_id/experiences/:experience_id/bullets/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        work_experience-bullets or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get required IDs
        candidate_id, experience_id = kwargs.get('candidate_id'), kwargs.get('experience_id')
        bullet_id = kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        if bullet_id:
            # Experience must belong to Candidate and bullet must belong to CandidateExperience
            bullet = db.session.query(CandidateExperienceBullet).join(CandidateExperience).join(Candidate). \
                filter(CandidateExperienceBullet.id == bullet_id). \
                filter(CandidateExperience.id == experience_id). \
                filter(CandidateExperience.candidate_id == candidate_id).first()
            if not bullet:
                raise NotFoundError(error_message='Candidate experience bullet not found',
                                    error_code=custom_error.EXPERIENCE_BULLET_NOT_FOUND)

            db.session.delete(bullet)

        else:  # Delete all bullets
            experience = CandidateExperience.get_by_id(_id=experience_id)
            if not experience:
                raise NotFoundError(error_message='Candidate experience not found',
                                    error_code=custom_error.EXPERIENCE_NOT_FOUND)

            # Experience must belong to Candidate
            if experience.candidate_id != candidate_id:
                raise ForbiddenError(error_message='Not authorized',
                                     error_code=custom_error.EXPERIENCE_FORBIDDEN)

            bullets = experience.candidate_experience_bullets
            if not bullets:
                raise NotFoundError(error_message='Candidate experience bullet not found',
                                    error_code=custom_error.EXPERIENCE_BULLET_NOT_FOUND)

            for bullet in bullets:
                db.session.delete(bullet)

        db.session.commit()
        return '', 204


class CandidateEmailResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoints:
             i. DELETE /v1/candidates/:candidate_id/emails
            ii. DELETE /v1/candidates/:candidate_id/emails/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        emails or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id and email_id
        candidate_id, email_id = kwargs.get('candidate_id'), kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        if email_id:  # Delete specified email
            email = CandidateEmail.get_by_id(_id=email_id)
            if not email:
                raise NotFoundError(error_message='Candidate email not found',
                                    error_code=custom_error.EMAIL_NOT_FOUND)

            # Email must belong to candidate
            if email.candidate_id != candidate_id:
                raise ForbiddenError(error_message='Not authorized',
                                     error_code=custom_error.EMAIL_FORBIDDEN)

            db.session.delete(email)

        else:  # Delete all of Candidate's emails
            emails = db.session.query(CandidateEmail).filter_by(candidate_id=candidate_id).all()
            for email in emails:
                db.session.delete(email)

        db.session.commit()
        return '', 204


class CandidateMilitaryServiceResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoints:
             i. DELETE /v1/candidates/:candidate_id/military_services
            ii. DELETE /v1/candidates/:candidate_id/military_services/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        military_services or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id and military_service_id
        candidate_id, military_service_id = kwargs.get('candidate_id'), kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        if military_service_id:  # Delete specified military-service
            military_service = CandidateMilitaryService.get_by_id(_id=military_service_id)
            if not military_service:
                raise NotFoundError(error_message='Candidate military service not found',
                                    error_code=custom_error.MILITARY_NOT_FOUND)

            # CandidateMilitaryService must belong to Candidate
            if military_service.candidate_id != candidate_id:
                raise ForbiddenError(error_message='Not authorized',
                                     error_code=custom_error.MILITARY_FORBIDDEN)

            db.session.delete(military_service)

        else:  # Delete all of Candidate's military services
            military_services = db.session.query(CandidateMilitaryService). \
                filter_by(candidate_id=candidate_id).all()
            for military_service in military_services:
                db.session.delete(military_service)

        db.session.commit()
        return '', 204


class CandidatePhoneResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoints:
             i. DELETE /v1/candidates/:candidate_id/phones
            ii. DELETE /v1/candidates/:candidate_id/phones/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        phones or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id and phone_id
        candidate_id, phone_id = kwargs.get('candidate_id'), kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        if phone_id:  # Delete specified phone
            phone = CandidatePhone.get_by_id(_id=phone_id)
            if not phone:
                raise NotFoundError(error_message='Candidate phone not found',
                                    error_code=custom_error.PHONE_NOT_FOUND)

            # Phone must belong to Candidate
            if phone.candidate_id != candidate_id:
                raise ForbiddenError(error_message='Not authorized',
                                     error_code=custom_error.PHONE_FORBIDDEN)

            db.session.delete(phone)

        else:  # Delete all of Candidate's phones
            phones = db.session.query(CandidatePhone).filter_by(candidate_id=candidate_id).all()
            for phone in phones:
                db.session.delete(phone)

        db.session.commit()
        return '', 204


class CandidatePreferredLocationResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoints:
             i. DELETE /v1/candidates/:candidate_id/preferred_locations
            ii. DELETE /v1/candidates/:candidate_id/preferred_locations/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        preferred_locations or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id and preferred_location_id
        candidate_id, preferred_location_id = kwargs.get('candidate_id'), kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        if preferred_location_id:  # Delete specified preferred location
            preferred_location = CandidatePreferredLocation.get_by_id(_id=preferred_location_id)
            if not preferred_location_id:
                raise NotFoundError(error_message='Candidate preferred location not found',
                                    error_code=custom_error.PREFERRED_LOCATION_NOT_FOUND)

            # Preferred location must belong to Candidate
            if preferred_location.candidate_id != candidate_id:
                raise ForbiddenError(error_message='Not authorized',
                                     error_code=custom_error.PREFERRED_LOCATION_FORBIDDEN)

            db.session.delete(preferred_location)

        else:  # Delete all of Candidate's preferred locations
            preferred_locations = db.session.query(CandidatePreferredLocation). \
                filter_by(candidate_id=candidate_id).all()
            for preferred_location in preferred_locations:
                db.session.delete(preferred_location)

        db.session.commit()
        return '', 204


class CandidateSkillResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoint:
             i. DELETE /v1/candidates/:candidate_id/skills
            ii. DELETE /v1/candidates/:candidate_id/skills/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        skills or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id and work_preference_id
        candidate_id, skill_id = kwargs.get('candidate_id'), kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        if skill_id:  # Delete specified skill
            # skill = CandidateSkill.get_by_id(_id=skill_id)
            skill = db.session.query(CandidateSkill).get(skill_id)
            if not skill:
                raise NotFoundError(error_message='Candidate skill not found',
                                    error_code=custom_error.SKILL_NOT_FOUND)

            # Skill must belong to Candidate
            if skill.candidate_id != candidate_id:
                raise ForbiddenError(error_message='Not authorized',
                                     error_code=custom_error.SKILL_FORBIDDEN)

            db.session.delete(skill)

        else:  # Delete all of Candidate's skills
            skills = db.session.query(CandidateSkill).filter_by(candidate_id=candidate_id).all()
            for skill in skills:
                db.session.delete(skill)

        db.session.commit()
        return '', 204


class CandidateSocialNetworkResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoint:
             i. DELETE /v1/candidates/:candidate_id/social_networks
            ii. DELETE /v1/candidates/:candidate_id/social_networks/:id
        Depending on the endpoint requested, function will delete all of Candidate's
        social_networks or just a single one.
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id and work_preference_id
        candidate_id, social_networks_id = kwargs.get('candidate_id'), kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        if social_networks_id:  # Delete specified social network
            # social_network = CandidateSocialNetwork.get_by_id(_id=social_networks_id)
            social_network = db.session.query(CandidateSocialNetwork).get(social_networks_id)

            if not social_network:
                raise NotFoundError(error_message='Candidate social network not found',
                                    error_code=custom_error.SOCIAL_NETWORK_NOT_FOUND)

            # Social network must belong to Candidate
            if social_network.candidate_id != candidate_id:
                raise ForbiddenError(error_message='Not authorized',
                                     error_code=custom_error.SOCIAL_NETWORK_FORBIDDEN)

            db.session.delete(social_network)

        else:  # Delete all of Candidate's social networks
            social_networks = db.session.query(CandidateSocialNetwork). \
                filter_by(candidate_id=candidate_id).all()
            for social_network in social_networks:
                db.session.delete(social_network)

        db.session.commit()
        return '', 204


class CandidateWorkPreferenceResource(Resource):
    decorators = [require_oauth()]

    def delete(self, **kwargs):
        """
        Endpoint: DELETE /v1/candidates/:candidate_id/work_preference/:id
        Function will delete Candidate's work_preference
        """
        # Authenticated user
        authed_user = request.user

        # Get candidate_id and work_preference_id
        candidate_id, work_preference_id = kwargs.get('candidate_id'), kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        work_preference = CandidateWorkPreference.get_by_id(_id=work_preference_id)
        if not work_preference:
            raise NotFoundError(error_message='Candidate work preference not found',
                                error_code=custom_error.WORK_PREF_NOT_FOUND)

        # CandidateWorkPreference must belong to Candidate
        if work_preference.candidate_id != candidate_id:
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.WORK_PREF_FORBIDDEN)

        db.session.delete(work_preference)
        db.session.commit()
        return '', 204


class CandidateEditResource(Resource):
    decorators = [require_oauth()]

    def get(self, **kwargs):
        """
        Endpoint: GET /v1/candidates/:id/edits
        Function will return requested Candidate with all of its edits.
        """
        # Authenticated user & candidate_id
        authed_user, candidate_id = request.user, kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized',
                                 error_code=custom_error.CANDIDATE_FORBIDDEN)

        candidate_edits = fetch_candidate_edits(candidate_id=candidate_id)
        return {'candidate': {'id': candidate_id, 'edits': [
            candidate_edit for candidate_edit in candidate_edits]}}


class CandidateOpenWebResource(Resource):
    decorators = [require_oauth()]

    def get(self, **kwargs):
        """
        Endpoint: GET /v1/candidates/openweb?url=http://...
        Function will return requested Candidate url from openweb endpoint
        """
        # Authenticated user
        authed_user = request.user
        url = request.args.get('url')
        find_candidate = find_candidate_from_openweb(url)
        if find_candidate:
            candiate = fetch_candidate_info(find_candidate)
            return {'candidate': candiate}
        else:
            raise NotFoundError(error_message="Candidate not found",
                                error_code=custom_error.CANDIDATE_NOT_FOUND)


class CandidateViewResource(Resource):
    decorators = [require_oauth()]

    def get(self, **kwargs):
        """
        Endpoint:  GET /v1/candidates/:id/views
        Function will return all view information pertaining to the requested Candidate
        """
        # Authenticated user & candidate_id
        authed_user, candidate_id = request.user, kwargs.get('id')

        # Candidate must belong to user and its domain
        if not does_candidate_belong_to_user(authed_user, candidate_id):
            raise ForbiddenError(error_message='Not authorized')

        candidate_views = fetch_candidate_views(candidate_id=candidate_id)
        return {'candidate': {'views': [view for view in candidate_views]}}

