
__author__ = 'Erik Farmer'

from activity_service.app import app
from activity_service.common.routes import GTApis

if __name__ == '__main__':
    app.run(port=GTApis.ACTIVITY_SERVICE_PORT, debug=True)
