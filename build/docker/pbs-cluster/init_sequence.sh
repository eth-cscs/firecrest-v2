#!/bin/bash

sleep 5

while [ ! -f /var/run/sshd.pid ]; do
    echo "Waiting for sshd.pid..."
    sleep 1
done

# Restart PostgreSQL
service postgresql restart

# Create the munge key
dd if=/dev/urandom bs=1 count=1024 > /etc/munge/munge.key
chown munge:munge /etc/munge/munge.key
chmod 400 /etc/munge/munge.key

# Start Munge
service munge start

sleep 5

# sshpass -p 'root' ssh -o StrictHostKeyChecking=no localhost

sshpass -p 'root' ssh -T -o StrictHostKeyChecking=no localhost << 'EOF'
  /usr/libexec/pbs_postinstall
  sleep 5
  /etc/init.d/pbs start

  export HOSTNAME=$(hostname)
  /usr/bin/qmgr -c "create node $HOSTNAME"
  /usr/bin/qmgr -c "set node $HOSTNAME resources_available.ncpus = 1"
  /usr/bin/qmgr -c "set node $HOSTNAME resources_available.mem = 1024mb"
  /etc/init.d/pbs restart

  sleep 5

  mom_pid=$(ps aux | grep pbs_mom | grep -v grep | awk '{print $2}')
  kill -9 $mom_pid
  /usr/sbin/pbs_mom
EOF


# Run PBS post-install
#/opt/pbs/libexec/pbs_postinstall
# bash -lc "/opt/pbs/libexec/pbs_postinstall && /etc/init.d/pbs start"

#sleep 5

# Start PBS
#/etc/init.d/pbs start
# bash -l "/etc/init.d/pbs start"
# 
# # Wait for PBS to initialize
# sleep 5
# 
# # Configure PBS node
# HOSTNAME=$(hostname)
# /opt/pbs/bin/qmgr -c "create node $HOSTNAME"
# /opt/pbs/bin/qmgr -c "set node $HOSTNAME resources_available.ncpus = 1"
# /opt/pbs/bin/qmgr -c "set node $HOSTNAME resources_available.mem = 1024mb"
# 
# /etc/init.d/pbs restart
