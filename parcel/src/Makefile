C++ := g++

APP = parcel

# Paths
INSTALL_PATH := /usr/local/lib
mkfile_path  := $(abspath $(lastword $(MAKEFILE_LIST)))
current_dir  := $(notdir $(patsubst %/,%,$(dir $(mkfile_path))))
SO_NAME      := lparcel.so
SO_PATH      := $(abspath $(dir mkfile_path))/$(SO_NAME)
DIR          := $(shell pwd)

# Compiler flags
INCLUDES        = -I../lib/udt4/src/ -I../include/
OPTFLAGS        = -finline-functions -O3
LIBS            = -ludt
ERRFLAGS        = -Wall -Werror
FSFLAGS         = -D_LARGE_FILE_SOURCE=1
MISCFLAGS       = -g -fPIC
CCFLAGS         = $(INCLUDES) $(OPTFLAGS) $(FSFLAGS) $(ERRFLAGS) $(MISCFLAGS) -D$(os)
LDFLAGS         = -lstdc++ -lpthread -lm -L../lib/udt/src
LINK_FLAGS      = -shared -Wl,-soname,lparcel.so
LD_LINK_FLAGS   = $(INSTALL_PATH)/libudt.so

# Objects
OBJECTS = parcel.o transcribers.o udt2tcp.o tcp2udt.o

ifndef os
   os = LINUX
endif

ifndef arch
   arch = IA32
endif

ifeq ($(arch), IA32)
    CCFLAGS += -DIA32
endif

ifeq ($(arch), POWERPC)
   CCFLAGS += -mcpu=powerpc
endif

ifeq ($(arch), IA64)
   CCFLAGS += -DIA64
endif

ifeq ($(arch), SPARC)
   CCFLAGS += -DSPARC
endif

ifeq ($(os), UNIX)
   LDFLAGS += -lsocket
endif

ifeq ($(os), SUNOS)
   LDFLAGS += -lrt -lsocket
endif

all: $(APP)

%.o: %.cpp
	$(C++) $(CCFLAGS) $(LDFLAGS) $< -c -static

parcel: $(OBJECTS)
	$(C++) $(LINK_FLAGS) -o $(SO_PATH) $(LD_LINK_FLAGS) $(OBJECTS) $(LIBS)

clean:
	rm -f *.o $(SO_NAME)

install:
	export PATH=$(DIR):$$PATH
	ldconfig
	cp $(SO_PATH) $(INSTALL_PATH)/$(SO_NAME)

uninstall:
	rm $(INSTALL_PATH)/$(SO_NAME)
