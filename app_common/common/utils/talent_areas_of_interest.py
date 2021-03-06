from ..error_handling import InternalServerError
from flask import current_app

DEFAULT_AREAS_OF_INTEREST = ['Production & Development', 'Marketing', 'Sales', 'Design', 'Finance',
                             'Business & Legal Affairs', 'Human Resources', 'Technology', 'Other']


# Gets or creates AOIs
def get_or_create_areas_of_interest(domain_id, include_child_aois=False):
    """
    Get or create areas of interest for candidates
    :param domain_id:
    :param include_child_aois:
    :return: area_of_interest row object
    """
    from ..models.misc import AreaOfInterest
    areas = AreaOfInterest.query.filter_by(domain_id=domain_id).order_by(AreaOfInterest.id.asc())
    # If no AOIs exist, create them
    if not areas:
        for description in DEFAULT_AREAS_OF_INTEREST:
            AreaOfInterest(description=description, domain_id=domain_id)
        areas = AreaOfInterest.query.filter_by(domain_id=domain_id).order_by(AreaOfInterest.id.asc())

    # If we only want parent AOIs, must filter for all AOIs that don't have parentIds
    if not include_child_aois:
        areas = areas.filter(AreaOfInterest.parent_id is not None)
    return areas


def get_area_of_interest_id_to_sub_areas_of_interest(domain_id):
    """
    Get area of interest is to sub area of interest
    :param domain_id:
    :return:
    """
    from ..models.misc import AreaOfInterest
    sub_areas_of_interest = AreaOfInterest.query.filter(AreaOfInterest.domain_id == domain_id,
                                                        AreaOfInterest.parent_id is not None).sorted(
        lambda row: AreaOfInterest.description)
    area_of_interest_id_to_sub_areas_of_interest = dict()
    for sub_aoi in sub_areas_of_interest:
        if not area_of_interest_id_to_sub_areas_of_interest.get(sub_aoi.parentId):
            area_of_interest_id_to_sub_areas_of_interest[sub_aoi.parentId] = []

        area_of_interest_id_to_sub_areas_of_interest[sub_aoi.parentId].append(sub_aoi)

    return area_of_interest_id_to_sub_areas_of_interest


def add_aoi_to_candidate(candidate_id, aoi_ids, owner_user_id=None):
    """
    Add area of interest to created candidate.
    Simply modified. Not Tested, nor found any usage in code. Anyone using this please test it first.
    :param candidate_id:
    :param aoi_ids:
    :param owner_user_id:
    :return:
    """
    from ..models.candidate import Candidate
    from ..models.misc import AreaOfInterest
    from ..models.associations import CandidateAreaOfInterest
    if not isinstance(aoi_ids, list):
        aoi_ids = [aoi_ids]
    candidate = Candidate.query.filter_by(id=candidate_id).first()
    owner_id = candidate.user_id
    domain_id = owner_user_id.domain_id or owner_id.domain_id
    domain_areas_of_interest = get_or_create_areas_of_interest(domain_id, include_child_aois=True)
    candidate_area_of_interests = CandidateAreaOfInterest.query.filter_by(candidate_id=candidate_id)
    current_candidate_aoi_ids = [r.area_of_interest_id for r in candidate_area_of_interests]
    for new_aoi_id in aoi_ids:
        # Only add the AOI if the candidate doesn't already have it
        if new_aoi_id not in current_candidate_aoi_ids:
            # Find the AOI amongst the domain's AOIs
            aoi_row = domain_areas_of_interest.filter_by(id=new_aoi_id).first()
            if aoi_row:
                try:
                    new_aoi = CandidateAreaOfInterest(area_of_interest_id=new_aoi_id, candidate_id=candidate_id)
                    current_app.db.session.add(new_aoi)
                    current_app.db.session.commit()
                    current_candidate_aoi_ids.append(new_aoi_id)
                except Exception, ex:
                    current_app.logger.exception("Received exception while inserting AOI %s for candidate %s. "
                                                 "Exception was: %s" % (new_aoi_id, candidate_id, ex))
                    raise InternalServerError("Received exception inserting AOI %s for candidate %s" % (new_aoi_id,
                                                                                                        candidate_id))
                # If AOI is a child, insert its parent as well
                if aoi_row.parent_id:
                    existing_parent_candidate_aoi = CandidateAreaOfInterest.query.filter(
                        CandidateAreaOfInterest.area_of_interest_id == aoi_row.parent_id,
                        CandidateAreaOfInterest.candidate_id == candidate_id).first()
                    if not existing_parent_candidate_aoi:
                        current_app.db.session.add(CandidateAreaOfInterest(area_of_interest_id=aoi_row.parent_id,
                                                                           candidate_id=candidate_id))
                        current_app.db.session.commit()

                        current_candidate_aoi_ids.append(aoi_row.parent_id)
            else:
                current_app.logger.error(
                    "add_aoi_to_candidate(%s): Could not find AOI %s (domain ID %s) in domain %s's AOIs: %s" % (
                        candidate_id,
                        new_aoi_id,
                        AreaOfInterest.get(new_aoi_id).domain_id,
                        domain_id,
                        [aoi.id for aoi in domain_areas_of_interest]))

# All the available Areas of interests in Kaiser domain.
KAISER_PARENT_TO_CHILD_AOIS = {
    'Accounting, Finance and Actuarial Services': ['Actuarial',
                                                   'Audit',
                                                   'SOX',
                                                   'Tax',
                                                   'Financial Planning & Analysis',
                                                   'Accounting',
                                                   'Payroll',
                                                   'Accounts Receivable/Payable',
                                                   'Treasury'],
    'Administration, Clerical and Support Services': [],
    'All': [],
    'Behavioral Health/Social Services/Spiritual Care': ['Behavioral Health/Social Services Management',
                                                         'Medical Social Worker',
                                                         'Medical Social Worker LCSW',
                                                         'Behavioral Health non licensed',
                                                         'Psychologist',
                                                         'Behavioral Health Case Managers LCSW/LMFT',
                                                         'Addiction Medicine Counselors/Clinicians',
                                                         'LCSW Intern',
                                                         'MFT Intern',
                                                         'Employee Assistance Program Coordinator',
                                                         'Chaplain',
                                                         'Psychological Assistant',
                                                         'Psychology Post Doc',
                                                         'Psychology Pre Doc'],
    'Biomedical Engineering': [],
    'Communications': ['Public Relations',
                       'Brand Communications',
                       'Marketing Communications',
                       'Copywriter',
                       'Educational Theatre',
                       'Media Relations',
                       'Editor'],
    'Compliance/Privacy/Regulatory': ['Regulatory Affairs',
                                      'Compliance',
                                      'Audit',
                                      'Risk Assessment',
                                      'Fraud'],
    'Construction': ['Construction Project Management',
                     'Construction Management',
                     'Architecture',
                     'Engineering',
                     'Contracts',
                     'Estimating/Cost engineering',
                     'Real Estate'],
    'Consulting Services, Project/Program Management (Non IT)': ['Program Management',
                                                                 'Project Management',
                                                                 'Business Consultant',
                                                                 'Executive Consultant'],
    'Customer Services': ['Call Center', 'Member Relations/Services'],
    'Dental': [],
    'Dietitians/Nutrition Services': ['Registered Dietitians',
                                      'Food/Nutrition Services Management',
                                      'Diet Technician',
                                      'Food/Nutrition Services Staff'],
    'Durable Medical Equipment': [],
    'Education/Training': ['Learning & Development',
                           'Health Education',
                           'Learning Specialist',
                           'Educator',
                           'Learning Consultant',
                           'Instructional Design',
                           'Professional Development'],
    'External Affairs/Relations': ['Public Affairs/Public Relations',
                                   'Events Coordinator',
                                   'Language Interpreter',
                                   'Community Relations'],
    'Facilities Services': ['Environmental Health & Safety',
                            'Maintenance & Operations',
                            'Clinical Technology',
                            'Housekeeping',
                            'Facilities Planner',
                            'Security',
                            'Plant Engineer'],
    'Health Information Management (Medical Records)': ['HIM Management',
                                                        'HIM Consultant/Trainer/Analyst/PM',
                                                        'HIM Coder',
                                                        'Clinical Documentation/Coding Auditor'],
    'Healthcare/Hospital Operations': [],
    'Human Resources/HRIS': ['Human Resources Business Partners/Consultant/Generalist',
                             'Compensation',
                             'Recruitment',
                             'Benefits',
                             'HR Information Systems/Technology',
                             'Organizational Development',
                             'Workforce planning',
                             'Diversity',
                             'Environmental Health & Safety',
                             'Payroll',
                             'Labor Relations',
                             'Wellness',
                             'Workers Compensation',
                             'Leave of Absence'],
    'Imaging/Radiology': ['Diagnostic Medical Sonographer/Ultrasound',
                          'MRI Technologist',
                          'Nuclear Medicine Technologist',
                          'Radiation Therapist',
                          'Radiology/Imaging Management/Education',
                          'Radiologic Technologist',
                          'Mammography Technologist',
                          'CT Technologist',
                          'Dosimetrist',
                          'Radiation Biologist',
                          'Radiation Physicist',
                          'Interventional Radiology Technologist',
                          'Bone Densitometry Technologist',
                          'PACS Administrator',
                          'PACS Administrator Assistant'],
    'Information Technology': ['Project/Program Management',
                               'Application Programming',
                               'Database Administration',
                               'Risk Management',
                               'Cyber Security',
                               'Solution Consulting',
                               'Management',
                               'Business Consulting',
                               'Data Center Operations',
                               'Help Desk',
                               'Desktop Support',
                               'Network Engineer',
                               'Enterprise Architect',
                               'Systems Integration'],
    'Insurance/Claims': ['Pricing/Underwriting',
                         'Benefits Administration',
                         'Government Programs',
                         'Claims',
                         'Membership Administration',
                         'Customer Service'],
    'Laboratory': ['Clinical Laboratory Scientist/Medical Laboratory Technologist',
                   'Cytotechnologist',
                   'Histologic Technician',
                   'Laboratory Assistant/Phlebotomist',
                   'Laboratory Management/Education',
                   'Medical Laboratory Technician',
                   "Pathologist's Assistant",
                   'Pathology Technician',
                   'Embryologist',
                   'Molecular Technologist'],
    'Legal': ['Paralegal', 'Attorney/General Counsel', 'Legal Secretary'],
    'Library Sciences': [],
    'Materials Management': ['Durable Medical Equipment',
                             'Distribution',
                             'Inventory'],
    'Nurse Practitioner/Physician Assistant': ['Nurse Practitioner',
                                               'Physician Assistant'],
    'Nursing Licensed': ['Ambulatory/Primary Care/Outpatient Nursing',
                         'Advice Nurse',
                         'Cardiac Cath Lab/Cardiology',
                         'Center for Health Resources',
                         'Continuing Care (Home Health/Hospice/SNF)',
                         'Critical Care/Step Down/DOU',
                         'Education/CNS',
                         'Emergency',
                         'IV Therapy/Infusion Center',
                         'GI',
                         'LVN/LPN',
                         'Medical/Surgery',
                         'Mental Health',
                         'Neuro/ENT',
                         'Nurse Anesthetist (CRNA)',
                         'Occupational Health',
                         'Oncology/Radiation/Radiology/Imaging',
                         'Pediatrics/PICU/NICU',
                         'Perioperative/Ambulatory Surgery',
                         'Telemetry',
                         'Urgent Care',
                         'Case Management',
                         "Women's Health/L&D/Midwives",
                         'Quality/Utilization Management/Risk'],
    'Optical Services': ['Optometric Assistant',
                         'Optical Dispenser',
                         'Contact Lens Dispenser/Fitter',
                         'Optometrists',
                         'Ophthalmic Technician'],
    'Patient Care Services (Non RN)': ['Clerical/Administrative Services',
                                       'Management, Technician/Licensed',
                                       'Nursing Support Services',
                                       'Technician/Licensed'],
    'Pharmacy': ['Ambulatory Care/Clinical Pharmacist',
                 'Clerk or Assistant',
                 'Inpatient Pharmacist',
                 'Intern/Graduate Pharmacist/Resident',
                 'Management',
                 'Outpatient Pharmacist',
                 'Pharmacy Professional (Educators, Project Managers, Consultant/Analyst)',
                 'Pharmacy Technician'],
    'Procurement and Supply': ['Supply Chain',
                               'Sourcing',
                               'Vendor Management',
                               'Purchasing & Contracts'],
    'QA/UR/Case Management': ['Accreditation',
                              'Quality/Utilization Review',
                              'Risk/Patient Safety',
                              'Infection Prevention',
                              'Case Management'],
    'Rehab Services': ['Acupuncture',
                       'Audiologist',
                       'Occupational Therapist',
                       'Certified Occupational Therapy Assistant',
                       'Physical Therapist',
                       'Licensed Physical Therapy Assistant',
                       'Recreational Therapist',
                       'Rehab Management/Education',
                       'Speech Therapist/Speech Language Pathologist',
                       'Respiratory Care Practitioner',
                       'Respiratory Management',
                       'Polysomnographic Technologist',
                       'Sleep Technologist'],
    'Research and Development': ['Clinical Research', 'Research Administration'],
    'Sales and Marketing': ['Product Management',
                            'Account Management',
                            'Internet/Intranet',
                            'Strategic Market Planning',
                            'Sales Operations',
                            'Market Research',
                            'Enroller',
                            'Proposal Development']
}

