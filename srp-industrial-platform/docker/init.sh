#!/bin/sh
set -eu
umask 077
for path in /broker /pg /sim-auth /apm-auth; do
  mkdir -p "$path"
done
new_secret() { od -An -v -N24 -tx1 /dev/urandom | tr -d ' \n'; }
[ -s /sim-auth/password ] || new_secret > /sim-auth/password
[ -s /apm-auth/password ] || new_secret > /apm-auth/password
[ -s /pg/password ] || new_secret > /pg/password
printf 'simulator:%s\napm:%s\n' "$(cat /sim-auth/password)" "$(cat /apm-auth/password)" > /broker/passwd
mosquitto_passwd -U /broker/passwd
chmod 755 /broker /pg
chown 1883:1883 /broker/passwd
chmod 600 /broker/passwd
chmod 644 /pg/password
