import re
from ..error_handling import *


def is_number(s):
    try:
        float(s)
        return True
    except ValueError:
        return False


def is_valid_email(email):
    """
    According to: http://www.w3.org/TR/html5/forms.html#valid-e-mail-address

    :type email: str
    """
    regex = """^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$"""
    return email and re.match(regex, email)


# def format_phone_number(phone_number):
#     """
#     Format US/Canada phone numbers in +1 (123) 456-7899 format
#     :return: Formatted phone numbers
#     :rtype: str
#     """
#     import phonenumbers
#     try:
#         parsed_phone_numbers = phonenumbers.parse(str(phone_number), region="US")
#         if phonenumbers.is_valid_number_for_region(parsed_phone_numbers, 'US'):
#             # Phone number format is : +1 (123) 456-7899
#             return '+1 ' + phonenumbers.format_number(parsed_phone_numbers, phonenumbers.PhoneNumberFormat.NATIONAL)
#         else:
#             raise InvalidUsage(error_message="[%s] is an invalid or non-US/Canada Phone Number" % phone_number)
#     except:
#         raise InvalidUsage("[%s] is an invalid or non-US/Canada Phone Number" % phone_number)


def format_phone_number(phone_number, country_code='US'):
    """
    Format US/Canada phone numbers in +1 (123) 456-7899 format
    :return: Formatted phone numbers
    :rtype: str
    """
    try:
        import phonenumbers

        # Maybe the number is already internationally formatted
        try:
            parsed_phone_number = phonenumbers.parse(str(phone_number))
            formatted_number = phonenumbers.format_number(parsed_phone_number, phonenumbers.PhoneNumberFormat.E164)
            return formatted_number
        except phonenumbers.NumberParseException:
            pass

        # Maybe the country_code is correct
        try:
            parsed_phone_number = phonenumbers.parse(str(phone_number), region=country_code)
            formatted_number = phonenumbers.format_number(parsed_phone_number, phonenumbers.PhoneNumberFormat.E164)
            return formatted_number
        except phonenumbers.NumberParseException:
            raise InvalidUsage(error_message="format_phone_number(%s, %s): Couldn't parse phone number" % (phone_number,
                                                                                                           country_code))

    except:
        raise InvalidUsage(error_message="format_phone_number(%s, %s): Received other exception" % (phone_number,
                                                                                                    country_code))
        return False


def sanitize_zip_code(zip_code):
    """
    :param zip_code:
    :return:
    """
    zip_code = str(zip_code)
    zip_code = ''.join(filter(lambda character: character not in ' -', zip_code))
    if zip_code and not ''.join(filter(lambda character: not character.isdigit(), zip_code)):
        zip_code = zip_code.zfill(5) if len(zip_code) <= 5 else zip_code.zfill(9) if len(zip_code) <= 9 else ''
        if zip_code:
            return (zip_code[:5] + ' ' + zip_code[5:]).strip()
    # logger.info("[%s] is not a valid US Zip Code", zip_code)
    return None

