C++ = g++

CCFLAGS = -Wall -D$(os) -I../../udt/src -finline-functions -g\
	 -lcrypto -lopenssl -D_LARGE_FILE_SOURCE=1 -fPIC
LINK_FLAGS = -shared -Wl,-soname,lparcel.so
DIR = $(shell pwd)
INSTALL_PATH = /usr/local/lib
APP = parcel
APPOUT = parcel
mkfile_path := $(abspath $(lastword $(MAKEFILE_LIST)))
current_dir := $(notdir $(patsubst %/,%,$(dir $(mkfile_path))))
so_path := $(abspath $(dir mkfile_path))/lparcel.so
LIBS = -lssl -lcrypto -ludt
LDFLAGS = -L../../udt/src -lstdc++ -lpthread -lm -g

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

parcel: parcel.o crypto.o
	$(C++) $(LINK_FLAGS) -o $(so_path) $(INSTALL_PATH)/libudt.so parcel.o crypto.o $(LIBS)

clean:
	rm -f *.o parcel.so

install:
	export PATH=$(DIR):$$PATH
	cp lparcel.so $(INSTALL_PATH)/

uninstall:
	rm $(INSTALL_PATH)/lparcel.so
