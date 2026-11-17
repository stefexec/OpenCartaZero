#!/bin/sh
set -e
sudo mkdir -p /usr/share/APPLaunch/apps/opencartazero /usr/share/APPLaunch/bin /usr/share/APPLaunch/applications /usr/share/APPLaunch/share/images
sudo cp opencartazero.py /usr/share/APPLaunch/apps/opencartazero/opencartazero.py
sudo chmod 755 /usr/share/APPLaunch/apps/opencartazero/opencartazero.py
sudo cp opencartazero /usr/share/APPLaunch/bin/opencartazero
sudo chmod 755 /usr/share/APPLaunch/bin/opencartazero
sudo cp opencartazero.desktop /usr/share/APPLaunch/applications/opencartazero.desktop
sudo cp opencartazero.png /usr/share/APPLaunch/share/images/opencartazero.png
echo "OpenCartaZero installed to /usr/share/APPLaunch!"
