# Does Amerika Office start with and without its sandbox in this environment?
(/usr/bin/amerika-office >$T/office-default.log 2>&1 & echo $! > $T/office-default.pid); sleep 8
kill -0 $(cat $T/office-default.pid) 2>/dev/null && echo "default: ALIVE" || echo "default: EXITED"
grep -m1 -oE "FATAL.*" $T/office-default.log | cut -c1-200
pkill -x amerika-office 2>/dev/null; sleep 2
(/usr/bin/amerika-office --no-sandbox >$T/office-nosandbox.log 2>&1 & echo $! > $T/office-nosandbox.pid); sleep 9
kill -0 $(cat $T/office-nosandbox.pid) 2>/dev/null && echo "--no-sandbox: ALIVE" || echo "--no-sandbox: EXITED"
pkill -x amerika-office 2>/dev/null; true
