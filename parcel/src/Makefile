C++ := g++
GCC := gcc

APP = parcel

################################################################################
# Paths
################################################################################
INSTALL_PATH    = /usr/local/lib
SO_NAME         = lparcel.so
SO_PATH         = $(abspath $(dir mkfile_path))/$(SO_NAME)
INC_DIRS        = udt4/src simclist

################################################################################
# UDT
################################################################################
UDT_DIR         = udt4/src
UDT_OBJS        = libudt.so
UDT_OBJECTS     = $(patsubst %,$(UDT_DIR)/%,$(UDT_OBJS))

################################################################################
# Clist
################################################################################
CLIST_DIR       = simclist
CLIST_OBJS      = simclist.o
CLIST_OBJECTS   = $(patsubst %,$(CLIST_DIR)/%,$(CLIST_OBJS))

################################################################################
# Dependencies
################################################################################
DEP_DIRS        = $(CLIST_PATH)
DEP_OBJS        = $(CLIST_OBJECTS)

################################################################################
# Compiler flags
################################################################################
INCLUDES        = $(patsubst %,-I%,$(INC_DIRS)) $(patsubst %,-I%,$(DEPENDENCIES))
OPTFLAGS        = -finline-functions -O3
ERRFLAGS        = -Wall
FSFLAGS         = -D_LARGE_FILE_SOURCE=1
MISCFLAGS       = -g -fPIC -static
CCFLAGS         = $(INCLUDES) $(OPTFLAGS) $(FSFLAGS) $(ERRFLAGS) $(MISCFLAGS) -D$(os)
LDFLAGS         = -lstdc++ -lpthread -lm -ludt $(patsubst %,-L%,$(INC_DIRS))
LINK_FLAGS      = -shared -Wl,-soname,lparcel.so
LIBS            = -ludt

################################################################################
# Library objects
################################################################################
OBJECTS         = $(DEP_OBJS) transcribers.o udt2tcp.o tcp2udt.o

################################################################################
# OS options
################################################################################

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

################################################################################
# Build library
################################################################################

all: $(APP)

%.o: %.c
	$(GCC) $(CCFLAGS) $(LDFLAGS) $< -o $@ -c

%.o: %.cpp
	$(C++) $(CCFLAGS) $(LDFLAGS) $< -o $@ -c

parcel: $(OBJECTS)
	$(C++) $(LINK_FLAGS) -o $(SO_PATH) $(UDT_DIR)/libudt.so $(OBJECTS) $(LIBS)

################################################################################
# Build dependencies
################################################################################

udt4/src/libudt.so:
	make -C udt4/src

################################################################################
# Manage library
################################################################################

clean:
	rm -f $(OBJECTS) $(CLIST_OBJ) $(SO_NAME)

install:
	cp $(UDT_DIR)/libudt.so $(INSTALL_PATH)/libudt.so
	$(C++) $(LINK_FLAGS) -o $(SO_PATH) $(INSTALL_PATH)/libudt.so $(OBJECTS) $(LIBS)
	cp $(SO_PATH) $(INSTALL_PATH)/$(SO_NAME)
	ldconfig

uninstall:
	rm $(INSTALL_PATH)/$(SO_NAME)
