C++ = g++

ifndef os
   os = LINUX
endif

ifndef arch
   arch = IA32
endif

CCFLAGS = -Wall -D$(os) -I../udt/src -finline-functions -g -lcrypto -D_LARGE_FILE_SOURCE=1 -fPIC

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

LDFLAGS = -L../udt/src -lstdc++ -lpthread -lm

ifeq ($(os), UNIX)
   LDFLAGS += -lsocket
endif

ifeq ($(os), SUNOS)
   LDFLAGS += -lrt -lsocket
endif

DIR = $(shell pwd)

APP = parcel
APPOUT = parcel

mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
current_dir := $(notdir $(patsubst %/,%,$(dir $(mkfile_path))))

all: $(APP)

%.o: %.cpp
	$(C++) $(CCFLAGS) $(LDFLAGS) $< -c

parcel: server.o
	$(C++) -shared -Wl,-soname,lparcel.so -o $(abspath $(dir mkfile_path))/lparcel.so $< libudt.so

clean:
	rm -f *.o $(APP)

install:
	export PATH=$(DIR):$$PATH
