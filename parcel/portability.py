import platform
from termcolor import colored as _colored

OS_WINDOWS = False
OS_LINUX = False
OS_OSX = False

# Are we running on windows?
if platform.system() == 'Windows':
    OS_WINDOWS = True
elif platform.system() == 'Darwin':
    OS_OSX = True
elif platform.system() == 'Linux':
    OS_LINUX = True


def colored(text, color):
    if OS_WINDOWS:
        return text
    else:
        return _colored(text, color)
