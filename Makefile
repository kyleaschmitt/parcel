DIRS = parcel
TARGETS = all clean install uninstall

$(TARGETS): %: $(patsubst %, %.%, $(DIRS))

udt:
	make -C parcel/udt

$(foreach TGT, $(TARGETS), $(patsubst %, %.$(TGT), $(DIRS))):
	$(MAKE) -C $(subst ., , $@)
