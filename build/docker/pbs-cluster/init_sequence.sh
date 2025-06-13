#!/bin/bash

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

sshpass -p 'root' ssh -T -o StrictHostKeyChecking=no localhost << 'EOF'
  /usr/libexec/pbs_postinstall

  /etc/init.d/pbs start

  export HOSTNAME=$(hostname)
  /usr/bin/qmgr -c "create node $HOSTNAME"
  /usr/bin/qmgr -c "set node $HOSTNAME resources_available.ncpus = 1"
  /usr/bin/qmgr -c "set node $HOSTNAME resources_available.mem = 1024mb"
  /usr/bin/qmgr -c "set server job_history_enable = True"
  /usr/bin/qmgr -c "set server job_history_duration = 24:00:00"
  /etc/init.d/pbs restart

  mom_pid=$(ps aux | grep pbs_mom | grep -v grep | awk '{print $2}')
  kill -9 $mom_pid
  /usr/sbin/pbs_mom
EOF
