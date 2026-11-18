---
title: Linux and networking troubleshooting
categories: [linux, networking, troubleshooting]
license: CC-BY-4.0
attribution: CareerPilot AI contributors
---
# A slow Linux server: where to look

Start broad, then narrow down:

1. **Load and CPU**: `uptime` gives load averages; `top` or `htop` shows live per-process CPU and memory.
   A load much higher than the number of CPUs means processes are waiting, for CPU or for I/O.
2. **Memory**: `free -h` (a readable view of `/proc/meminfo`). Look at "available" memory and swap activity
   (`vmstat 1`, columns si/so). Heavy swapping makes everything slow.
3. **Disk I/O**: `iostat -x 1` or `iotop`: high utilisation or long wait times point to storage.
4. **Disk space**: `df -h` per filesystem and `du -sh` per directory. If `df` reports a full disk but `du`
   finds much less, a process still holds deleted files open: `lsof +L1`, then restart or signal the process.
5. **Logs and kernel**: `journalctl -u <service>`, and `dmesg` for driver errors, OOM-killer messages and
   disk errors.

# Networking basics

- **DNS**: `dig example.org` (or `nslookup`) shows the answer, the TTL and which server responded. `A`
  records hold IPv4 addresses, `AAAA` IPv6, `CNAME` aliases, `PTR` reverse lookups.
- **Connectivity**: `ping` for reachability, `traceroute`/`mtr` for the path, `curl -v` for HTTP and TLS,
  `ss -tulpn` for listening ports and the processes behind them.
- **CIDR**: a `/24` has 256 addresses, a `/22` has 1024 (2^(32-22)). Cloud providers reserve a few addresses
  in every subnet.
- **Firewalls** usually apply the first matching rule, so rule order matters.

# Permissions

`chmod 750 file` means owner rwx (7), group r-x (5), others none (0). Prefer groups and least privilege over
`777`.
