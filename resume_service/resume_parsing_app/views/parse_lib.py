"""Main resume parsing logic & functions."""
# Standard library
from cStringIO import StringIO
from os.path import basename
from os.path import splitext
from time import sleep
from time import time
import base64
# Third Party
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import process_pdf
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfparser import PDFDocument
from pdfminer.layout import LAParams
from pdfminer.converter import TextConverter
from xhtml2pdf import pisa
import requests
from BeautifulSoup import BeautifulSoup
import magic
# Module Specific
from flask import current_app
from resume_service.resume_parsing_app.views.optic_parse_lib import parse_optic_json, fetch_optic_response


def parse_resume(file_obj, filename_str):
    """Primary resume parsing function.

    Args:
        file_obj: an s3 file object.
        filename_str: the file's name
        is_test_parser: debugging/test mode Bool.

    Returns:
        Dictionary containing error message or candidate data.

    """
    current_app.logger.info("Beginning parse_resume(%s)", filename_str)
    file_ext = basename(splitext(filename_str.lower())[-1]) if filename_str else ""

    if not file_ext.startswith("."):
        file_ext = ".{}".format(file_ext)

    image_formats = ['.pdf', '.jpg', '.jpeg', '.png', '.tiff', '.tif', '.gif', '.bmp', '.dcx',
                     '.pcx', '.jp2', '.jpc', '.jb2', '.djvu', '.djv']
    doc_formats = ['.pdf', '.doc', '.docx', '.rtf', '.txt']

    if file_ext not in image_formats and file_ext not in doc_formats:
        current_app.logger.error('file_ext {} not in image_formats and file_ext not in doc_formats'.format(file_ext))
        return dict(error='file_ext not in image_formats and file_ext not in doc_formats')

    # Find out if the file is an image
    is_resume_image = False
    if file_ext in image_formats:
        if file_ext == '.pdf':
            start_time = time()
            text = convert_pdf_to_text(file_obj)
            current_app.logger.info("Benchmark: convert_pdf_to_text(%s) took %ss", filename_str, time() - start_time)
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
        doc_content = ocr_image(file_obj)
        current_app.logger.info("Benchmark: ocr_image(%s) took %ss", filename_str, time() - start_time)
    else:
        """
        BurningGlass doesn't work when the file's MIME type is text/html, even if the file is a .doc file.
        (Apparently HTML files that have a .doc extension are also valid doc files, that can be opened/edited in
        MS Word/LibreOffice/etc.)
        So, we have to convert the file into PDF using xhtml2pdf.
        """
        start_time = time()
        doc_content = file_obj.read()
        mime_type = magic.from_buffer(doc_content, mime=True)
        current_app.logger.info("Benchmark: Reading file_obj and magic.from_buffer(%s) took %ss", filename_str, time() - start_time)
        final_file_ext = file_ext

        if mime_type == 'text/html':
            start_time = time()
            file_obj = StringIO()
            try:
                create_pdf_status = pisa.CreatePDF(doc_content, file_obj)
                if create_pdf_status.err:
                    current_app.logger.error('PDF create error: {}'.format(create_pdf_status.err))
                    return None
            except:
                current_app.logger.error('parse_resume: Couldn\'t convert text/html file \'{}\' to PDF'.format(
                    filename_str))
                return None
            file_obj.seek(0)
            doc_content = file_obj.read()
            final_file_ext = '.pdf'
            current_app.logger.info("Benchmark: pisa.CreatePDF(%s) and reading file took %ss", filename_str,
                                    time() - start_time)

    if not doc_content:
        current_app.logger.error('parse_resume: No doc_content')
        return {}

    encoded_resume = base64.b64encode(doc_content)
    start_time = time()
    # Original Parsing via Dice API
    # bg_response_dict = parse_resume_with_bg(filename_str + final_file_ext, encoded_resume)
    optic_response = fetch_optic_response(encoded_resume)
    current_app.logger.info("Benchmark: parse_resume_with_bg(%s) took %ss", filename_str + final_file_ext,
                            time() - start_time)
    if optic_response:
        # candidate_data = parse_xml_into_candidate_dict(bg_response_dict)
        candidate_data = parse_optic_json(optic_response)
        # consider returning raw value
        # candidate_data['dice_api_response'] = bg_response_dict
        return candidate_data
    else:
        return dict(error='No XML text')


def ocr_image(img_file_obj, export_format='pdfSearchable'):
    """Posts the image to Abby OCR API, then keeps pinging to check if it's done.
       Quits if not done in certain number of tries.

    Return:
        Image file OCR'd in desired format.
    """

    ABBY_OCR_API_AUTH_TUPLE = ('gettalent', 'lfnJdQNWyevJtg7diX7ot0je')

    # Post the image to Abby
    files = {'file': img_file_obj}
    response = requests.post('http://cloud.ocrsdk.com/processImage',
                             auth=ABBY_OCR_API_AUTH_TUPLE,
                             files=files,
                             data={'profile': 'documentConversion', 'exportFormat': export_format}
                             )
    if response.status_code != 200:
        current_app.logger.error('ABBY OCR returned non 200 response code')
        return 0

    xml = BeautifulSoup(response.text)
    current_app.logger.info("ocr_image() - Abby response to processImage: %s", response.text)

    task_id = xml.response.task['id']
    estimated_processing_time = int(xml.response.task['estimatedprocessingtime'])

    if xml.response.task['status'] != 'Queued':
        current_app.logger.error('ocr_image() - Non queued status in ABBY OCR')
        pass

    # Keep pinging Abby to get task status. Quit if tried too many times
    ocr_url = ''
    num_tries = 0
    max_num_tries = 6
    while not ocr_url:
        sleep(estimated_processing_time)

        response = requests.get('http://cloud.ocrsdk.com/getTaskStatus', params=dict(taskId=task_id),
                                auth=ABBY_OCR_API_AUTH_TUPLE)
        xml = BeautifulSoup(response.text)
        ocr_url = xml.response.task.get('resulturl')
        current_app.logger.info("ocr_image() - Abby response to getTaskStatus: %s", response.text)

        if not ocr_url:
            if num_tries > max_num_tries:
                current_app.logger.error('OCR took > {} tries to process image'.format(max_num_tries))
                raise Exception('OCR took > {} tries to process image'.format(max_num_tries))
            estimated_processing_time = 2  # If not done in originally estimated processing time, wait 2 more seconds
            num_tries += 1
            continue

    if response.status_code == requests.codes.ok:
        start_time = time()
        response = requests.get(ocr_url)
        current_app.logger.info("Benchmark: ocr_image: requests.get(%s) took %ss to download resume", ocr_url,
                                time() - start_time)
        return response.content
    else:
        return 0


def convert_pdf_to_text(pdf_file_obj):
    rsrcmgr = PDFResourceManager()
    retstr = StringIO()
    codec = 'utf-8'
    laparams = LAParams()
    device = TextConverter(rsrcmgr, retstr, codec=codec, laparams=laparams)

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
