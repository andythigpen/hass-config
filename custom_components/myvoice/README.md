# Snowboy

* Install manually via the github repo (no binary distributions for ARM)
    * https://github.com/Kitt-AI/snowboy.git
* Requires Swig 3.0.12+, also installed manually
* May require modifying setup.py to use 'Python3' instead of 'Python'
* Modify snowboydecoder to add the correct `input_device_index` for `self.audio.open()`


# ReSpeaker

* Install https://github.com/respeaker/respeaker_python_library.git
* pip install requirements
    * pocketsphinx
    * webrtcvad
* Modify respeaker/usb_hid/hidapi_backend.py to look for the correct product name
  'ReSpeaker' instead of 'MicArray'

## USB HID (LED control, etc.)

* pip install --upgrade setuptools 
* Install https://github.com/trezor/cython-hidapi.git

# SpeechRecognition

* pip3 install SpeechRecognition

# Pocketsphinx main installation

* See https://wolfpaulus.com/embedded/raspberrypi2-sr/

Sphinxbase
```
sudo apt-get install bison libasound2-dev swig python-dev mplayer
wget http://sourceforge.net/projects/cmusphinx/files/sphinxbase/5prealpha/sphinxbase-5prealpha.tar.gz
tar -zxvf ./sphinxbase-5prealpha.tar.gz
cd ./sphinxbase-5prealpha
./configure --enable-fixed
make clean all
make check
sudo make install
```

Pocketsphinx
```
wget http://sourceforge.net/projects/cmusphinx/files/sphinxbase/5prealpha/sphinxbase-5prealpha.tar.gz
tar -zxvf ./sphinxbase-5prealpha.tar.gz
cd ./sphinxbase-5prealpha
./configure --enable-fixed
make clean all
make check
sudo make install
```
