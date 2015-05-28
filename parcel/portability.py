import platform
from termcolor import colored as _colored

# Are we running on windows?
if platform.system() == 'Windows':
    OS = 'WINDOWS'
elif platform.system() == 'Darwin':
    OS = 'OSX'
elif platform.system() == 'Linux':
    OS = 'LINUX'    # Assume a posix system
else:
    OS = None


def colored(text, color):
    if OS == 'WINDOWS':
        return text
    else:
        return _colored(text, color)
