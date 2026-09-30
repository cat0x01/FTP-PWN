# FTP-PWN

FTP-PWN is a simple FTP penetration testing tool for authorized security assessments. It helps you quickly check common FTP risks such as anonymous access, weak credentials, known vulnerabilities, and unsafe configurations.



## Legal Notice
Use this tool **only** on systems you own or have explicit permission to test. You must confirm authorization with `--i-understand`.

## Features
- Banner grabbing and version fingerprinting
- Anonymous login check
- Brute-force login (multi-threaded, optional delay/jitter)
- Searchsploit integration
- Known vulnerability checks
- vsftpd 2.3.4 backdoor check
- FTP bounce attack check
- Writable directory check
- FTP enumeration (MLSD/LIST)
- FTPS support (explicit TLS)
- Username enumeration heuristic
- JSON report output

## Installation
This tool uses Python 3 and standard libraries. Optional external tool:
- `searchsploit` (from exploit-db) for exploit search

## Quick Start
```bash
python3 ftp_pwn.py -t 192.168.1.10 --i-understand
```


## Options
- `--auto` / `--all`: Run all checks automatically
- `--banner`: Grab banner only
- `--anon`: Anonymous login check only
- `--brute`: Brute-force login
- `--users`, `--passwords`: Wordlists for brute force
- `--threads`: Brute-force threads (default 10)
- `--delay`, `--jitter`: Slow down brute force attempts
- `--vuln`: Known vulnerabilities only
- `--ftps`: Use explicit FTPS (AUTH TLS)
- `--mlsd`: Prefer MLSD for listings
- `--enum`: Username enumeration check
- `--timeout`: Connection timeout
- `--json`: Save JSON report
- `--i-understand`: Confirm authorized testing

## Notes
- Some FTP servers intentionally return the same response for all usernames. In that case, user enumeration results may be false positives.
- `searchsploit` results are best when the banner reveals a precise server version.

## Disclaimer
This project is for educational and authorized testing only. The author is not responsible for misuse.
