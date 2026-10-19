chmod +x tri.sh
printf '15 12 * * 1-5 %s/tri.sh %s/inbox >> %s/tri.log 2>&1\n' "$PWD" "$PWD" "$PWD" > planning.cron
