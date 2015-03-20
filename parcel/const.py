###############################################################################
#                              Constants
###############################################################################

GB = 1024 * 1024 * 1024
MB = 1024 * 1024


# ======== Lengths ========
LEN_CONTROL = 10
LEN_TOKEN = 60
LEN_PAYLOAD_SIZE = 100
RES_CHUNK_SIZE = 64 * MB
HTTP_CHUNK_SIZE = 1 * MB

# ======== CONTROL TYPES ========
CNTL_HANDSHAKE = 'HANDSHAKE'
CNTL_DOWNLOAD = 'DOWNLOAD'
CNTL_FILE_INFO = 'FILE_INFO'
CNTL_EXIT = 'EXIT'


# ======== States ========
STATE_IDLE = 'STATE_IDLE'
