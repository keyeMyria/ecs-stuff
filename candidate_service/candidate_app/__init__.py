from candidate_service.common.utils.models_utils import init_talent_app
from candidate_service.common.talent_config_manager import TalentConfigKeys
from candidate_service.common.routes import CandidateApi
from candidate_service.common.talent_celery import init_celery_app
from candidate_service.common.models.db import db

app, logger = init_talent_app(__name__)

try:
    # Instantiate Celery
    celery_app = init_celery_app(app, 'celery_candidate_documents_scheduler')

    from candidate_service.candidate_app.api.v1_candidates import (
        CandidateResource, CandidateAddressResource, CandidateAreaOfInterestResource,
        CandidateEducationResource, CandidateEducationDegreeResource, CandidateEducationDegreeBulletResource,
        CandidateWorkExperienceResource, CandidateWorkExperienceBulletResource, CandidateWorkPreferenceResource,
        CandidateEmailResource, CandidatePhoneResource, CandidateMilitaryServiceResource,
        CandidatePreferredLocationResource, CandidateSkillResource, CandidateSocialNetworkResource,
        CandidatesResource, CandidateOpenWebResource, CandidateViewResource,
        CandidatePreferenceResource, CandidateClientEmailCampaignResource,
        CandidateDeviceResource, CandidatePhotosResource, CandidateLanguageResource, CandidateDocumentResource
    )
    from candidate_service.candidate_app.api.references import CandidateReferencesResource
    from candidate_service.candidate_app.api.candidate_search_api import CandidateSearch, CandidateDocuments
    from candidate_service.candidate_app.api.v1_candidate_tags import CandidateTagResource
    from candidate_service.candidate_app.api.pipelines import CandidatePipelineResource
    from candidate_service.candidate_app.api.candidate_custom_fields import CandidateCustomFieldResource
    from candidate_service.candidate_app.api.statuses import CandidateStatusesResources
    from candidate_service.candidate_app.api.notes import CandidateNotesResource
    from candidate_service.candidate_app.api.edits import CandidateEditResource

    from candidate_service.common.talent_api import TalentApi
    api = TalentApi(app=app)

    # API RESOURCES
    # ****** CandidateResource ******
    api.add_resource(
        CandidateResource,
        CandidateApi.CANDIDATE_ID,
        CandidateApi.CANDIDATE_EMAIL,
        endpoint='candidate_resource'
    )

    # ****** CandidatesResource ******
    api.add_resource(
        CandidatesResource,
        CandidateApi.CANDIDATES,
        CandidateApi.CANDIDATE_ID,
        endpoint='candidates_resource'
    )

    # ****** CandidateAddressResource ******
    api.add_resource(
        CandidateAddressResource,
        CandidateApi.ADDRESSES,
        endpoint='candidate_address_1'
    )
    api.add_resource(
        CandidateAddressResource,
        CandidateApi.ADDRESS,
        endpoint='candidate_address_2'
    )

    # ****** CandidateAreaOfInterestResource ******
    api.add_resource(
        CandidateAreaOfInterestResource,
        CandidateApi.AOIS,
        endpoint='candidate_area_of_interest_1'
    )
    api.add_resource(
        CandidateAreaOfInterestResource,
        CandidateApi.AOI,
        endpoint='candidate_area_of_interest_2'
    )

    # ****** CandidateCustomFieldResource ******
    api.add_resource(
        CandidateCustomFieldResource,
        CandidateApi.CUSTOM_FIELDS,
        endpoint='candidate_custom_field_1'
    )
    api.add_resource(
        CandidateCustomFieldResource,
        CandidateApi.CUSTOM_FIELD,
        endpoint='candidate_custom_field_2'
    )

    # ****** CandidateEducationResource ******
    api.add_resource(
        CandidateEducationResource,
        CandidateApi.EDUCATIONS,
        endpoint='candidate_education_1'
    )
    api.add_resource(
        CandidateEducationResource,
        CandidateApi.EDUCATION,
        endpoint='candidate_education_2'
    )

    # ****** CandidateEducationDegreeResource ******
    api.add_resource(
        CandidateEducationDegreeResource,
        CandidateApi.DEGREES,
        endpoint='candidate_education_degree_1'
    )
    api.add_resource(
        CandidateEducationDegreeResource,
        CandidateApi.DEGREE,
        endpoint='candidate_education_degree_2'
    )

    # ****** CandidateEducationDegreeBulletResource ******
    api.add_resource(
        CandidateEducationDegreeBulletResource,
        CandidateApi.DEGREE_BULLETS,
        endpoint='candidate_education_degree_bullet_1'
    )
    api.add_resource(
        CandidateEducationDegreeBulletResource,
        CandidateApi.DEGREE_BULLET,
        endpoint='candidate_education_degree_bullet_2'
    )

    # ****** CandidateExperienceResource ******
    api.add_resource(CandidateWorkExperienceResource, CandidateApi.EXPERIENCES, endpoint='candidate_experience_1')
    api.add_resource(CandidateWorkExperienceResource, CandidateApi.EXPERIENCE, endpoint='candidate_experience_2')

    # ****** CandidateExperienceBulletResource ******
    api.add_resource(CandidateWorkExperienceBulletResource, CandidateApi.EXPERIENCE_BULLETS,
                     endpoint='candidate_experience_bullet_1')
    api.add_resource(CandidateWorkExperienceBulletResource, CandidateApi.EXPERIENCE_BULLET,
                     endpoint='candidate_experience_bullet_2')

    # ****** CandidateEmailResource ******
    api.add_resource(CandidateEmailResource, CandidateApi.EMAILS,endpoint='candidate_email_1')
    api.add_resource(CandidateEmailResource, CandidateApi.EMAIL, endpoint='candidate_email_2')

    # ****** CandidateMilitaryServiceResource ******
    api.add_resource(CandidateMilitaryServiceResource, CandidateApi.MILITARY_SERVICES,
                     endpoint='candidate_military_service_1')
    api.add_resource(CandidateMilitaryServiceResource, CandidateApi.MILITARY_SERVICE,
                     endpoint='candidate_military_service_2')

    # ****** CandidatePhoneResource ******
    api.add_resource(CandidatePhoneResource, CandidateApi.PHONES, endpoint='candidate_phone_1')
    api.add_resource(CandidatePhoneResource, CandidateApi.PHONE, endpoint='candidate_phone_2')

    # ****** CandidatePreferredLocationResource ******
    api.add_resource(CandidatePreferredLocationResource, CandidateApi.PREFERRED_LOCATIONS,
                     endpoint='candidate_preferred_location_1')
    api.add_resource(CandidatePreferredLocationResource, CandidateApi.PREFERRED_LOCATION,
                     endpoint='candidate_preferred_location_2')

    # ****** CandidateSkillResource ******
    api.add_resource(CandidateSkillResource, CandidateApi.SKILLS, endpoint='candidate_skill_1')
    api.add_resource(CandidateSkillResource, CandidateApi.SKILL, endpoint='candidate_skill_2')

    # ****** CandidateSocialNetworkResource ******
    api.add_resource(CandidateSocialNetworkResource, CandidateApi.SOCIAL_NETWORKS,
                     endpoint='candidate_social_networks_1')
    api.add_resource(CandidateSocialNetworkResource, CandidateApi.SOCIAL_NETWORK,
                     endpoint='candidate_social_networks_2')
    api.add_resource(CandidateSocialNetworkResource, CandidateApi.CHECK_SOCIAL_NETWORK,
                     endpoint='candidate_check_social_network')

    # ****** CandidateWorkPreferenceResource ******
    api.add_resource(CandidateWorkPreferenceResource, CandidateApi.WORK_PREFERENCES,
                     endpoint='candidate_work_preferences')
    api.add_resource(CandidateWorkPreferenceResource, CandidateApi.WORK_PREFERENCE,
                     endpoint='candidate_work_preference')

    # ****** CandidateEditResource ******
    api.add_resource(CandidateEditResource, '/v1/candidates/<int:id>/edits', endpoint='candidate_edit')

    # ****** CandidateViewResource ******
    api.add_resource(CandidateViewResource, CandidateApi.CANDIDATE_VIEWS, endpoint='candidate_views')

    # ****** CandidateDeviceResource ******
    api.add_resource(CandidateDeviceResource, CandidateApi.DEVICES, endpoint='candidate_devices')

    # ****** CandidatePhotosResource ******
    api.add_resource(CandidatePhotosResource, CandidateApi.PHOTOS, endpoint='candidate_photos')
    api.add_resource(CandidatePhotosResource, CandidateApi.PHOTO, endpoint='candidate_photo')

    # ****** Candidate Search *******
    api.add_resource(CandidateSearch, CandidateApi.CANDIDATE_SEARCH)

    # ****** Candidate Documents *******
    api.add_resource(CandidateDocuments, CandidateApi.CANDIDATES_DOCUMENTS)

    # ****** OPENWEB Request *******
    api.add_resource(CandidateOpenWebResource, CandidateApi.OPENWEB, endpoint='openweb')

    # ****** Client email campaign *******
    api.add_resource(CandidateClientEmailCampaignResource, CandidateApi.CANDIDATE_CLIENT_CAMPAIGN)

    # ****** CandidatePreferenceResource *******
    api.add_resource(CandidatePreferenceResource, CandidateApi.CANDIDATE_PREFERENCES, endpoint='candidate_preference')

    # ****** CandidatePreferenceResource *******
    api.add_resource(CandidateNotesResource, CandidateApi.CANDIDATE_NOTES, endpoint='candidate_notes')
    api.add_resource(CandidateNotesResource, CandidateApi.CANDIDATE_NOTE, endpoint='candidate_note')

    # ****** CandidateLanguageResource *******
    api.add_resource(CandidateLanguageResource, CandidateApi.LANGUAGES, endpoint='candidate_languages')
    api.add_resource(CandidateLanguageResource, CandidateApi.LANGUAGE, endpoint='candidate_language')

    # ****** CandidateReferencesResource *******
    api.add_resource(CandidateReferencesResource, CandidateApi.REFERENCES, endpoint='candidate_references')
    api.add_resource(CandidateReferencesResource, CandidateApi.REFERENCE, endpoint='candidate_reference')

    # ****** CandidateTagResource *******
    api.add_resource(CandidateTagResource, CandidateApi.TAGS, endpoint='candidate_tags')
    api.add_resource(CandidateTagResource, CandidateApi.TAG, endpoint='candidate_tag')

    # ****** CandidatePipelineResource *******
    api.add_resource(CandidatePipelineResource, CandidateApi.PIPELINES, endpoint='candidate_pipelines')

    # ****** CandidateStatusesResource *******
    api.add_resource(CandidateStatusesResources, CandidateApi.STATUSES, endpoint='candidate_statuses')

    # ****** CandidateDocumentResource *******
    api.add_resource(CandidateDocumentResource, CandidateApi.DOCUMENTS, endpoint='candidate_documents')
    api.add_resource(CandidateDocumentResource, CandidateApi.DOCUMENT, endpoint='candidate_document')

    db.create_all()
    db.session.commit()

    logger.info('Starting candidate_service in %s environment', app.config[TalentConfigKeys.ENV_KEY])


except Exception as e:
    logger.exception("Couldn't start candidate_service in %s environment because: %s"
                     % (app.config[TalentConfigKeys.ENV_KEY], e.message))
