INSTALL_DIR = /usr/local/lib

all:
	make -C udt
	make install -C udt
	make -C parcel

parcel: all

udt:
	make -C udt

install:
	export LD_LIBRARY_PATH=:$(INSTALL_DIR):$$LD_LIBRARY_PATH
	sudo cp parcel/src/lparcel.so $(INSTALL_DIR)/lparcel.so

clean:
	make clean -C udt
	make clean -C parcel

.PHONY: install
