from social_network_service.tasks import import_meetup_events

import_meetup_events.apply_async(countdown=15)