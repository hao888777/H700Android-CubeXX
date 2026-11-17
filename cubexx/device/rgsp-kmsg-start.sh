#!/system/bin/sh
set -eu
export PATH=/system/bin:/vendor/bin

LOG=/data/rgsp-persist/RGSP_ANDROID_KMSG_BOUNDED.log
mkdir -p /data/rgsp-persist
# setgid root:log so rotated files inherit the log group; shell (group log) can
# then read the bounded kernel log for on-device diagnosis without root.
chown root:log /data/rgsp-persist
chmod 2750 /data/rgsp-persist
/vendor/bin/rgsp_kmsg_logger "$LOG" &
reader=$!
# The logger creates files 0600; grant group read across rotation.
( while kill -0 "$reader" 2>/dev/null; do
    chmod 0640 "$LOG" "$LOG.1" "$LOG.2" "$LOG.3" 2>/dev/null || true
    sleep 5
  done ) &
watchdog=$!
trap 'kill "$reader" "$watchdog" 2>/dev/null || true; wait "$reader" "$watchdog" 2>/dev/null || true' EXIT
trap 'exit 0' TERM INT
sleep 1
kill -0 "$reader"
[ -s "$LOG" ]
chmod 0640 "$LOG" 2>/dev/null || true

# Stop only the inherited reader of the historical handoff log, after the
# bounded replacement is alive. Do not truncate or delete the old evidence.
for process in /proc/[0-9]*; do
    command=$(tr '\000' ' ' 2>/dev/null < "$process/cmdline") || continue
    case "$command" in
        "busybox cat /dev/kmsg "|"/bin/busybox cat /dev/kmsg ") ;;
        *) continue ;;
    esac
    target=$(readlink "$process/fd/1" 2>/dev/null) || continue
    [ "$target" = /rgsp-boot/RGSP_ANDROID_KMSG_LAST.log ] || continue
    kill "${process##*/}"
done
wait "$reader"
