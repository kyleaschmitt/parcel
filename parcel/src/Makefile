C++ := g++

APP = parcel

# Paths
INSTALL_PATH := /usr/local/lib
mkfile_path  := $(abspath $(lastword $(MAKEFILE_LIST)))
current_dir  := $(notdir $(patsubst %/,%,$(dir $(mkfile_path))))
SO_PATH      := $(abspath $(dir mkfile_path))/lparcel.so
DIR          := $(shell pwd)

# Compiler flags
INCLUDES   = -I../lib/udt4/src/ -I../include/
OPTFLAGS   = -finline-functions -O3
LIBS       = -ludt
ERRFLAGS   = -Wall -Werror
FSFLAGS    = -D_LARGE_FILE_SOURCE=1
MISCFLAGS  = -g -fPIC
CCFLAGS    = -D$(os) $(INCLUDES) $(OPTFLAGS) $(FSFLAGS) $(ERRFLAGS) $(MISCFLAGS)
LDFLAGS    = -lstdc++ -lpthread -lm -L../lib/udt/src
LINK_FLAGS = -shared -Wl,-soname,lparcel.so

ifndef os
   os = LINUX
endif

ifndef arch
   arch = IA32
endif

ifeq ($(arch), IA32)
    CCFLAGS += -DIA32 #-mcpu=pentiumpro -march=pentiumpro -mmmx -msse
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

parcel: parcel.o
	$(C++) $(LINK_FLAGS) -o $(SO_PATH) $(INSTALL_PATH)/libudt.so parcel.o $(LIBS)

clean:
	rm -f *.o lparcel.so

install:
	export PATH=$(DIR):$$PATH
	cp lparcel.so $(INSTALL_PATH)/lparcel.so

uninstall:
	rm $(INSTALL_PATH)/lparcel.so $(INSTALL_PATH)/libudt.so
