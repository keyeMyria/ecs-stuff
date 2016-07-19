"""Functions associated with resume parsing flow (generally based on file type."""
__author__ = 'erik@gettalent.com'
# pylint: disable=wrong-import-position, fixme, import-error
# Standard library
from cStringIO import StringIO
from os.path import basename
from os.path import splitext
from time import time
import base64
import json
# Third Party/Framework Specific.
from flask import current_app
import PyPDF2
# Module Specific
from resume_parsing_service.app import logger, redis_store
from resume_parsing_service.app.views.optic_parse_lib import fetch_optic_response
from resume_parsing_service.app.views.optic_parse_lib import parse_optic_xml
from resume_parsing_service.app.views.utils import gen_hash_from_file
from resume_parsing_service.app.views.ocr_lib import google_vision_ocr
from resume_parsing_service.app.views.pdf_utils import convert_pdf_to_text, decrypt_pdf
from resume_parsing_service.common.error_handling import InvalidUsage
from resume_parsing_service.common.utils.talent_s3 import boto3_put


IMAGE_FORMATS = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.gif', '.bmp', '.dcx',
                 '.pcx', '.jp2', '.jpc', '.jb2', '.djvu', '.djv']
DOC_FORMATS = ['.pdf', '.doc', '.docx', '.rtf', '.txt']
RESUME_EXPIRE_TIME = 60 * 60 * 24 * 7  # one week in seconds.


def parse_resume(file_obj, filename_str, cache_key):
    """Primary resume parsing function.

    :param cStringIO.StringI file_obj: a StringIO representation of the raw binary.
    :param str filename_str: The file_obj file name.
    :return: A dictionary of processed candidate data or an appropriate error message.
    """
    logger.info("Beginning parse_resume(%s)", filename_str)

    file_ext = basename(splitext(filename_str.lower())[-1]) if filename_str else ""

    # PDFs must have attempted decryption with the empty string password if applicable.
    if file_ext == '.pdf':
        file_obj = decrypt_pdf(file_obj)

    if is_resume_image(file_ext, file_obj):
        # If file is an image, OCR it
        start_time = time()
        doc_content = google_vision_ocr(file_obj)
        logger.info(
            "Benchmark: google_vision_ocr for {}: took {}s to process".format(
                filename_str, time() - start_time)
        )

    else:
        doc_content = file_obj.getvalue()

    if not doc_content:
        bucket = current_app.config['S3_BUCKET_NAME']
        boto3_put(file_obj.getvalue(), bucket, filename_str, 'FailedResumes')
        raise InvalidUsage("Unable to determine the contents of the document: {}".format(filename_str))

    try:
        encoded_resume = base64.b64encode(doc_content)

    except Exception:
        logger.exception('Error encoding resume before sending to BG Optic.')
        raise InvalidUsage('Issue encoding resume text. Please ensure the file is of a resume and not blurry.')

    optic_response = fetch_optic_response(encoded_resume, filename_str)

    if optic_response:
        redis_store.set(cache_key, optic_response)
        redis_store.expire(cache_key, RESUME_EXPIRE_TIME)
        candidate_data = parse_optic_xml(optic_response)
        return {'raw_response': optic_response, 'candidate': candidate_data}

    else:
        raise InvalidUsage('No XML text received from Optic Response for {}'.format(filename_str))


def is_resume_image(file_ext, file_obj):
    resume_is_image = False

    if not file_ext.startswith("."):
        file_ext = ".{}".format(file_ext)

    if file_ext not in IMAGE_FORMATS and file_ext not in DOC_FORMATS:
        raise InvalidUsage('File ext \'{}\' not in accepted image or document formats'.format(file_ext))

    # Find out if the file is an image
    if file_ext in IMAGE_FORMATS:
        if file_ext == '.pdf':
            text = convert_pdf_to_text(file_obj)
            if not text.strip():
                # pdf is possibly an image
                resume_is_image = True
        else:
            resume_is_image = True

    return resume_is_image
