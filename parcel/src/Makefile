C++ := g++
GCC := gcc

APP = parcel

################################################################################
# Paths
################################################################################
# The path where the libraries will be installed
  INSTALL_PATH    = /usr/local/lib
# The name of the library
  SO_NAME         = lparcel.so
# The full instal path of the library
  SO_PATH         = $(abspath $(dir mkfile_path))/$(SO_NAME)
# Include directories
  INC_DIRS        = udt4/src simclist

################################################################################
# UDT
################################################################################
# The udt source directory
  UDT_DIR         = udt4/src
# The udt library name
  UDT_LIB         = libudt.so
# Construct the full path to local udt library
  UDT_OBJECTS     = $(patsubst %,$(UDT_DIR)/%,$(UDT_LIB))
# Construct the full path to installed udt library
  INST_UDT_OBJ    = $(patsubst %,$(INSTALL_PATH)/%,$(UDT_LIB))

################################################################################
# Dependencies
################################################################################
# Construct all depencency paths
  DEP_DIRS        = $(UDT_DIR)
# Construct all depencency objects
  DEP_OBJS        = $(UDT_OBJECTS)
# Construct all depencency objects with installation paths
  INST_DEP_OBJS   = $(INST_CLIST_OBJ)

################################################################################
# Compiler flags
################################################################################
# Construct include flags from INC_DIRS and dependencies
  INCLUDES        = $(patsubst %,-I%,$(INC_DIRS)) $(patsubst %,-I%,$(DEP_DIRS))
# Optimization flags
  OPTFLAGS        = -finline-functions -O3
# Error flags
  ERRFLAGS        = -Wall
# File system flags
  FSFLAGS         = -D_LARGE_FILE_SOURCE=1
# Misc flags
  MISCFLAGS       = -g -fPIC -static
# Construct compiler flags
  CCFLAGS         = $(INCLUDES) $(OPTFLAGS) $(FSFLAGS) $(ERRFLAGS) $(MISCFLAGS) -D$(os)
# LD linkning flags
  LDFLAGS         = -lstdc++ -lpthread -lm -ludt $(patsubst %,-L%,$(INC_DIRS))
# Other linking flags
  LINK_FLAGS      = -shared -Wl,-soname,lparcel.so
# Non-standard libraries
  LIBS            = -ludt -L$(UDT_DIR)

################################################################################
# Library objects
################################################################################
  OBJECTS         = transcribers.o udt2tcp.o tcp2udt.o cbuffer.o

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

parcel: $(OBJECTS) $(DEP_OBJS)
	$(C++) $(LINK_FLAGS) -o $(SO_PATH) $(DEP_OBJS) $(OBJECTS) $(LIBS)

################################################################################
# Build dependencies
################################################################################

$(UDT_OBJECTS):
	make -C udt4/src

$(CLIST_OBJECTS):
	cd simclist && cmake . && make

################################################################################
# Manage library
################################################################################

clean:
	rm -f $(OBJECTS) $(DEP_OBJS) $(SO_NAME)

install:
	mkdir -p $(INSTALL_PATH)
	cp $(UDT_OBJECTS) $(INST_UDT_OBJ)
	$(C++) $(LINK_FLAGS) -o $(SO_PATH) $(INST_DEP_OBJS) $(OBJECTS) $(LIBS)
	cp $(SO_PATH) $(INSTALL_PATH)/$(SO_NAME)
	ldconfig

uninstall:
	rm $(INSTALL_PATH)/$(SO_NAME) $(INST_UDT_OBJ)
