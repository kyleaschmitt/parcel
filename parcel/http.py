import urlparse
import requests
from threading import Thread

from log import get_logger
from const import RES_CHUNK_SIZE
from utils import print_download_information

# Logging
log = get_logger()
try:
    requests.packages.urllib3.disable_warnings()
except Exception as e:
    log.error('Unable to silence requests warnings: {}'.format(str(e)))


####################################################################
#                            Util functions
####################################################################


####################################################################
#                          SThread functions
####################################################################
