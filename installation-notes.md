#Installation notes
=====================

##Term Recognition Tool

1) wget https://www.python.org/ftp/python/3.4.3/Python-3.4.3.tgz

2) tar -xvzf Python-3.4.3.tgz

3) chmod 777 -R Python-3.4.3

4) /home/ac1jgx/Python-3.4.3$ ./configure --prefix=/mnt/Python34  &&
	make

5) sudo chmod 777 -R /mnt/Python34

6) sudo apt-get install libssl-dev libsqlite3-dev

7) sudo make install && chmod -v 755 /mnt/Python-3.4.3/libpython3.4m.a

8) sudo chmod 777 -R /mnt/Python34

9) sudo wget https://bootstrap.pypa.io/get-pip.py

10) /mnt$ sudo /mnt/Python34/bin/python3.4 get-pip.py

11) sudo apt-get install libblas-dev checkinstall

12) sudo apt-get install libblas-doc checkinstall

13) sudo apt-get install liblapacke-dev checkinstall

14) sudo apt-get install liblapack-doc checkinstall

15) apt-get install libatlas-base-dev

16) sudo apt-get update

    sudo apt-get install gfortran

17) sudo /mnt/Python34/bin/pip3.4 install NLTK==3.0

18) sudo /mnt/Python34/bin/python3.4 -m nltk.downloader all

19) sudo /mnt/Python34/bin/pip3.4 install -U pandas

20) sudo /mnt/Python34/bin/pip3.4 install -U httplib2

21) sudo /mnt/Python34/bin/pip3.4 install -U chardet

22) sudo /mnt/Python34/bin/pip3.4 install -U beautifulsoup4

23) sudo /mnt/Python34/bin/pip3.4 install -U Flask

24) sudo apt-get install git

25) sudo git clone https://github.com/jerrygaoLondon/flask-mako.git

	/mnt/flask-mako$ sudo /mnt/Python34/bin/python3.4 setup.py install

26) modify config/config

	required:
* the local solr url('solr_core_url')
* path of 'pos_sequence_filter'
* path of 'stopwords'

optional:
* path of 'dictionary_file'
* ...

27) modify log file path in config/logging.conf
* change log file path in 'args' of "handler_fileHandler"
	
28) modify src/integration.py for integration task
* remote solr for retrieving source documents ('remote_solr_server')
* local/internal solr for term recognition computation and indexing ('local_solr_server')

29) setup term recognition as scheduled task in linux
	Solution:
* use crontab via "crontab -e"
* e.g., run batch processing every night:

```
29 0 * * * /mnt/SPEEAK-PC-TermRecognition/batch_processing_speeak-pc_attachments.sh
```

## Facet Navigation/Search UI

1) modify solr core url in /TATA-Steel-Web-Demo/web/js/tatasteel.js

2) deploy/copy 'TATA-Steel-Web-Demo' to tomcat server at dedicated port
