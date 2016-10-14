import datetime
import graphene

from graphql_service.common.models.db import db
from graphql_service.common.models.user import Domain
from graphql_service.common.models.candidate import Candidate
from graphql_service.common.utils.candidate_utils import get_candidate_if_validated
from schema import CandidateType

from flask import request

from talent_candidates import add_or_edit_candidate_from_params

from graphql_service.dynamodb.dynamo_actions import DynamoDB, set_empty_strings_to_null

# Utilities
from graphql_service.common.utils.datetime_utils import DatetimeUtils


class AddressInput(graphene.InputObjectType):
    address_line_1 = graphene.String()
    address_line_2 = graphene.String()
    city = graphene.String()
    state = graphene.String()
    zip_code = graphene.String()
    po_box = graphene.String()
    is_default = graphene.Boolean()
    coordinates = graphene.String()
    updated_time = graphene.String()
    iso3166_subdivision = graphene.String()
    iso3166_country = graphene.String()


class EmailInput(graphene.InputObjectType):
    address = graphene.String()
    label = graphene.String()
    is_default = graphene.Boolean()


class EducationDegreeInput(graphene.InputObjectType):
    degree_type = graphene.String()
    degree_title = graphene.String()
    start_year = graphene.Int()
    start_month = graphene.Int()
    end_year = graphene.Int()
    end_month = graphene.Int()
    gpa = graphene.Float()
    added_datetime = graphene.String()
    updated_datetime = graphene.String()
    concentration = graphene.String()
    comments = graphene.String()


class EducationInput(graphene.InputObjectType):
    school_name = graphene.String()
    school_type = graphene.String()
    city = graphene.String()
    state = graphene.String()
    iso3166_subdivision = graphene.String()
    is_current = graphene.Boolean()
    added_datetime = graphene.String()
    updated_datetime = graphene.String()

    # Nested data
    degrees = graphene.List(EducationDegreeInput)


class ExperienceInput(graphene.InputObjectType):
    organization = graphene.String()
    position = graphene.String()
    city = graphene.String()
    iso3166_subdivision = graphene.String()
    iso3166_country = graphene.String()
    start_year = graphene.Int()
    start_month = graphene.Int()
    end_year = graphene.Int()
    end_month = graphene.Int()
    is_current = graphene.Boolean()
    added_datetime = graphene.String()
    description = graphene.String()


class MilitaryServiceInput(graphene.InputObjectType):
    service_status = graphene.String()
    highest_rank = graphene.String()
    highest_grade = graphene.String()
    branch = graphene.String()
    comments = graphene.String()
    start_year = graphene.Int()
    start_month = graphene.Int()
    end_year = graphene.Int()
    end_month = graphene.Int()
    iso3166_country = graphene.String()
    added_datetime = graphene.String()


class NoteInput(graphene.InputObjectType):
    title = graphene.String()
    comment = graphene.String(required=True)
    added_datetime = graphene.String()


class PhoneInput(graphene.InputObjectType):
    label = graphene.String()
    value = graphene.String()
    is_default = graphene.Boolean()


class PhotoInput(graphene.InputObjectType):
    image_url = graphene.String()
    is_default = graphene.Boolean()
    added_datetime = graphene.String()


class PreferredLocationInput(graphene.InputObjectType):
    iso3166_country = graphene.String()
    iso3166_subdivision = graphene.String()
    city = graphene.String()
    zip_code = graphene.String()
    added_datetime = graphene.String()


class ReferenceInput(graphene.InputObjectType):
    person_name = graphene.String()
    position_title = graphene.String()
    comments = graphene.String()
    added_datetime = graphene.String()


class SkillInput(graphene.InputObjectType):
    name = graphene.String()
    total_months_used = graphene.Int()
    last_used_year = graphene.Int()
    last_used_month = graphene.Int()
    added_datetime = graphene.String()


class SocialNetworkInput(graphene.InputObjectType):
    name = graphene.String()
    profile_url = graphene.String()
    added_datetime = graphene.String()


class TagInput(graphene.InputObjectType):
    name = graphene.String(required=True)
    added_datetime = graphene.String()


class WorkPreferenceInput(graphene.InputObjectType):
    relocate = graphene.Boolean()
    authorization = graphene.String()
    telecommute = graphene.Boolean()
    travel_percentage = graphene.Int()
    hourly_rate = graphene.Float()
    salary = graphene.Int()
    tax_terms = graphene.String()


class CreateCandidate(graphene.Mutation):
    ok = graphene.Boolean()
    id = graphene.Int()
    candidate = graphene.Field(lambda: CandidateType)

    class Input(object):
        """
        Class contains optional input fields for creating candidate
        """
        # Primary data
        first_name = graphene.String()
        middle_name = graphene.String()
        last_name = graphene.String()
        formatted_name = graphene.String()
        user_id = graphene.Int()
        filename = graphene.String()
        objective = graphene.String()
        summary = graphene.String()
        total_months_experience = graphene.Int()
        added_datetime = graphene.String()
        updated_datetime = graphene.String()
        candidate_status_id = graphene.Int()
        source_id = graphene.Int()
        culture_id = graphene.Int()

        # Secondary data
        addresses = graphene.List(AddressInput)
        # areas_of_interest = graphene.List(AreaOfInterestInput)
        # custom_fields = graphene.List(CustomFieldInput)
        educations = graphene.List(EducationInput)
        emails = graphene.List(EmailInput)
        experiences = graphene.List(ExperienceInput)
        military_services = graphene.List(MilitaryServiceInput)
        notes = graphene.List(NoteInput)
        phones = graphene.List(PhoneInput)
        photos = graphene.List(PhotoInput)
        preferred_locations = graphene.List(PreferredLocationInput)
        references = graphene.List(ReferenceInput)
        skills = graphene.List(SkillInput)
        social_networks = graphene.List(SocialNetworkInput)
        tags = graphene.List(TagInput)
        # work_preference = graphene.ObjectType(WorkPreferenceInput)

    def mutate(self, args, context, info):
        resume_url = args.get('resume_url')
        candidate_data = dict(
            first_name=args.get('first_name'),
            middle_name=args.get('middle_name'),
            last_name=args.get('last_name'),
            formatted_name=args.get('formatted_name'),
            # user_id=request.user.id, # TODO: will work after user is authenticated
            filename=resume_url,
            objective=args.get('objective'),
            summary=args.get('summary'),
            added_time=args.get('added_datetime') or datetime.datetime.utcnow(),
            candidate_status_id=args.get('status_id'),
            source_id=args.get('source_id'),
            culture_id=args.get('culture_id')
        )
        # todo: add validation: does candidate exits? Is candidate hidden?, etc.
        # Insert candidate into MySQL database
        new_candidate = Candidate(**candidate_data)
        db.session.add(new_candidate)
        db.session.flush()

        candidate_id = new_candidate.id

        # We need candidate's MySQL-generated ID as a unique identifier for DynamoDB's primary key
        # DynamoDB does not accept datetime objects, hence it must be converted to string
        del candidate_data['added_time']
        del candidate_data['filename']
        candidate_data.update(
            id=candidate_id,
            added_datetime=DatetimeUtils.to_utc_str(datetime.datetime.utcnow()),
            resume_url=resume_url
        )

        addresses = args.get('addresses')
        areas_of_interest = args.get('areas_of_interest')
        educations = args.get('educations')
        emails = args.get('emails')
        experiences = args.get('experiences')
        military_services = args.get('military_services')
        notes = args.get('notes')
        phones = args.get('phones')
        photos = args.get('photos')
        preferred_locations = args.get('preferred_locations')
        references = args.get('references')
        skills = args.get('skills')
        social_networks = args.get('social_networks')
        tags = args.get('tags')
        # work_preference = args.get('work_preference')

        # Save candidate's primary data
        # ValidateAndSave.candidate_data = candidate_data
        try:
            # candidate = DynamoDB.get_candidate(candidate_id)

            candidates_validated_data = add_or_edit_candidate_from_params(
                user_id=19,
                primary_data=candidate_data,
                areas_of_interest=areas_of_interest,
                addresses=addresses,
                educations=educations,
                emails=emails,
                experiences=experiences,
                military_services=military_services,
                notes=notes,
                phones=phones,
                photos=photos,
                preferred_locations=preferred_locations,
                references=references,
                skills=skills,
                social_networks=social_networks,
                tags=tags,
                added_datetime=candidate_data['added_datetime']
                # work_preference=work_preference
            )
        except Exception as e:
            print "Something went wrong: {}".format(e.message)
            return e
        else:
            ok = True

        # Commit transaction
        db.session.commit()

        DynamoDB.add_candidate(set_empty_strings_to_null(candidates_validated_data))

        return CreateCandidate(candidate=CandidateType(**candidate_data),
                               ok=ok,
                               id=candidate_id)


class UpdateCandidate(graphene.Mutation):
    ok = graphene.Boolean()
    id = graphene.Int()
    candidate = graphene.Field(lambda: CandidateType)

    class Input(object):
        """
        Class contains optional input fields for creating candidate
        """
        # Primary data
        id = graphene.Int()
        first_name = graphene.String()
        middle_name = graphene.String()
        last_name = graphene.String()
        formatted_name = graphene.String()
        user_id = graphene.Int()
        resume_url = graphene.String()
        objective = graphene.String()
        summary = graphene.String()
        total_months_experience = graphene.Int()
        updated_datetime = graphene.String()
        candidate_status_id = graphene.Int()
        source_id = graphene.Int()
        culture_id = graphene.Int()

        # Secondary data
        addresses = graphene.List(AddressInput)
        # areas_of_interest = graphene.List(AreaOfInterestInput)
        # custom_fields = graphene.List(CustomFieldInput)
        educations = graphene.List(EducationInput)
        emails = graphene.List(EmailInput)
        experiences = graphene.List(ExperienceInput)
        military_services = graphene.List(MilitaryServiceInput)
        notes = graphene.List(NoteInput)
        phones = graphene.List(PhoneInput)
        photos = graphene.List(PhotoInput)
        preferred_locations = graphene.List(PreferredLocationInput)
        references = graphene.List(ReferenceInput)
        skills = graphene.List(SkillInput)
        social_networks = graphene.List(SocialNetworkInput)
        tags = graphene.List(TagInput)
        # work_preference = graphene.ObjectType(WorkPreferenceInput)

    def mutate(self, args, context, info):
        candidate_data = dict(
            first_name=args.get('first_name'),
            middle_name=args.get('middle_name'),
            last_name=args.get('last_name'),
            formatted_name=args.get('formatted_name'),
            # user_id=request.user.id, # TODO: will work after user is authenticated
            resume_url=args.get('resume_url'),
            objective=args.get('objective'),
            summary=args.get('summary'),
            candidate_status_id=args.get('status_id'),
            source_id=args.get('source_id'),
            culture_id=args.get('culture_id')
        )
        # todo: add validation: does candidate exits? Is candidate hidden?, etc.
        # Retrieve candidate
        candidate_id = args.get('id')

        # TODO: uncomment function once user object is available
        # get_candidate_if_validated(user, candidate_id)

        addresses = args.get('addresses')
        areas_of_interest = args.get('areas_of_interest')
        educations = args.get('educations')
        emails = args.get('emails')
        experiences = args.get('experiences')
        military_services = args.get('military_services')
        notes = args.get('notes')
        phones = args.get('phones')
        photos = args.get('photos')
        preferred_locations = args.get('preferred_locations')
        references = args.get('references')
        skills = args.get('skills')
        social_networks = args.get('social_networks')
        tags = args.get('tags')
        # work_preference = args.get('work_preference')

        # Save candidate's primary data
        # ValidateAndSave.candidate_data = candidate_data
        try:
            existing_candidate_data = DynamoDB.get_candidate(candidate_id)
            if not existing_candidate_data:
                raise Exception  # TODO: update with new method of error handling or raise InvalidUsage error

            candidates_validated_data = add_or_edit_candidate_from_params(
                user_id=19,  # TODO: user ID to be set via request.user once authentication has been set
                primary_data=candidate_data,
                is_updating=True,
                existing_candidate_data=existing_candidate_data,
                areas_of_interest=areas_of_interest,
                addresses=addresses,
                educations=educations,
                emails=emails,
                experiences=experiences,
                military_services=military_services,
                notes=notes,
                phones=phones,
                photos=photos,
                preferred_locations=preferred_locations,
                references=references,
                skills=skills,
                social_networks=social_networks,
                tags=tags,
                updated_datetime=DatetimeUtils.to_utc_str(datetime.datetime.utcnow())
                # work_preference=work_preference
            )
        except Exception as e:
            print "Something went wrong: {}".format(e.message)
            return e
        else:
            ok = True

        # Commit transaction
        db.session.commit()

        DynamoDB.update_candidate(
            candidate_id=candidate_id,
            candidate_data=set_empty_strings_to_null(candidates_validated_data))

        return UpdateCandidate(candidate=CandidateType(**candidate_data),
                               ok=ok,
                               id=candidate_id)


class DeleteCandidate(graphene.Mutation):
    ok = graphene.Boolean()
    id = graphene.Int()

    class Input(object):
        id = graphene.Int()

    def mutate(self, args, context, info):
        # todo: add validation: does candidate exits? Is candidate hidden? Does candidate belong to user's domain?, etc.
        candidate_id = args.get('id')
        candidate = Candidate.get(candidate_id)
        if candidate:

            try:
                # Delete from MySQL
                db.session.delete(candidate)

                # Delete from DynamoDB
                DynamoDB.delete_candidate(candidate_id)
            except Exception as e:
                print "Something went wrong while deleting: {}".format(e.message)
                return e
            else:
                db.session.commit()
                ok = True

            return DeleteCandidate(ok=ok, id=candidate_id)


class Mutation(graphene.ObjectType):
    create_candidate = CreateCandidate.Field()
    update_candidate = UpdateCandidate.Field()
    delete_candidate = DeleteCandidate.Field()
