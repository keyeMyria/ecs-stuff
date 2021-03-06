__author__ = 'basit'

ALL_EMAIL_CAMPAIGN_FIELDS = ["id",
                             "user_id",
                             "name",
                             "frequency",
                             "subject",
                             "description",
                             "from",
                             "reply_to",
                             "start_datetime",
                             "end_datetime",
                             "added_datetime",
                             "body_html",
                             "body_text",
                             "is_hidden",
                             "talent_pipelines",
                             "list_ids",
                             "scheduler_task_id",
                             "email_client_credentials_id",
                             "base_campaign_id"]

CAMPAIGN_OPTIONAL_FIELDS = ['from',
                            'reply_to',
                            'body_text',
                            'description',
                            'start_datetime',
                            'end_datetime']

EMAIL_CLIENTS_ALL_FIELDS = ['name',
                            'host',
                            'port',
                            'email',
                            'password']

EMAIL_CLIENTS_OPTIONAL_FIELDS = ['port']

CAMPAIGN_REQUIRED_FIELDS = ['name', 'subject', 'body_html', 'frequency_id', 'list_ids']
