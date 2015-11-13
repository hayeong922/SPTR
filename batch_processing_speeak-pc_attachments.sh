#!/bin/bash
PATH=/mnt/Python34/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

result=`ps aux | grep -i "src/integration.py" | grep -v "grep" | wc -l`
if [ $result -ge 1 ]
   then
        echo "term recognition batch processing script is running"
   else
        echo "term recognition batch processing is not running. Start now..."
	nohup /mnt/Python34/bin/python3.4 src/integration.py &
fi

