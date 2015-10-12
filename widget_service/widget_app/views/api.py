"""Widget serving/processing"""
__author = 'erikfarmer'

# Standard library
import json

# Framework specific/Third Party
from flask import Blueprint
from flask import current_app as app
from flask import jsonify
from flask import request
from flask import render_template
import requests

# Module specific
from widget_service.common.models.candidate import University
from widget_service.common.models.misc import AreaOfInterest
from widget_service.common.models.misc import Major
from widget_service.common.models.user import Domain
from widget_service.common.models.user import User
from widget_service.common.models.widget import WidgetPage
from widget_service.widget_app import db
from widget_service.widget_app.views.utils import parse_interest_ids_from_form
from widget_service.widget_app.views.utils import parse_city_and_state_ids_from_form

mod = Blueprint('widget_api', __name__)


@mod.route('/test/<domain>', methods=['GET'])
def show_widget(domain):
    if app.config['ENVIRONMENT'] != 'dev':
        return 'Error', 400
    if domain == 'kaiser-military':
        return render_template('kaiser_military.html', domain=domain)
    elif domain == 'kaiser-university':
        return render_template('kaiser_2.html', domain=domain)
    elif domain == 'kaiser-corp':
        return render_template('kaiser_3.html', domain=domain)


@mod.route('/widget/<widget_name>', methods=['GET'])
def process_widget(widget_name):
    widget = db.session.query(WidgetPage).filter_by(widget_name=widget_name).first()
    return widget.widget_html, 200


@mod.route('/widget/candidates', methods=['POST'])
def create_candidate_from_widget():
    form = request.form
    candidate_dict = {
        'full_name': '{} {}'.format(form['firstName'], form['lastName']),
        'emails': [{'address': form['emailAdd'], 'label': 'Primary'}],
        'areas_of_interest':  parse_interest_ids_from_form(form['hidden-tags-aoi']),
        'custom_fields': parse_city_and_state_ids_from_form(form['hidden-tags-location'])
    }
    payload = json.dumps({'candidates': [candidate_dict]})
    try:
        request = requests.post(app.config['CANDIDATE_CREATION_URI'], data=payload,
                          headers={'Authorization': app.config['OAUTH_TOKEN'].access_token})
    except:
        return jsonify({'error': {'message': 'unable to create candidate from form'}})
    return jsonify({'success': {'message': 'candidate successfully created'}}), 201


@mod.route('/interests/<widget_name>', methods=['GET'])
def get_areas_of_interest(widget_name):
    current_widget = WidgetPage.query.filter_by(widget_name=widget_name).first()
    widget_user = User.query.get(current_widget.user_id)
    interests = db.session.query(AreaOfInterest).filter(
        AreaOfInterest.domain_id == widget_user.domain_id)
    primary_interests = []
    secondary_interests = []
    for interest in interests:
        if interest.parent_id:
            secondary_interests.append({
                'description': interest.description,
                'parent_id': interest.parent_id
            })
        else:
            primary_interests.append({
                'description': interest.description,
                'parent_id': interest.parent_id
            })
    return jsonify({'primary_interests': primary_interests,
                    'secondary_interests': secondary_interests})


@mod.route('/universities', methods=['GET'])
def get_university_names():
    university_names = db.session.query(University.name)
    return jsonify(universities_list=[uni for uni in university_names])


@mod.route('/majors/<domain_name>', methods=['GET'])
def get_major_names(domain_name):
    domain_id = db.session.query(Domain.id).filter(Domain.name==domain_name)
    majors = db.session.query(Major.name).filter(domain_id==domain_id)
    return jsonify(majors=[major for major in majors])
