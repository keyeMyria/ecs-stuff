"""Main resume parsing logic & functions."""
# pylint: disable=wrong-import-position, fixme
# Standard library
from cStringIO import StringIO
from os.path import basename
from os.path import splitext
from time import sleep
from time import time
import base64
import json
# Third Party/Framework Specific.
from bs4 import BeautifulSoup
from pdfminer.converter import TextConverter
from pdfminer.layout import LAParams
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import process_pdf
from pdfminer.pdfparser import PDFDocument
from pdfminer.pdfparser import PDFParser
import magic
import requests
# Module Specific
from resume_parsing_service.app import logger, redis_store
from resume_parsing_service.app.views.optic_parse_lib import fetch_optic_response
from resume_parsing_service.app.views.optic_parse_lib import parse_optic_xml
# from resume_parsing_service.app.views.sovren_parse_lib import fetch_sovren_response
# from resume_parsing_service.app.views.sovren_parse_lib import parse_sovren_xml
from resume_parsing_service.app.views.utils import update_candidate_from_resume
from resume_parsing_service.app.views.utils import create_parsed_resume_candidate
from resume_parsing_service.app.views.utils import gen_hash_from_file
from resume_parsing_service.common.error_handling import ForbiddenError
from resume_parsing_service.common.error_handling import InvalidUsage, InternalServerError
from resume_parsing_service.common.routes import CandidateApiUrl
from resume_parsing_service.common.utils.talent_s3 import download_file
from resume_parsing_service.common.utils.talent_s3 import get_s3_filepicker_bucket_and_conn
from resume_parsing_service.common.utils.talent_s3 import upload_to_s3

IMAGE_FORMATS = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.gif', '.bmp', '.dcx',
                 '.pcx', '.jp2', '.jpc', '.jb2', '.djvu', '.djv']
DOC_FORMATS = ['.pdf', '.doc', '.docx', '.rtf', '.txt']
RESUME_EXPIRE_TIME = 604800  # one week in seconds.
GOOGLE_API_KEY = "AIzaSyD4i4j-8C5jLvQJeJnLmoFW6boGkUhxSuw"
GOOGLE_CLOUD_VISION_URL = "https://vision.googleapis.com/v1/images:annotate"


def process_resume(parse_params):
    """
    Parses a resume based on a provided: filepicker key or binary, filename
    :param dict parse_params:
    :return: dict: {'candidate': {...}, 'raw': {...}}
    """
    filepicker_key = parse_params.get('filepicker_key')
    # None may be explicitly passed so the normal .get('attr', default) doesn't apply here.
    create_candidate = parse_params.get('create_candidate', False)
    talent_pools = parse_params.get('talent_pools')
    # Talent pools are the ONLY thing required to create a candidate.
    if create_candidate and not talent_pools:
        raise InvalidUsage('Talent Pools required for candidate creation')
    if filepicker_key:
        file_picker_bucket, unused_conn = get_s3_filepicker_bucket_and_conn()
        filename_str = filepicker_key
        resume_bin = resume_file = download_file(file_picker_bucket, filename_str)
    elif parse_params.get('filename'):
        resume_bin = parse_params.get('resume_file')
        resume_file = StringIO(resume_bin.read())
        filename_str = parse_params.get('filename')
    else:
        raise InvalidUsage('Invalid query params for /parse_resume')
    # Parse the actual resume content.
    hashed_file_name = gen_hash_from_file(resume_file)
    cached_resume = redis_store.get(hashed_file_name)
    if cached_resume:
        parsed_resume = json.loads(cached_resume)
        logger.info('Resume %s has been loaded from cache and its hashed_key is %s' % (filename_str, hashed_file_name))
    else:
        logger.info("Couldn't find Resume %s in cache with hashed_key: %s" % (filename_str, hashed_file_name))
        parsed_resume = parse_resume(file_obj=resume_file, filename_str=filename_str)
        redis_store.set(hashed_file_name, json.dumps(parsed_resume))
        redis_store.expire(hashed_file_name, RESUME_EXPIRE_TIME)
    if not create_candidate:
        return parsed_resume
    oauth_string = parse_params.get('oauth')
    parsed_resume['candidate']['talent_pool_ids']['add'] = talent_pools
    try:
        resume_bin.seek(0)
        s3_url, key = upload_to_s3(resume_bin.read(), 'OriginalFiles', filename_str)
        parsed_resume['candidate']['resume_url'] = filename_str
    except Exception as e:
        logger.exception('Failure during s3 upload; reason: {}'.format(e.message))
    candidate_post_response = create_parsed_resume_candidate(parsed_resume['candidate'],
                                                             oauth_string)
    response_dict = json.loads(candidate_post_response.content)
    if candidate_post_response.status_code is not requests.codes.created:
        # If there was an issue with candidate creation we want to forward the error message and
        # the error code supplied by Candidate Service.
        existing_candidate_id = response_dict.get('error', {}).get('id')
        if not existing_candidate_id:
            raise InvalidUsage(error_message=response_dict.get('error', {}).get(
                'message', 'Error in candidate creating from resume service.'))
        # We have a candidate already with this email so lets patch it up
        parsed_resume['candidate']['id'] = existing_candidate_id
        update_response = update_candidate_from_resume(parsed_resume['candidate'], oauth_string)
        if update_response.status_code is not requests.codes.ok:
            logger.info("ResumetoCandidateError. {} received from CandidateService (update)".format(
                update_response.status_code))
            raise InternalServerError(
                'Candidate from {} exists, error updating info'.format(filename_str))
        response_dict = json.loads(update_response.content)
        logger.info('Response Dict: {}'.format(response_dict))

    candidate_id = response_dict.get('candidates')[0]['id']
    logger.debug('Candidate created with id: {}'.format(candidate_id))
    candidate_get_response = requests.get(CandidateApiUrl.CANDIDATE % candidate_id,
                                          headers={'Authorization': oauth_string})
    if candidate_get_response.status_code is not requests.codes.ok:
        raise InvalidUsage(error_message='Error retrieving created candidate')
    candidate = json.loads(candidate_get_response.content)
    return candidate


def parse_resume(file_obj, filename_str):
    """Primary resume parsing function.

    :param cStringIO.StringI file_obj: a StringIO representation of the raw binary.
    :param str filename_str: The file_obj file name.
    :return: A dictionary of processed candidate data or an appropriate error message.
    """
    logger.info("Beginning parse_resume(%s)", filename_str)
    file_ext = basename(splitext(filename_str.lower())[-1]) if filename_str else ""
    if not file_ext.startswith("."):
        file_ext = ".{}".format(file_ext)
    if file_ext not in IMAGE_FORMATS and file_ext not in DOC_FORMATS:
        logger.error(
            'file_ext {} not in image_formats and file_ext not in doc_formats'.format(file_ext))
        return dict(error='file_ext not in image_formats and file_ext not in doc_formats')
    # Find out if the file is an image
    is_resume_image = False
    if file_ext in IMAGE_FORMATS:
        if file_ext == '.pdf':
            start_time = time()
            text = convert_pdf_to_text(file_obj)
            logger.info(
                "Benchmark: convert_pdf_to_text(%s) took %ss", filename_str, time() - start_time)
            if not text.strip():
                # pdf is possibly an image
                is_resume_image = True
        else:
            is_resume_image = True
        final_file_ext = '.pdf'

    file_obj.seek(0)
    if is_resume_image:
        # If file is an image, OCR it
        start_time = time()
        doc_content = google_vision_ocr(file_obj)
        logger.info(
            "Benchmark: google_vision_ocr{}: took {}s to process".format(filename_str,
                                                                         time() - start_time)
        )
        logger.info("Benchmark: ocr_image(%s) took %ss", filename_str, time() - start_time)
    else:
        start_time = time()
        doc_content = file_obj.read()
        logger.info(
            "Benchmark: Reading file_obj and magic.from_buffer(%s) took %ss",
            filename_str, time() - start_time
        )
        final_file_ext = file_ext

    if not doc_content:
        logger.error('parse_resume: No doc_content')
        return {}

    encoded_resume = base64.b64encode(doc_content)
    start_time = time()
    optic_response = fetch_optic_response(encoded_resume)
    logger.info(
        "Benchmark: parse_resume_with_bg({}) took {}s".format(filename_str + final_file_ext,
                                                              time() - start_time)
    )
    if optic_response:
        candidate_data = parse_optic_xml(optic_response)
        # Consider returning tuple
        return {'raw_response': optic_response, 'candidate': candidate_data}
    else:
        raise InvalidUsage('No XML text received from Optic Response for {}'.format(filename_str))


def ocr_image(img_file_obj, export_format='pdfSearchable'):
    """
    Posts the image to Abby OCR API, then keeps pinging to check if it's done. Quits if not done in
    certain number of tries.
    :param cStringIO.StringIO img_file_obj: File initially posted to the resume parsing service.
    :param string export_format: Abby OCR param.
    :return: Image file OCR'd in desired format.
    """

    abby_ocr_api_auth_tuple = ('gettalent', 'lfnJdQNWyevJtg7diX7ot0je')

    # Post the image to Abby
    files = {'file': img_file_obj}
    response = requests.post('http://cloud.ocrsdk.com/processImage',
                             auth=abby_ocr_api_auth_tuple,
                             files=files,
                             data={'profile': 'documentConversion', 'exportFormat': export_format}
                             )
    if response.status_code != 200:
        raise ForbiddenError('Error connecting to Abby OCR instance.')

    xml = BeautifulSoup(response.text)
    logger.info("ocr_image() - Abby response to processImage: %s", response.text)

    task_id = xml.response.task['id']
    estimated_processing_time = int(xml.response.task['estimatedprocessingtime'])

    if xml.response.task['status'] != 'Queued':
        logger.error('ocr_image() - Non queued status in ABBY OCR')

    # Keep pinging Abby to get task status. Quit if tried too many times
    ocr_url = ''
    num_tries = 0
    max_num_tries = 6
    while not ocr_url:
        sleep(estimated_processing_time)

        response = requests.get('http://cloud.ocrsdk.com/getTaskStatus',
                                params=dict(taskId=task_id), auth=abby_ocr_api_auth_tuple)
        xml = BeautifulSoup(response.text)
        ocr_url = xml.response.task.get('resulturl')
        logger.info("ocr_image() - Abby response to getTaskStatus: %s", response.text)

        if not ocr_url:
            if num_tries > max_num_tries:
                logger.error('OCR took > {} tries to process image'.format(
                    max_num_tries))
                raise Exception('OCR took > {} tries to process image'.format(max_num_tries))
            # If not done in originally estimated processing time, wait 2 more seconds.
            estimated_processing_time = 2
            num_tries += 1
            continue

    if response.status_code == requests.codes.ok:
        start_time = time()
        response = requests.get(ocr_url)
        logger.info(
            "Benchmark: ocr_image: requests.get(%s) took %ss to download resume",
            ocr_url, time() - start_time
        )
        return response.content
    else:
        return 0


def google_vision_ocr(file_string_io):
    b64_string = base64.b64encode(file_string_io.getvalue())
    req_data = {
        "requests": [
            {
                "image": {
                    "content": b64_string
                },
                "features": [
                    {
                        "type": "TEXT_DETECTION",
                        "maxResults": 1
                    }
                ]
            }
        ]
    }
    try:
        google_request = requests.post("{}?key={}".format(GOOGLE_CLOUD_VISION_URL, GOOGLE_API_KEY),
                                       json.dumps(req_data),
                                       timeout=20,
                                       headers={'content-type': 'application/json'})
    except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
        logger.exception("google_vision_ocr: Could not reach Google API")
        raise InternalServerError("Unable to reach Google API in resume OCR")
    if google_request.status_code is not requests.codes.ok:
        logger.info('google_vision_ocr: Google API response error with headers: {} content{}'.format(
            google_request.headers, google_request.content))
        raise InternalServerError('Error in response from candidate service during creation')
    ocr_results = json.loads(google_request.content)
    # Check for errors since even a 'bad' request gives a 200 response. And use Abby in that event.
    google_api_errors = ocr_results['responses'][0].get('error')
    if google_api_errors:
        logger.warn('Error parsing with Google Vision. Trying Abby parse. Param: {}'.format(file_string_io))
        return ocr_image(file_string_io)
    logger.info("google_vision_ocr: Google API response JSON: %s", ocr_results)
    return ocr_results['responses'][0]['textAnnotations'][0]['description']


def convert_pdf_to_text(pdf_file_obj):
    """Converts a PDF file to a usable string."""
    rsrcmgr = PDFResourceManager()
    retstr = StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)

    # TODO access if this reassignment is needed.
    fp = pdf_file_obj

    parser = PDFParser(fp)
    doc = PDFDocument()
    parser.set_document(doc)
    doc.set_parser(parser)
    doc.initialize('')
    if not doc.is_extractable:
        return ''

    process_pdf(rsrcmgr, device, fp)
    device.close()

    text = retstr.getvalue()
    retstr.close()
    return text
