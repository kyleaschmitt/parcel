#!/usr/bin/env bash

# Get version
VERSION=$(git branch 2>/dev/null | grep '*' | sed s/'* '//g | cut -d'-' -f2)

# Create binary
pyinstaller --clean --noconfirm --onefile -c parcel

APPNAME="Parcel"
SOURCE="dist/parcel"

# Zip dist
zip "parcel_${VERSION}_Ubuntu14.04_x64.zip" "${SOURCE}"
