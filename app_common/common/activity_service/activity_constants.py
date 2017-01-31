"""
Constants container copy for different activity types.
"""

CANDIDATENAME_CAMPAIGNNAME = ('candidate_name', 'campaign_name')
USERNAME_CAMPAIGNNAME = ('username', 'campaign_name')
USERNAME_CAMPAIGNTYPE_CAMPAIGNNAME = ('username', 'campaign_type', 'campaign_name')
USERNAME_EVENTTITLE = ('username', 'event_title')
USERNAME_FORMATTEDNAME = ('username', 'formatted_name')

ACTIVTY_PARAMS = {
    "CAMPAIGN_CREATE": USERNAME_CAMPAIGNTYPE_CAMPAIGNNAME,
    "CAMPAIGN_DELETE": USERNAME_CAMPAIGNTYPE_CAMPAIGNNAME,
    "CAMPAIGN_EMAIL_CLICK": CANDIDATENAME_CAMPAIGNNAME,
    "CAMPAIGN_EMAIL_OPEN": CANDIDATENAME_CAMPAIGNNAME,
    "CAMPAIGN_EMAIL_SEND": CANDIDATENAME_CAMPAIGNNAME,
    "CAMPAIGN_EXPIRE": USERNAME_CAMPAIGNNAME,
    "CAMPAIGN_PAUSE": USERNAME_CAMPAIGNNAME,
    "CAMPAIGN_PUSH_CLICK": CANDIDATENAME_CAMPAIGNNAME,
    "CAMPAIGN_PUSH_CREATE": USERNAME_CAMPAIGNNAME,
    "CAMPAIGN_PUSH_SEND": CANDIDATENAME_CAMPAIGNNAME,
    "CAMPAIGN_RESUME": USERNAME_CAMPAIGNNAME,
    "CAMPAIGN_SCHEDULE": USERNAME_CAMPAIGNTYPE_CAMPAIGNNAME,
    "CAMPAIGN_SEND": ('campaign_name', 'num_candidates'),
    "CAMPAIGN_SMS_CLICK": CANDIDATENAME_CAMPAIGNNAME,
    "CAMPAIGN_SMS_REPLY": ('candidate_name', 'campaign_name', 'reply_text'),
    "CAMPAIGN_SMS_SEND": CANDIDATENAME_CAMPAIGNNAME,
    "CANDIDATE_CREATE_CSV": USERNAME_FORMATTEDNAME,
    "CANDIDATE_CREATE_MOBILE": USERNAME_FORMATTEDNAME,
    "CANDIDATE_CREATE_WEB": USERNAME_FORMATTEDNAME,
    "CANDIDATE_CREATE_WIDGET": ('formatted_name',),
    "CANDIDATE_DELETE": USERNAME_FORMATTEDNAME,
    "CANDIDATE_UPDATE": USERNAME_FORMATTEDNAME,
    "DUMBLIST_CREATE": ('username', 'dumblist_name'),
    "DUMBLIST_DELETE": ('username', 'dumblist_name'),
    "EVENT_CREATE": USERNAME_EVENTTITLE,
    "EVENT_DELETE": USERNAME_EVENTTITLE,
    "EVENT_UPDATE": USERNAME_EVENTTITLE,
    "NOTIFICATION_CREATE": (),
    "PIPELINE_CREATE": ('username', 'pipeline_name'),
    "PIPELINE_DELETE": ('username', 'pipeline_name'),
    "RSVP_EVENT": ('first_name', 'last_name', 'response', 'creator'),
    "SMARTLIST_ADD_CANDIDATE": ('formatted_name', 'smartlist_name'),
    "SMARTLIST_CREATE": ('username', 'smartlist_name'),
    "SMARTLIST_DELETE": ('username', 'smartlist_name'),
    "SMARTLIST_REMOVE_CANDIDATE": ('formatted_name', 'smartlist_name'),
    "TALENT_POOL_CREATE": ('username', 'talent_pool_name'),
    "TALENT_POOL_DELETE": ('username', 'talent_pool_name'),
    "USER_CREATE": ('username',),
    "WIDGET_VISIT": (),
}