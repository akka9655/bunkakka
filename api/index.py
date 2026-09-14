"""
Smart Bunker - Flask Backend
============================
Attendance tracking and bunker-planning system that supports three colleges:

┌──────────────────────────────────────────────────────────────────────────────┐
│  College  │  Roll No Format     │  Portal URL                  │  Min Att.  │
├──────────────────────────────────────────────────────────────────────────────┤
│ PSG Tech  │ 6-7 alphanumeric    │ ecampus.psgtech.ac.in        │  75% (exam)│
│           │ e.g. 22CSA01        │ /studzone2/                  │  80% bunk  │
├──────────────────────────────────────────────────────────────────────────────┤
│ PSG IAS   │ 7 chars w/ letters  │ ecampus.psgias.ac.in/        │  75%       │
│           │ e.g. 25IR007        │ Login/UserLogin               │            │
├──────────────────────────────────────────────────────────────────────────────┤
│ CEG / AU  │ exactly 10 digits   │ www.auegov.ac.in/            │  75%       │
│ (Anna Uni)│ e.g. 2023103001     │ Login/UserLogin (CeGov)      │            │
└──────────────────────────────────────────────────────────────────────────────┘

College Detection Logic (detect_college):
  1. If roll number matches r'^\d{10}$'        → CEG  (CeGov / Anna Univ portal)
  2. If roll has a known PSG Tech course code  → PSGTECH
  3. Otherwise                                 → PSGIAS

Scraper Classes:
  - EcampusScraper      : PSG Tech  (ecampus.psgtech.ac.in/studzone2/)
  - EcampusIASScraper   : PSG IAS   (ecampus.psgias.ac.in/)
  - EcampusCEGScraper   : CEG/AU    (www.auegov.ac.in/) — min attendance 75%

API Endpoints:
  POST /api/login           → Authenticate + fetch attendance/timetable
  GET  /api/calendar/<roll> → Academic calendar (PSG Tech only; CEG/IAS return empty)
  POST /api/internals       → CA marks          (PSG Tech only)
  POST /api/gpa             → GPA / results     (PSG Tech only)
  POST /api/cgpa            → CGPA history      (PSG Tech only)
"""

from flask import Flask, render_template, request, jsonify
import requests
from bs4 import BeautifulSoup
import math
import time
from datetime import datetime
import os
import json
import logging
import urllib3

urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def get_disk_cache(cache_key, max_age_seconds=900):
    """Read cached JSON data from /tmp/ if within max_age_seconds"""
    try:
        path = f"/tmp/{cache_key}.json"
        if os.path.exists(path):
            if (time.time() - os.path.getmtime(path)) < max_age_seconds:
                with open(path, 'r') as f:
                    return json.load(f)
    except Exception as e:
        logger.debug(f"Disk cache read miss for {cache_key}: {e}")
    return None


def set_disk_cache(cache_key, data):
    """Write JSON data to /tmp/"""
    try:
        path = f"/tmp/{cache_key}.json"
        with open(path, 'w') as f:
            json.dump(data, f)
    except Exception as e:
        logger.debug(f"Disk cache write error for {cache_key}: {e}")


# ============================================================================
# ===== EDIT THESE VALUES EACH SEMESTER =====
# ============================================================================

CONFIG = {
    # API year (change each academic year)
    'API_YEAR': 2026,
    
    # Planner ID mapping (update each semester if needed)
    # Format: "COURSE_YEAR": PLANNER_ID
    'PLANNER_MAP': {
        # BE/BTech Programs
        "BE_1": 39, "BTech_1": 39,
        "BE_2": 33, "BTech_2": 33,
        "BE_3": 32, "BTech_3": 32,
        "BE_4": 32, "BTech_4": 32,
        "BE_5": 35,
        
        # BSc Programs (ALL YEARS - same calendar)
        "BSc_1": 32, "BSc_2": 32, "BSc_3": 32,
        
        # MSc Programs (ALL YEARS - same calendar)
        "MSc_1": 32, "MSc_2": 32,
        
        # ME/MTech Programs
        "ME_1": 32, "MTech_1": 32,
        "ME_2": 32, "MTech_2": 32,
        
        # MCA Program
        "MCA_1": 33, "MCA_2": 32,
    },
    
    # Course code mapping (usually stable - based on roll number letter)
    'COURSE_CODES': {
        # BE codes
        'U': 'BE', 'A': 'BE', 'D': 'BE', 'C': 'BE', 'Z': 'BE',
        'N': 'BE', 'E': 'BE', 'L': 'BE', 'M': 'BE', 'Y': 'BE',
        'P': 'BE', 'R': 'BE',
        
        # BTech codes
        'B': 'BTech', 'H': 'BTech', 'I': 'BTech', 'T': 'BTech',
        
        # BSc codes
        'S': 'BSc', 'X': 'BSc',
        
        # ME codes (two letters)
        'AE': 'ME', 'NB': 'ME', 'ZC': 'ME', 'UC': 'ME',
        'EE': 'ME', 'MD': 'ME', 'MN': 'ME', 'PP': 'ME',
        'ED': 'ME', 'CS': 'ME', 'LV': 'ME', 'BT': 'ME',
        'LN': 'ME', 'TT': 'ME', 'SE': 'ME',
        
        # MTech codes
        'CE': 'MTech', 'EC': 'MTech', 'IT': 'MTech', 'ME': 'MTech',
        
        # MCA code
        'MX': 'MCA',
        
        # MBA codes
        'GM': 'MBA', 'GW': 'MBA',
        
        # MSc codes (using letters from your list)
        'SA': 'MSc', 'FD': 'MSc', 'XW': 'MSc', 'XT': 'MSc', 'XD': 'MSc', 'XC': 'MSc',
    }
}

# ============================================================================
# ===== END OF EDITABLE SECTION =====
# ============================================================================

app = Flask(__name__, template_folder='templates', static_folder='../static')

session_secret = os.environ.get("SESSION_SECRET")
if not session_secret:
    logger.warning("SESSION_SECRET not set - using development fallback")
    session_secret = "bunker-dev-secret-key-change-in-production"

app.secret_key = session_secret

import gzip
from io import BytesIO

@app.after_request
def compress_response(response):
    """Automatically Gzip-compress responses to minimize Vercel Fast Origin Transfer bandwidth."""
    accept_encoding = request.headers.get('Accept-Encoding', '')
    if (
        'gzip' in accept_encoding.lower()
        and response.status_code < 400
        and not response.direct_passthrough
        and 'Content-Encoding' not in response.headers
    ):
        data = response.get_data()
        if len(data) > 500:
            gzip_buffer = BytesIO()
            with gzip.GzipFile(mode='wb', fileobj=gzip_buffer, compresslevel=6) as gz:
                gz.write(data)
            compressed = gzip_buffer.getvalue()
            if len(compressed) < len(data):
                response.set_data(compressed)
                response.headers['Content-Encoding'] = 'gzip'
                response.headers['Content-Length'] = len(compressed)
    return response


# Helper functions for calendar API
def get_academic_year(roll_number):
    """Calculate academic year from roll number"""
    if not roll_number or len(roll_number) < 2:
        return None
    
    try:
        admission_year = int('20' + roll_number[:2])
        current_year = datetime.now().year
        current_month = datetime.now().month
        
        if current_month >= 1 and current_month <= 5:
            academic_year = current_year - 1
        else:
            academic_year = current_year
        
        year_of_study = academic_year - admission_year + 1
        return max(1, min(5, year_of_study))
    except:
        return None


def get_course_type(roll_number):
    """Get course type from roll number"""
    if not roll_number or len(roll_number) < 3:
        return None
    
    letters = roll_number[2:]
    
    # Check two-letter codes first
    if len(letters) >= 2:
        two_letters = letters[:2].upper()
        if two_letters in CONFIG['COURSE_CODES']:
            return CONFIG['COURSE_CODES'][two_letters]
    
    # Check single letter
    first_letter = letters[0].upper()
    return CONFIG['COURSE_CODES'].get(first_letter)


def get_planner_id(roll_number):
    """Get planner ID for calendar from roll number"""
    if not roll_number or len(roll_number) < 6:
        return None
    
    course_type = get_course_type(roll_number)
    academic_year = get_academic_year(roll_number)
    
    if not course_type or not academic_year:
        return None
    
    map_key = f"{course_type}_{academic_year}"
    return CONFIG['PLANNER_MAP'].get(map_key)


def detect_college(roll_number):
    """
    Determine which college a student belongs to, based on roll number format.

    Rules (applied in order):
      1. Exactly 10 digits  →  'CEG'     (Anna Univ. / CeGov portal: auegov.ac.in)
         e.g. 2023103001
      2. Contains a known PSG Tech course code letter(s)  →  'PSGTECH'
         e.g. 22CSA01  (C = BE course code)
      3. Anything else  →  'PSGIAS'
         e.g. 25IR007
    """
    if not roll_number:
        return None
    
    roll_number = roll_number.strip().upper()
    
    # --- Rule 1: CEG (Anna University constituent colleges) ---
    # CEG roll numbers are exactly 10 numeric digits, e.g. 2023103001
    # They are purely numeric, so we check before looking for letters.
    import re
    if re.match(r'^\d{10}$', roll_number):
        return 'CEG'
    
    # --- Rule 2: PSG Tech ---
    # PSG Tech roll numbers contain uppercase letters (course code) after the year.
    # e.g. 22CSA01 → letters 'C' or 'CS' map to a known course type.
    match = re.search(r'[A-Z]+', roll_number)
    if match:
        course_code = match.group(0)
        if course_code in CONFIG['COURSE_CODES']:
            return 'PSGTECH'

    # --- Rule 3: PSG IAS (default) ---
    # Roll numbers with letters not in PSG Tech's course code list (e.g. 25IR007)
    # or other unrecognised formats fall through to PSG IAS.
    return 'PSGIAS'


def is_absolute_grading(roll_number):
    """Check if the student follows the Absolute Grading System"""
    return True


class EcampusScraper:
    """
    Ultra-Fast Dual-Engine Scraper for PSG College of Technology (PSG Tech).

    Portals:
      1. Primary: https://ecampus.psgtech.ac.in/studzone/ (Modern ASP.NET Core)
         - Concurrent parallel prefetch of Attendance & Timetable via ThreadPoolExecutor (< 0.7s)
         - 90% lighter payload, non-crashing, highly reliable
      2. Fallback: https://ecampus.psgtech.ac.in/studzone2/ (Classic ASP.NET WebForms)
         - Automatic failover if studzone is under maintenance
         - Used for Exam Results (FrmEpsStudResult.aspx) and CGPA history
    """
    ECAMPUS_URL = "https://ecampus.psgtech.ac.in/studzone2/"
    STUDZONE_URL = "https://ecampus.psgtech.ac.in/studzone/"

    def __init__(self, username, password, timeout=7, prefetch=True, force_studzone2=False):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
        })
        adapter = requests.adapters.HTTPAdapter(pool_connections=15, pool_maxsize=15)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        
        self.username = username.strip().upper()
        self.password = password.strip()
        self.timeout = timeout
        self.portal_type = None  # 'new' or 'old'
        self.authenticated = False
        self._att_html = None
        self._tt_html = None
        self._studzone2_authenticated = False
        
        if force_studzone2:
            self.authenticated = self._login_studzone2()
            if not self.authenticated:
                self.authenticated = self._login()
        else:
            self.authenticated = self._login()

        if self.authenticated and prefetch:
            self._prefetch_data()

    def _login(self):
        """Attempt login with primary (studzone) and fallback to (studzone2)"""
        # 1. Primary: Fast ASP.NET Core Studzone
        try:
            r_get = self.session.get(self.STUDZONE_URL, verify=False, timeout=self.timeout)
            soup = BeautifulSoup(r_get.text, 'html.parser')
            tok_el = soup.find('input', {'name': '__RequestVerificationToken'})
            if tok_el and tok_el.get('value'):
                token = tok_el['value']
                payload = {
                    'rollno': self.username,
                    'password': self.password,
                    'chkterms': 'on',
                    '__RequestVerificationToken': token
                }
                r_post = self.session.post(
                    self.STUDZONE_URL,
                    data=payload,
                    verify=False,
                    allow_redirects=False,
                    timeout=self.timeout
                )
                if r_post.status_code in (301, 302, 303, 307, 308):
                    loc = r_post.headers.get('Location', '')
                    if loc and not loc.endswith('/studzone') and not loc.endswith('/studzone/'):
                        self.portal_type = 'new'
                        return True
                    elif loc:
                        r_chk = self.session.get(f'https://ecampus.psgtech.ac.in{loc}', verify=False, timeout=self.timeout)
                        if 'Invalid' not in r_chk.text and 'password' not in r_chk.text.lower():
                            self.portal_type = 'new'
                            return True
                elif 'Student Login' not in r_post.text and ('Menu' in r_post.text or 'Attendance' in r_post.text):
                    self.portal_type = 'new'
                    return True
        except Exception as e:
            logger.warning(f"Studzone (new) login attempt: {e}")

        # 2. Fallback: Classic Studzone2
        return self._login_studzone2()

    def _login_studzone2(self):
        """Authenticate on studzone2 (WebForms)"""
        try:
            login_url = f"{self.ECAMPUS_URL}AttWfLoginPage.aspx"
            login_page = self.session.get(login_url, verify=False, timeout=self.timeout)
            soup = BeautifulSoup(login_page.text, 'html.parser')
            view_state = soup.find('input', {'name': '__VIEWSTATE'})
            event_validation = soup.find('input', {'name': '__EVENTVALIDATION'})
            view_state_gen = soup.find('input', {'name': '__VIEWSTATEGENERATOR'})

            if not all([view_state, event_validation, view_state_gen]):
                return False

            login_data = {
                '__VIEWSTATE': view_state.get('value', ''),
                '__VIEWSTATEGENERATOR': view_state_gen.get('value', ''),
                '__EVENTVALIDATION': event_validation.get('value', ''),
                'rdolst': 'S',
                'txtusercheck': self.username,
                'txtpwdcheck': self.password,
                'abcd3': 'Login'
            }

            self.session.headers['Referer'] = login_url
            response = self.session.post(login_url, data=login_data, verify=False, timeout=self.timeout)
            if ('AttWfStudMenu' in response.url or 'Invalid' not in response.text) and response.status_code == 200:
                self.portal_type = 'old'
                self._studzone2_authenticated = True
                self.session.headers['Referer'] = f"{self.ECAMPUS_URL}AttWfStudMenu.aspx"
                return True
        except Exception as e:
            logger.error(f"Studzone2 login error: {e}")
        return False

    def ensure_studzone2_auth(self):
        """Ensure session on studzone2 for GPA/CGPA results pages with proper referer and menu initialization"""
        if not self._studzone2_authenticated:
            self._login_studzone2()
        self.session.headers['Referer'] = f"{self.ECAMPUS_URL}AttWfStudMenu.aspx"
        try:
            self.session.get(f"{self.ECAMPUS_URL}AttWfStudMenu.aspx", verify=False, timeout=self.timeout)
        except Exception:
            pass
        return self._studzone2_authenticated

    def _prefetch_data(self):
        """Fetch attendance and timetable concurrently using ThreadPoolExecutor"""
        if not self.authenticated:
            return
        from concurrent.futures import ThreadPoolExecutor

        def fetch(url):
            try:
                return self.session.get(url, verify=False, timeout=self.timeout).text
            except Exception as e:
                logger.error(f"Prefetch error for {url}: {e}")
                return None

        if self.portal_type == 'new':
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_att = ex.submit(fetch, f"{self.STUDZONE_URL}Attendance/StudentPercentage")
                f_tt = ex.submit(fetch, f"{self.STUDZONE_URL}Attendance/TimeTable")
                self._att_html = f_att.result()
                self._tt_html = f_tt.result()
        else:
            with ThreadPoolExecutor(max_workers=2) as ex:
                f_att = ex.submit(fetch, f"{self.ECAMPUS_URL}AttWfPercView.aspx")
                f_tt = ex.submit(fetch, f"{self.ECAMPUS_URL}AttWfStudTimtab.aspx")
                self._att_html = f_att.result()
                self._tt_html = f_tt.result()

    def get_attendance(self):
        """Fetch attendance data from eCampus"""
        if not self.authenticated:
            return None, None, "Authentication failed"

        if not self._att_html:
            self._prefetch_data()

        if not self._att_html:
            return None, "No data", "Attendance data not available"

        try:
            soup = BeautifulSoup(self._att_html, 'html.parser')
            table = soup.find('table', {'id': 'example'}) if self.portal_type == 'new' else soup.find('table', {'class': 'cssbody'})
            if not table:
                # If new portal table wasn't found, try old portal fallback
                if self.portal_type == 'new' and self.ensure_studzone2_auth():
                    self.portal_type = 'old'
                    self._prefetch_data()
                    return self.get_attendance()
                return None, "No data", "Attendance table not found"

            attendance_data = []
            last_update = None
            rows = table.find_all('tr')[1:]

            def safe_int(v):
                try: return int(v)
                except: return 0

            def safe_float(v):
                try: return float(v.replace('%', '').strip())
                except: return 0.0

            for row in rows:
                cols = [col.text.strip() for col in row.find_all('td')]
                if len(cols) >= 10:
                    try:
                        total = safe_int(cols[1])
                        exemption = safe_int(cols[2])
                        attended = safe_int(cols[4])

                        attendance_data.append({
                            'code': cols[0],
                            'name': cols[0],
                            'total': total,
                            'attended': attended,
                            'exemption': exemption,
                            'percentage': safe_float(cols[5]),
                            'pct_exemp': safe_float(cols[6]),
                            'pct_medical': safe_float(cols[7]),
                        })

                        if not last_update and cols[9]:
                            date_str = cols[9].strip()
                            try:
                                date_obj = datetime.strptime(date_str, '%d-%m-%Y')
                                last_update = date_obj.strftime('%b %d, %Y')
                            except:
                                last_update = date_str
                    except (ValueError, IndexError):
                        continue

            if not last_update:
                last_update = "No data"

            return attendance_data, last_update, "Success"
        except Exception as e:
            logger.error(f"Attendance fetch error: {str(e)}")
            return None, "No data", f"Error: {str(e)}"

    def get_timetable_and_schedule(self):
        """Extract course mapping, weekly schedule, and student name in a single pass"""
        if not self.authenticated:
            return {}, {d: [] for d in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']}, "Student"

        if not self._tt_html:
            self._prefetch_data()

        course_mapping = {}
        schedule = {'Mon': [], 'Tue': [], 'Wed': [], 'Thu': [], 'Fri': []}
        student_name = "Student"

        if not self._tt_html:
            return course_mapping, schedule, student_name

        try:
            import re
            soup = BeautifulSoup(self._tt_html, 'html.parser')
            if self.portal_type == 'new':
                # Student Name from timetable header
                name_b = soup.find('b', string=re.compile(r'^[A-Z\s]{4,}$'))
                if name_b:
                    student_name = name_b.text.strip()

                table = soup.find('table')
                day_map = {
                    'monday': 'Mon', 'tuesday': 'Tue', 'wednesday': 'Wed',
                    'thursday': 'Thu', 'friday': 'Fri'
                }
                if table:
                    for tr in table.find_all('tr'):
                        cells = [c.text.strip() for c in tr.find_all(['td', 'th'])]
                        if not cells:
                            continue
                        day_key = cells[0].lower()
                        if day_key in day_map:
                            short_day = day_map[day_key]
                            for cell_text in cells[1:]:
                                if not cell_text or cell_text == '-':
                                    schedule[short_day].append('Free')
                                else:
                                    lines = [l.strip() for l in cell_text.split('\n') if l.strip()]
                                    m_code = re.search(r'\b([0-9]{2}[A-Z0-9]+|TWM|[A-Z0-9]{4,8})\b', cell_text)
                                    code = m_code.group(1) if m_code else 'Free'
                                    title = lines[-1] if len(lines) > 1 else code
                                    if code != 'Free' and title != code:
                                        course_mapping[code] = title
                                    schedule[short_day].append(code)
            else:
                # Old studzone2 portal
                name_el = soup.find('span', {'id': 'lbluser'})
                if name_el:
                    student_name = name_el.text.strip()

                desc_table = soup.find('table', {'id': 'TbCourDesc'})
                if desc_table:
                    for row in desc_table.find_all('tr')[1:]:
                        cols = [col.text.strip() for col in row.find_all('td')]
                        if len(cols) >= 2:
                            course_mapping[cols[0]] = cols[1]

                dt_table = soup.find('table', {'id': 'DtStfTimtab'})
                if dt_table:
                    days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
                    rows = dt_table.find_all('tr')
                    start_idx = 0
                    for i, row in enumerate(rows):
                        row_text = row.get_text(strip=True).lower()
                        if 'mon' in row_text or i > 1:
                            start_idx = i
                            break
                    for day_idx, day in enumerate(days):
                        row_idx = start_idx + day_idx
                        if row_idx < len(rows):
                            row = rows[row_idx]
                            cols = row.find_all('td')
                            for col in cols[1:]:
                                content = col.get_text(strip=True)
                                if content and content.lower() != 'free':
                                    matched_code = None
                                    for course_code in course_mapping.keys():
                                        if course_code.lower() in content.lower():
                                            matched_code = course_code
                                            break
                                    if matched_code:
                                        schedule[day].append(matched_code)
                                    else:
                                        codes = re.findall(r'[A-Z0-9]+', content.upper())
                                        code = next((c for c in codes if len(c) >= 5 and any(ch.isdigit() for ch in c)), codes[0] if codes else 'Unknown')
                                        schedule[day].append(code)
                                else:
                                    schedule[day].append('Free')
        except Exception as e:
            logger.error(f"Timetable & schedule parse error: {e}")

        return course_mapping, schedule, student_name

    def get_timetable(self):
        mapping, _, _ = self.get_timetable_and_schedule()
        return mapping, "Success"

    def get_weekly_schedule(self):
        _, schedule, _ = self.get_timetable_and_schedule()
        return schedule, "Success"

    def get_student_name(self):
        _, _, name = self.get_timetable_and_schedule()
        return name



class EcampusIASScraper:
    """
    Web scraper for PSG Institute of Advanced Studies (PSG IAS) eCampus portal.

    Portal   : https://ecampus.psgias.ac.in/
    College  : PSG Institute of Advanced Studies, Coimbatore
    Roll No  : 7 chars with letters not in PSG Tech list (e.g. 25IR007)
    Min Att. : 75%
    Features : Attendance, Course name mapping, Weekly Schedule
               NOTE: CA Marks / GPA / CGPA are NOT available on this portal.

    Login flow:
      1. GET /Login/UserLogin → grab __RequestVerificationToken (CSRF)
      2. POST /Login/UserLoginTest with email + password + token
    """
    ECAMPUS_URL = "https://ecampus.psgias.ac.in/"
    
    def __init__(self, username, password):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.username = username
        self.authenticated = self._login(username, password)
    
    def _login(self, username, password):
        """Authenticate with PSG IAS eCampus"""
        try:
            login_url = f"{self.ECAMPUS_URL}Login/UserLogin"
            login_page = self.session.get(login_url, timeout=7)
            soup = BeautifulSoup(login_page.text, 'html.parser')
            
            # Get CSRF token
            csrf_token = soup.find('input', {'name': '__RequestVerificationToken'})
            if not csrf_token:
                logger.error("PSG IAS: CSRF token not found")
                return False
            
            login_data = {
                '__RequestVerificationToken': csrf_token.get('value', ''),
                'email': username,
                'password': password
            }
            
            response = self.session.post(f"{self.ECAMPUS_URL}Login/UserLoginTest", 
                                        data=login_data, timeout=7, allow_redirects=True)
            
            # Check if login was successful
            if 'Invalid' in response.text or 'Login' in response.url:
                logger.error("PSG IAS: Invalid credentials")
                return False
            
            return True
        except Exception as e:
            logger.error(f"PSG IAS Login error: {str(e)}")
            return False
    
    def get_attendance(self):
        """Fetch attendance data from PSG IAS eCampus"""
        if not self.authenticated:
            return None, None, "Authentication failed"
        
        try:
            attendance_url = f"{self.ECAMPUS_URL}AttpercCons/AttPercCons"
            response = self.session.get(attendance_url, timeout=7)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for table with class "table card-table table-vcenter text-wrap datatable"
            table = soup.find('table', {'class': lambda x: x and 'table' in x and 'card-table' in x})
            if not table:
                return None, "No data", "Attendance data not available"
            
            attendance_data = []
            last_update = None
            rows = table.find_all('tr')[1:]  # Skip header row
            
            for row in rows:
                cols = [col.text.strip() for col in row.find_all('td')]
                if len(cols) >= 9:
                    try:
                        # PSG IAS table structure:
                        # 0: Course Code
                        # 1: Course Name
                        # 2: Total Hours
                        # 3: Absent Hours
                        # 4: Leave Hours
                        # 5: Medical Hours
                        # 6: Total Absent
                        # 7: Total Present
                        # 8: % of Attendance
                        # 9: % with Exemption
                        # 10: % with Medical
                        
                        # Fix for potential whitespace issues
                        course_code = cols[0].strip()
                        course_name = cols[1].strip()
                        
                        total_hours = int(cols[2]) if cols[2] and cols[2].isdigit() else 0
                        total_present = int(cols[7]) if len(cols) > 7 and cols[7].isdigit() else 0
                        
                        # Handle percentage possibly being empty or weird
                        perc_str = cols[8].replace('%','').strip() if len(cols) > 8 else '0'
                        try:
                            percentage = float(perc_str)
                        except:
                            percentage = 0.0
                        
                        attendance_data.append({
                            'code': course_code,
                            'name': course_name,
                            'total': total_hours,
                            'attended': total_present,
                            'percentage': percentage
                        })
                    except (ValueError, IndexError) as e:
                        logger.error(f"PSG IAS: Error parsing row: {e}")
                        continue
            
            # Extract "Valid Until" date from card header
            # Looking for: "Valid Until : 04-02-2026"
            card_header = soup.find('div', {'class': 'card-header'})
            if card_header:
                h3_tags = card_header.find_all('h3')
                for h3 in h3_tags:
                    text = h3.text.strip()
                    if 'Valid Until' in text:
                        # Extract date after "Valid Until :"
                        date_parts = text.split(':')
                        if len(date_parts) > 1:
                            date_str = date_parts[1].strip()
                            try:
                                from datetime import datetime as dt
                                date_obj = dt.strptime(date_str, '%d-%m-%Y')
                                last_update = date_obj.strftime('%b %d, %Y')
                            except:
                                last_update = date_str
                        break
            
            if not last_update:
                last_update = "No data"
            
            return attendance_data, last_update, "Success"
        except Exception as e:
            logger.error(f"PSG IAS Attendance fetch error: {str(e)}")
            return None, "No data", f"Error: {str(e)}"
    
    def get_timetable(self):
        """Fetch course codes mapping for PSG IAS"""
        if not self.authenticated:
            return {}, "Authentication failed"
        
        try:
            # Build mapping from attendance data since PSG IAS shows both code and name
            attendance_data, _, _ = self.get_attendance()
            course_mapping = {}
            
            if attendance_data:
                for subject in attendance_data:
                    course_mapping[subject['code']] = subject['name']
            
            return course_mapping, "Success"
        except Exception as e:
            logger.error(f"PSG IAS Timetable fetch error: {str(e)}")
            return {}, f"Error: {str(e)}"
    
    def get_weekly_schedule(self):
        """Fetch weekly timetable for PSG IAS"""
        if not self.authenticated:
            return {}, "Authentication failed"
        
        try:
            tables_to_check = []

            # 1. Fetch Home
            try:
                home_url = f"{self.ECAMPUS_URL}Home/Home"
                response = self.session.get(home_url, timeout=15)
                soup = BeautifulSoup(response.text, 'html.parser')
                tables = soup.find_all('table')
                for t in tables:
                    text = t.get_text().lower()
                    if 'mon' in text and 'fri' in text:
                        tables_to_check.append(t)
            except Exception as e:
                logger.error(f"Home fetch error: {e}")

            # 2. Fetch TimeTableStud
            try:
                tt_url = f"{self.ECAMPUS_URL}TimeTableStud/TimeTableStud"
                response = self.session.get(tt_url, timeout=15)
                soup = BeautifulSoup(response.text, 'html.parser')
                t = soup.find('table', {'class': 'table'})
                if t:
                    tables_to_check.append(t)
            except Exception as e:
                logger.error(f"TimeTableStud fetch error: {e}")

            best_schedule = {day: [] for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']}
            best_count = 0

            # Logic to parse table
            start_days = ['mon', 'tue', 'wed', 'thu', 'fri']
            days_map = {'mon': 'Mon', 'tue': 'Tue', 'wed': 'Wed', 'thu': 'Thu', 'fri': 'Fri',
                        'monday': 'Mon', 'tuesday': 'Tue', 'wednesday': 'Wed', 
                        'thursday': 'Thu', 'friday': 'Fri'}

            for target_table in tables_to_check:
                current_schedule = {day: [] for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']}
                current_count = 0
                
                rows = target_table.find_all('tr')
                day_rows = []
                
                for row in rows:
                    row_text = row.get_text(" ", strip=True).lower()
                    found_day = None
                    for d in start_days:
                        if d in row_text:
                            if d + 'day' in row_text:
                                found_day = days_map.get(d + 'day')
                            else:
                                found_day = days_map.get(d)
                            break
                    
                    if found_day:
                        # PSG IAS uses <th> for slots sometimes, so check both
                        if len(row.find_all(['td', 'th'])) > 1:
                            day_rows.append((found_day, row))

                for day_name, row in day_rows:
                    cols = row.find_all(['td', 'th'])
                    
                    valid_cols = []
                    for col_idx, col in enumerate(cols):
                        txt = col.get_text(strip=True).lower()
                        # Skip if it's the day name itself or "Day Order"
                        if day_name.lower() in txt or txt in ['day', 'order', 'day order']:
                            continue
                        # Empty cell at start? usually index col
                        if not txt and col_idx == 0: continue
                        valid_cols.append(col)

                    # Now process valid columns
                    for col in valid_cols:
                        course_code = col.get_text(strip=True)
                        if not course_code or course_code == '-' or course_code == '&nbsp;' or course_code.lower() == 'fast track':
                            current_schedule[day_name].append('Free')
                        else:
                            current_schedule[day_name].append(course_code)
                            current_count += 1
                
                # If this table has more classes, use it
                if current_count > best_count:
                    best_count = current_count
                    best_schedule = current_schedule
            
            return best_schedule, "Success"
            
        except Exception as e:
            logger.error(f"PSG IAS Weekly schedule fetch error: {str(e)}")
            return {day: [] for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']}, f"Error: {str(e)}"
    
    def get_student_name(self):
        """Get student name from PSG IAS portal"""
        if not self.authenticated:
            return "Student"
        
        try:
            home_url = f"{self.ECAMPUS_URL}Home/Home"
            response = self.session.get(home_url, timeout=7)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Look for student name in the navbar/header
            # Based on the HTML, it's in a div with class "d-none d-xl-block ps-2"
            name_element = soup.find('div', {'class': 'd-none d-xl-block ps-2'})
            if name_element:
                # Get the first div inside
                name_div = name_element.find('div')
                if name_div:
                    return name_div.text.strip()
            
            return "Student"
        except Exception as e:
            logger.error(f"PSG IAS get_student_name error: {str(e)}")
            return "Student"



class EcampusCEGScraper:
    """
    Ultra-Fast Scraper for College of Engineering, Guindy (Anna University - CEG/ACT/SAP)
    Portal: https://www.auegov.ac.in/
    Login: https://www.auegov.ac.in/Login/UserLogin
    Attendance: https://www.auegov.ac.in/Students_Attendance
    Min Att. : 75% (as per Anna University regulations)
    Roll format: Exactly 10 digits (e.g. 2023103001)
    """
    ECAMPUS_URL = "https://www.auegov.ac.in/"
    MIN_ATTENDANCE = 75.0

    def __init__(self, username, password):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-US,en;q=0.9',
            'X-Requested-With': 'XMLHttpRequest',
            'Referer': 'https://www.auegov.ac.in/Login/UserLogin',
        })
        self.username = username
        self.authenticated = self._login(username, password)

    def _login(self, username, password):
        """Authenticate with CeGov portal using AJAX login verification flow"""
        try:
            # 1. GET UserLogin to fetch cookies
            login_url = f"{self.ECAMPUS_URL}Login/UserLogin"
            self.session.get(login_url, timeout=7)

            # 2. POST to LoginVerification
            verification_url = f"{self.ECAMPUS_URL}Login/LoginVerification"
            login_data = {
                'inRegNo': username,
                'inPassword': password
            }
            
            response = self.session.post(verification_url, data=login_data, timeout=7)
            res_data = response.json()
            logger.info(f"CEG LoginVerification Response: {res_data}")

            # status 1 = Success
            if res_data.get('status') != 1:
                logger.error(f"CEG CeGov login fail: {res_data.get('errorMsg', 'Unknown error')}")
                return False

            # 3. Finalize session variables using SetUserSessionData
            session_data_url = f"{self.ECAMPUS_URL}Login/SetUserSessionData"
            session_payload = {
                'ipAddress': '127.0.0.1',
                'loginActivity': 'User Logged In'
            }
            self.session.post(session_data_url, data=session_payload, timeout=7)
            
            return True
        except Exception as e:
            logger.error(f"CEG CeGov Login error: {str(e)}")
            return False

    def get_attendance(self):
        """Fetch attendance data via JSON endpoints directly"""
        if not self.authenticated:
            return None, None, "Authentication failed"

        try:
            headers = {
                'Referer': f"{self.ECAMPUS_URL}Students_Attendance"
            }
            
            # Fetch the courses for current semester
            courses_url = f"{self.ECAMPUS_URL}Student/Students_Attendance_Detail/fetchCourseCodeForCurrSemester"
            courses_resp = self.session.post(courses_url, headers=headers, timeout=7)
            courses_data = courses_resp.json()
            
            course_details = courses_data.get('courseDetail', [])
            if not course_details:
                return None, "No data", "No attendance records found for this semester"

            attendance_data = []
            
            for item in course_details:
                course_code = item.get('ASE_COURSE_CODE')
                staff_id = item.get('ASE_STAFFID')
                session_id = item.get('ASE_SESSIONID')
                mark_id = item.get('ASE_MARKID')
                
                # Fetch class details (held & absent)
                detail_url = f"{self.ECAMPUS_URL}Student/Students_Attendance_Detail/fetchSelectedCourseAttendanceInfo"
                payload = {
                    'course_code': course_code,
                    'staff_id': staff_id,
                    'session_id': session_id,
                    'mark_id': mark_id
                }
                detail_resp = self.session.post(detail_url, data=payload, headers=headers, timeout=7)
                detail_data = detail_resp.json()
                
                course_name = detail_data.get('courseTitle', course_code)
                held = detail_data.get('courseHeld', []) or []
                absent = detail_data.get('absenceDetail', []) or []
                
                total = len(held)
                attended = total - len(absent)
                percentage = (attended / total * 100) if total > 0 else 0.0
                
                attendance_data.append({
                    'code': course_code,
                    'name': course_name,
                    'total': total,
                    'attended': attended,
                    'percentage': round(percentage, 2),
                })

            last_update = datetime.now().strftime("%d-%b-%Y %I:%M %p")
            return attendance_data, last_update, "Success"
        except Exception as e:
            logger.error(f"CEG Attendance fetch error: {str(e)}")
            return None, "No data", f"Error: {str(e)}"

    def get_timetable(self):
        """Build course code→name mapping from attendance data"""
        if not self.authenticated:
            return {}, "Authentication failed"
        try:
            attendance_data, _, _ = self.get_attendance()
            course_mapping = {}
            if attendance_data:
                for subject in attendance_data:
                    course_mapping[subject['code']] = subject['name']
            return course_mapping, "Success"
        except Exception as e:
            logger.error(f"CEG Timetable fetch error: {str(e)}")
            return {}, f"Error: {str(e)}"

    def get_weekly_schedule(self):
        """CEG portal does not expose a weekly timetable in a parseable form yet.
        Return an empty schedule so the app gracefully falls back.
        """
        return {day: [] for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']}, "Success"

    def get_student_name(self):
        """Get student name from CeGov portal profile page"""
        if not self.authenticated:
            return "Student"
        try:
            home_url = f"{self.ECAMPUS_URL}Home/Index"
            response = self.session.get(home_url, timeout=7)
            soup = BeautifulSoup(response.text, 'html.parser')
            # Try common name placements in CeGov portal
            for selector in [
                {'class': lambda x: x and 'student-name' in x},
                {'id': 'lblStudentName'},
                {'id': 'lbluser'},
            ]:
                el = soup.find(attrs=selector) if isinstance(selector, dict) else soup.select_one(selector)
                if el and el.text.strip():
                    return el.text.strip()
            return "Student"
        except Exception as e:
            logger.error(f"CEG Student name fetch error: {str(e)}")
            return "Student"


@app.route('/manifest.json')
def serve_manifest():
    return app.send_static_file('manifest.json')

@app.route('/favicon.ico')
def serve_favicon():
    return app.send_static_file('favicon.ico')

@app.route('/sw.js')
def serve_sw():
    return app.send_static_file('sw.js')

@app.route('/robots.txt')
def serve_robots():
    return app.send_static_file('robots.txt')

@app.route('/sitemap.xml')
def serve_sitemap():
    return app.send_static_file('sitemap.xml')

@app.route('/llms.txt')
def serve_llms():
    return app.send_static_file('llms.txt')

@app.route('/')
def index():
    """Serve main application"""
    return render_template('index.html')


@app.route('/calendar')
@app.route('/calendar.html')
def calendar_page():
    """Serve standalone Google Calendar style academic calendar & event planner (public, no auth required)"""
    return render_template('calendar.html')


@app.route('/api/login', methods=['POST'])
def api_login():
    """API endpoint for login - Supports both PSG Tech and PSG IAS"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip().upper()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Credentials required'})
        
        # Detect college from roll number
        college = detect_college(username)
        
        if not college:
            return jsonify({
                'success': False, 
                'error': 'Invalid roll number format. Use 6 characters for PSG Tech or 7 for PSG IAS.'
            })
        
        # Select appropriate scraper based on college
        if college == 'PSGTECH':
            scraper = EcampusScraper(username, password)
        elif college == 'PSGIAS':
            scraper = EcampusIASScraper(username, password)
        elif college == 'CEG':
            scraper = EcampusCEGScraper(username, password)
        else:
            return jsonify({'success': False, 'error': 'Unsupported college'})
        
        if not scraper.authenticated:
            return jsonify({'success': False, 'error': 'Invalid credentials'})
            
        import hashlib
        import json
        
        # Cache file path based on credentials
        cred_hash = hashlib.sha256(f"{username}:{password}:{college}".encode()).hexdigest()
        cache_path = f"/tmp/bunker_cache_{cred_hash}.json"
        
        # Always fetch attendance to verify if new data has been updated from college side
        attendance_data, last_update, att_msg = scraper.get_attendance()
        
        if college == 'CEG':
            if not attendance_data:
                return jsonify({
                    'success': False,
                    'error': 'Unable to fetch attendance data. Please try again.'
                })
        
        use_cache = False
        cached_response = None
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cached_data = json.load(f)
                    
                # For CEG, last_update is current time, so we must compare the actual data
                # For others, we can use last_update if it exists
                if college == 'CEG' or college == 'PSGIAS':
                    # Compare actual attendance data
                    if json.dumps(cached_data.get('raw_attendance', []), sort_keys=True) == json.dumps(attendance_data, sort_keys=True):
                        use_cache = True
                else:
                    # For PSG Tech, last_update is reliable and data might be huge
                    if cached_data.get('last_update') == last_update and last_update != "No data":
                        use_cache = True
                        
                if use_cache:
                    cached_response = cached_data.get('response')
                    # Update the response's last_update for CEG since it's dynamic
                    if college == 'CEG' and cached_response:
                        cached_response['last_update'] = last_update
            except Exception as e:
                logger.error(f"Cache read error: {e}")
        
        if use_cache and cached_response:
            return jsonify(cached_response)
            
        # If cache miss or data updated, fetch the rest
        if hasattr(scraper, 'get_timetable_and_schedule'):
            course_mapping, weekly_schedule, student_name = scraper.get_timetable_and_schedule()
        else:
            course_mapping, _ = scraper.get_timetable()
            weekly_schedule, _ = scraper.get_weekly_schedule()
            student_name = scraper.get_student_name()
        
        # For CEG: success is based on having attendance data (timetable is optional/synthetic)
        # For PSG: must have timetable+course_mapping
        if college == 'CEG':
            # Build a synthetic timetable from the course codes so Smart Tracker works.
            # Since CeGov doesn't expose a day-wise schedule, we spread all courses across weekdays.
            codes = [s['code'] for s in attendance_data]
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
            synthetic_tt = {}
            for i, day in enumerate(days):
                synthetic_tt[day] = [codes[j] for j in range(len(codes)) if j % len(days) == i]
            weekly_schedule = synthetic_tt
        else:
            if not weekly_schedule or not course_mapping:
                return jsonify({
                    'success': False,
                    'error': 'Unable to fetch timetable data. Please try again.'
                })
        
        # Process subjects if available
        processed_subjects = []
        if attendance_data:
            for subject in attendance_data:
                processed_subjects.append({
                    'code': subject['code'],
                    'name': course_mapping.get(subject['code'], subject['name']),
                    'total': subject['total'],
                    'attended': subject['attended'],
                    'exemption': subject.get('exemption', 0),
                    'pct_normal': subject.get('percentage', 0),
                    'pct_exemp': subject.get('pct_exemp', 0),
                    'pct_medical': subject.get('pct_medical', 0),
                })

        # Track previous attendance per roll number so it can be restored when college updates/blocks attendance
        roll_hash = hashlib.sha256(f"{username.strip().upper()}:{college}".encode()).hexdigest()
        prev_cache_path = f"/tmp/bunker_prev_{roll_hash}.json"

        # Prepare response data
        response_data = {
            'success': True,
            'subjects': processed_subjects,
            'timetable': weekly_schedule,
            'course_mapping': course_mapping,
            'last_update': last_update or "No data",
            'college': college,
            'has_calendar': college == 'PSGTECH'  # Only PSG Tech has calendar support
        }

        # If current subjects are present, save to roll-specific prev cache
        if processed_subjects:
            try:
                with open(prev_cache_path, 'w') as pf:
                    json.dump({
                        'subjects': processed_subjects,
                        'last_update': last_update or "No data",
                        'timetable': weekly_schedule,
                        'course_mapping': course_mapping,
                        'student_name': student_name if student_name and student_name != "Student" else None
                    }, pf)
            except Exception as e:
                logger.error(f"Prev cache write error: {e}")
        else:
            # When attendance is currently stopped or updating, retrieve previously cached attendance
            prev_subs = None
            prev_update = None
            prev_name = None
            if os.path.exists(prev_cache_path):
                try:
                    with open(prev_cache_path, 'r') as pf:
                        p_data = json.load(pf)
                        if p_data.get('subjects'):
                            prev_subs = p_data.get('subjects')
                            prev_update = p_data.get('last_update')
                            prev_name = p_data.get('student_name')
                except Exception:
                    pass
            if not prev_subs and os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r') as f:
                        old_cache = json.load(f)
                        old_subs = old_cache.get('response', {}).get('subjects')
                        if old_subs:
                            prev_subs = old_subs
                            prev_update = old_cache.get('last_update')
                            prev_name = old_cache.get('response', {}).get('student_name')
                except Exception:
                    pass
            if prev_subs:
                response_data['previous_subjects'] = prev_subs
                response_data['previous_last_update'] = prev_update or "Previous Update"
                if prev_name:
                    student_name = prev_name
        
        # Add student name if available
        if student_name and student_name != "Student":
            response_data['student_name'] = student_name
        elif college in ('PSGIAS', 'CEG'):
            s_name = scraper.get_student_name()
            if s_name and s_name != "Student":
                response_data['student_name'] = s_name

        # For CEG, expose minimum attendance so frontend can show correct threshold
        if college == 'CEG':
            response_data['min_attendance'] = EcampusCEGScraper.MIN_ATTENDANCE
            
        # Save to cache (do not wipe previous valid attendance data if current is empty)
        try:
            should_save = True
            if not attendance_data and os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r') as f:
                        existing = json.load(f)
                    if existing.get('raw_attendance'):
                        # Keep existing cache with attendance data
                        should_save = False
                except Exception:
                    pass
            if should_save:
                with open(cache_path, 'w') as f:
                    json.dump({
                        'last_update': last_update,
                        'raw_attendance': attendance_data,
                        'response': response_data
                    }, f)
        except Exception as e:
            logger.error(f"Cache write error: {e}")

        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Login API error: {str(e)}")
        return jsonify({'success': False, 'error': f"Server error: {str(e)}"})


@app.route('/api/previous-attendance', methods=['POST'])
def api_previous_attendance():
    """Retrieve previously cached attendance data when college attendance is updating or stopped"""
    try:
        data = request.get_json() or {}
        username = data.get('username')
        password = data.get('password')
        college = data.get('college') or detect_college(username)
        
        if not username:
            return jsonify({'success': False, 'error': 'Roll number required'})
        
        import hashlib
        import json
        
        roll_hash = hashlib.sha256(f"{username.strip().upper()}:{college}".encode()).hexdigest()
        prev_cache_path = f"/tmp/bunker_prev_{roll_hash}.json"
        
        if os.path.exists(prev_cache_path):
            try:
                with open(prev_cache_path, 'r') as pf:
                    cached_data = json.load(pf)
                    if cached_data.get('subjects'):
                        return jsonify({
                            'success': True,
                            'subjects': cached_data['subjects'],
                            'last_update': cached_data.get('last_update', 'Previous Update'),
                            'timetable': cached_data.get('timetable'),
                            'course_mapping': cached_data.get('course_mapping')
                        })
            except Exception as e:
                logger.error(f"Error reading prev cache: {e}")
        
        if password:
            cred_hash = hashlib.sha256(f"{username}:{password}:{college}".encode()).hexdigest()
            cache_path = f"/tmp/bunker_cache_{cred_hash}.json"
            if os.path.exists(cache_path):
                try:
                    with open(cache_path, 'r') as f:
                        cached_info = json.load(f)
                        subs = cached_info.get('response', {}).get('subjects')
                        if subs:
                            return jsonify({
                                'success': True,
                                'subjects': subs,
                                'last_update': cached_info.get('last_update', 'Previous Update'),
                                'timetable': cached_info.get('response', {}).get('timetable'),
                                'course_mapping': cached_info.get('response', {}).get('course_mapping')
                            })
                except Exception as e:
                    logger.error(f"Error reading cred cache: {e}")
                    
        return jsonify({'success': False, 'error': 'No previous attendance data found on server'})
    except Exception as e:
        logger.error(f"Previous attendance API error: {e}")
        return jsonify({'success': False, 'error': str(e)})


ALL_CALENDARS_CACHE = {
    'data': None,
    'timestamp': 0
}

@app.route('/api/all-calendars')
def api_all_calendars():
    """Returns calendar planners for all departments with caching and fallback"""
    import time
    now = time.time()
    
    # 1 hour server cache (works for warm containers)
    if ALL_CALENDARS_CACHE['data'] and (now - ALL_CALENDARS_CACHE['timestamp'] < 3600):
        resp = jsonify(ALL_CALENDARS_CACHE['data'])
        resp.headers['Cache-Control'] = 'public, s-maxage=3600, stale-while-revalidate=7200'
        return resp
    
    # Baseline from disk cache
    cached_data = {}
    fallback_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'all_calendars_cache.json')
    if os.path.exists(fallback_path):
        try:
            with open(fallback_path, 'r', encoding='utf-8') as f:
                cached_data = json.load(f)
        except Exception as e:
            logger.warning(f"Failed to read disk cache: {e}")
    
    departments = [
        {"id": "be_3_4", "name": "3rd & 4th Year BE / B.Tech", "planner_odd": 32, "planner_even": 40, "color": "#6366f1"},
        {"id": "be_2", "name": "2nd Year BE / B.Tech", "planner_odd": 33, "planner_even": 41, "color": "#a855f7"},
        {"id": "be_1", "name": "1st Year BE / B.Tech", "planner_odd": 39, "planner_even": 42, "color": "#ec4899"},
        {"id": "bsc_msc", "name": "B.Sc & M.Sc (All Years)", "planner_odd": 32, "planner_even": 40, "color": "#06b6d4"},
        {"id": "pg", "name": "ME / M.Tech & MCA", "planner_odd": 32, "planner_even": 40, "color": "#f59e0b"},
        {"id": "sandwich", "name": "BE Sandwich (SW)", "planner_odd": 35, "planner_even": 44, "color": "#10b981"}
    ]

    # If we have disk cache, use it and skip live fetch (fast path for Vercel 10s limit)
    if cached_data:
        result = {
            'success': True,
            'year': CONFIG['API_YEAR'],
            'planners': cached_data,
            'departments': departments
        }
        ALL_CALENDARS_CACHE['data'] = result
        ALL_CALENDARS_CACHE['timestamp'] = now
        resp = jsonify(result)
        resp.headers['Cache-Control'] = 'public, s-maxage=3600, stale-while-revalidate=7200'
        return resp

    # No cache at all — try fetching fresh planners with tight timeouts
    planners = [32, 33, 34, 35, 39, 40, 41, 42, 43, 44]
    live_data = {}
    for pid in planners:
        try:
            url = f"https://academicschedule.psgtech.ac.in/api/calendar/{CONFIG['API_YEAR']}/planner/{pid}"
            res = requests.get(url, timeout=2)
            if res.status_code == 200:
                live_data[str(pid)] = res.json()
        except Exception:
            pass
            
    result = {
        'success': True,
        'year': CONFIG['API_YEAR'],
        'planners': live_data if live_data else cached_data,
        'departments': departments
    }
    
    ALL_CALENDARS_CACHE['data'] = result
    ALL_CALENDARS_CACHE['timestamp'] = now
    resp = jsonify(result)
    resp.headers['Cache-Control'] = 'public, s-maxage=3600, stale-while-revalidate=7200'
    return resp


@app.route('/api/calendar/<roll>')
def api_calendar(roll):
    """Proxy calendar API to avoid CORS issues with offline fallback"""
    try:
        roll = roll.strip().upper()
        
        # Detect college to determine if calendar is available
        college = detect_college(roll)
        
        if college == 'PSGIAS':
            from datetime import datetime
            return jsonify({
                'name': 'PSG IAS Academic Year',
                'startDate': datetime.now().isoformat(),
                'lastDate': datetime.now().isoformat(),
                'calendar': {'holidays': []},
                'activities': []
            })

        if college == 'CEG':
            from datetime import datetime
            return jsonify({
                'name': 'CEG Academic Year',
                'startDate': datetime.now().isoformat(),
                'lastDate': datetime.now().isoformat(),
                'calendar': {'holidays': []},
                'activities': []
            })
            
        # PSG Tech Logic (Default)
        planner_id = get_planner_id(roll)
        
        if not planner_id:
            return jsonify({
                'error': 'Could not identify course/year from roll number',
                'rollNumber': roll
            }), 400
        
        # Fetch from academic schedule API
        calendar_url = f"https://academicschedule.psgtech.ac.in/api/calendar/{CONFIG['API_YEAR']}/planner/{planner_id}"
        
        try:
            response = requests.get(calendar_url, timeout=5)
            if response.status_code == 200:
                resp = jsonify(response.json())
                resp.headers['Cache-Control'] = 'public, s-maxage=3600, stale-while-revalidate=7200'
                return resp
        except Exception:
            pass
        
        # Fallback to local cache if network/API fails
        fallback_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'all_calendars_cache.json')
        if os.path.exists(fallback_path):
            try:
                with open(fallback_path, 'r', encoding='utf-8') as f:
                    cdata = json.load(f)
                    if str(planner_id) in cdata:
                        resp = jsonify(cdata[str(planner_id)])
                        resp.headers['Cache-Control'] = 'public, s-maxage=3600, stale-while-revalidate=7200'
                        return resp
            except Exception:
                pass
                
        return jsonify({'error': 'Failed to fetch calendar data'}), 502
        
    except Exception as e:
        logger.error(f"Calendar API error: {str(e)}")
        return jsonify({'error': 'Server error fetching calendar'}), 500


@app.route('/api/internals', methods=['POST'])
def api_internals():
    """Fetch CA internal marks from eCampus with 15-minute server caching"""
    try:
        data = request.get_json() or {}
        auth_token = data.get('auth_token', '')
        force = data.get('force', False)
        
        if not auth_token:
            return jsonify({'error': 'Auth token required'}), 401
        
        # Parse stored credentials
        try:
            import json as _json
            creds = _json.loads(auth_token)
            roll = creds.get('roll', '')
            password = creds.get('password', '')
        except:
            return jsonify({'error': 'Invalid auth token'}), 401

        import hashlib
        roll_hash = hashlib.sha256(f"{roll}:{password}:internals".encode()).hexdigest()
        cache_key = f"bunker_internals_{roll_hash}"
        if not force:
            cached = get_disk_cache(cache_key, max_age_seconds=900)
            if cached is not None:
                return jsonify(cached)

        scraper = EcampusScraper(roll, password, timeout=7, prefetch=False, force_studzone2=True)
        if not scraper.authenticated:
            return jsonify({'error': 'Authentication failed'}), 401

        scraper.ensure_studzone2_auth()

        ca_url = f"{scraper.ECAMPUS_URL}CAMarks_View.aspx"
        response = scraper.session.get(ca_url, timeout=7)
        soup = BeautifulSoup(response.text, 'html.parser')

        internals = []
        # Find all tables with IDs like 8^XXXX (the CA mark tables)
        tables = soup.find_all('table', id=lambda x: x and '^' in str(x))
        
        for table in tables:
            table_id = table.get('id', '')
            rows = table.find_all('tr')
            
            # Get header to find column count/schema
            header_cells = []
            for r in rows[:2]:
                for td in r.find_all('td'):
                    header_cells.append(td.get_text(strip=True))
            
            # Data rows start after 2 header rows
            data_rows = rows[2:] if len(rows) > 2 else []
            
            for row in data_rows:
                cols = [td.get_text(strip=True) for td in row.find_all('td')]
                if len(cols) < 3:
                    continue
                
                course_code = cols[0].strip()
                course_name = cols[1].strip()
                
                # row_data is the list of mark columns (skip code+name)
                row_data = cols[2:]
                
                # The last column is 'Total'
                total_raw = row_data[-1].strip() if row_data else ''
                total = total_raw if total_raw and total_raw != '' else 'Not Updated Yet'
                
                # Calculate converted mark based on table type
                is_lab = table_id.startswith('8^16') or table_id.startswith('8^10')
                
                def safe_float(v):
                    try:
                        return float(v.replace('*','').strip()) if v and v != '*' and v.strip() else None
                    except:
                        return None
                
                total_val = safe_float(total)
                total_converted = 'Not Updated Yet'
                target_max = 40
                
                is_zero = course_code.strip().upper() == '23U215' or 'ACTIVITY POINT' in course_name.strip().upper()
                if total_val is not None:
                    if is_zero:
                        total_converted = str(round(total_val))
                        target_max = 100
                    elif is_lab:
                        total_converted = str(round(total_val * 1.2))
                        target_max = 60
                    else:
                        total_converted = str(round(total_val * 0.8))
                        target_max = 40

                internals.append({
                    'course_code': course_code,
                    'course_name': course_name,
                    'table_id': table_id,
                    'is_lab': is_lab,
                    'row_data': row_data,
                    'total': total,
                    'total_converted': total_converted,
                    'target_max': target_max
                })

        set_disk_cache(cache_key, internals)
        return jsonify(internals)

    except Exception as e:
        logger.error(f"Internals API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500


def fetch_allsem_results(scraper, roll):
    """
    Fetch comprehensive all-semester academic records directly from PSG Tech eCampus.
    Leverages dual-endpoints on studzone2:
      1. AttWfStudCourseSelection.aspx (Complete historical transcript of ALL completed semesters)
      2. FrmEpsStudResult.aspx (Latest semester provisional exam results & points)
    """
    from concurrent.futures import ThreadPoolExecutor
    scraper.ensure_studzone2_auth()

    # Concurrently fetch both Course Selection (all past semesters) & Exam Result (latest provisional)
    r_cs, r_res = None, None
    try:
        with ThreadPoolExecutor(max_workers=2) as ex:
            f_cs = ex.submit(scraper.session.get, f"{scraper.ECAMPUS_URL}AttWfStudCourseSelection.aspx", verify=False, timeout=7)
            f_res = ex.submit(scraper.session.get, f"{scraper.ECAMPUS_URL}FrmEpsStudResult.aspx", verify=False, timeout=7)
            r_cs = f_cs.result()
            r_res = f_res.result()
    except Exception as e:
        logger.error(f"Error fetching studzone2 results concurrently: {e}")

    grades_map = {
        'S': 10, 'O': 10, 'A+': 9, 'A': 8, 'B+': 7, 'B': 6, 'C+': 6, 'C': 5,
        'D': 6, 'E': 5, 'P': 5, 'RA': 0, 'U': 0, 'W': 0, 'SA': 0, 'WD': 0,
        'Completed': None
    }

    all_subjects = []
    seen_courses = {}

    # 1. Parse all completed courses from AttWfStudCourseSelection.aspx
    if r_cs and r_cs.status_code == 200:
        soup_cs = BeautifulSoup(r_cs.text, 'html.parser')
        tbl_completed = soup_cs.find('table', {'id': 'PDGCourse'}) or soup_cs.find('table', {'id': 'TabCourse'})
        if tbl_completed:
            for row in tbl_completed.find_all('tr')[1:]:
                cols = [td.get_text(strip=True) for td in row.find_all('td')]
                if len(cols) >= 8:
                    code = cols[1].strip()
                    title = cols[2].strip()
                    cat = cols[3].strip()
                    sem = int(cols[4].strip()) if cols[4].strip().isdigit() else 1
                    opt = cols[5].strip()
                    grade = cols[6].strip()
                    credits_str = cols[7].strip() if len(cols) > 7 else '0'
                    credits = int(credits_str) if credits_str.isdigit() else 0
                    passing = cols[8].strip() if len(cols) > 8 else ''
                    
                    # ONLY courses with 0 credits are Non-CGPA
                    is_non_cgpa = (credits == 0)
                    gp = None if is_non_cgpa else grades_map.get(grade.strip().upper(), 0)
                    is_pass = grade.strip().upper() not in ('RA', 'U', 'W', 'SA', 'WD')
                    
                    subj_obj = {
                        'sem': sem,
                        'course': code,
                        'title': title,
                        'category': cat,
                        'credits': str(credits),
                        'grade': grade,
                        'grade_points': gp,
                        'is_non_cgpa': is_non_cgpa,
                        'result': 'Pass' if is_pass else 'Fail',
                        'passing': passing
                    }
                    all_subjects.append(subj_obj)
                    seen_courses[code] = subj_obj

    # 2. Parse latest provisional exam results from FrmEpsStudResult.aspx
    if r_res and r_res.status_code == 200:
        soup_res = BeautifulSoup(r_res.text, 'html.parser')
        tbl_res = soup_res.find('table', {'id': 'DgResult'}) or soup_res.find(lambda x: x.name == 'table' and (x.get('id') or '').lower() == 'dgresult')
        if tbl_res:
            cur_sem = None
            for row in tbl_res.find_all('tr')[1:]:
                cols = [td.get_text(strip=True) for td in row.find_all('td')]
                if len(cols) >= 5:
                    sem_cell = cols[0].strip()
                    if sem_cell and sem_cell.isdigit():
                        cur_sem = int(sem_cell)
                    code = cols[1].strip()
                    title = cols[2].strip()
                    credits = cols[3].strip()
                    mark_raw = cols[4].strip()
                    result = cols[5].strip() if len(cols) > 5 else ''

                    parts = mark_raw.split()
                    gp = None
                    grade = mark_raw
                    if len(parts) >= 2:
                        try:
                            gp_val = float(parts[0])
                            gp = int(gp_val) if gp_val.is_integer() else gp_val
                            grade = parts[-1]
                        except: pass
                    elif mark_raw.lower() == 'completed':
                        grade = 'Completed'

                    cr_int = int(credits) if str(credits).isdigit() else 0
                    is_non_cgpa = (cr_int == 0)

                    grade_clean = grade.strip().upper()
                    if is_non_cgpa:
                        gp = None
                    elif gp is None and grade_clean in grades_map:
                        gp = grades_map[grade_clean]

                    is_pass = (result.lower() == 'pass') if result else (grade_clean not in ('RA', 'U', 'W', 'SA', 'WD'))

                    if code in seen_courses:
                        if not seen_courses[code].get('is_non_cgpa'):
                            if gp is not None:
                                seen_courses[code]['grade_points'] = gp
                        if grade:
                            seen_courses[code]['grade'] = grade
                        if result:
                            seen_courses[code]['result'] = result
                        if title and not seen_courses[code].get('title'):
                            seen_courses[code]['title'] = title
                    else:
                        new_subj = {
                            'sem': cur_sem or 1,
                            'course': code,
                            'title': title,
                            'category': '',
                            'credits': str(cr_int),
                            'grade': grade,
                            'grade_points': gp,
                            'is_non_cgpa': is_non_cgpa,
                            'result': result or ('Pass' if is_pass else 'Fail')
                        }
                        all_subjects.append(new_subj)
                        seen_courses[code] = new_subj

    # Sort semesters ascending to compute progression
    semesters_found = sorted(list(set(c['sem'] for c in all_subjects))) if all_subjects else []
    semwise_data = []
    semwise_gpa = {}
    semwise_credits = {}

    for sem in semesters_found:
        sem_courses = [c for c in all_subjects if c['sem'] == sem]
        credit_courses = [c for c in sem_courses if not c.get('is_non_cgpa') and str(c.get('credits', '')).isdigit() and int(c.get('credits', 0)) > 0 and c.get('grade_points') is not None]
        sem_cr = sum(int(c['credits']) for c in credit_courses)
        sem_cp = sum(int(c['credits']) * c['grade_points'] for c in credit_courses)
        sem_has_ra = any(c.get('grade') in ('RA', 'U') or str(c.get('grade', '')).startswith('RA') or c.get('result', '').lower() == 'fail' for c in sem_courses)
        
        sgpa_val = round(sem_cp / sem_cr, 2) if sem_cr > 0 else 0
        sgpa_display = 'RA' if sem_has_ra else sgpa_val

        cum_courses = [c for c in all_subjects if c['sem'] <= sem and not c.get('is_non_cgpa') and str(c.get('credits', '')).isdigit() and int(c.get('credits', 0)) > 0 and c.get('grade_points') is not None]
        cum_cr = sum(int(c['credits']) for c in cum_courses)
        cum_cp = sum(int(c['credits']) * c['grade_points'] for c in cum_courses)
        cum_has_ra = any(c.get('grade') in ('RA', 'U') or str(c.get('grade', '')).startswith('RA') or c.get('result', '').lower() == 'fail' for c in all_subjects if c['sem'] <= sem)
        
        cgpa_val = round(cum_cp / cum_cr, 2) if cum_cr > 0 else 0
        cgpa_display = 'RA' if cum_has_ra else cgpa_val

        semwise_gpa[str(sem)] = sgpa_display
        semwise_credits[str(sem)] = sem_cr
        semwise_data.append({
            'sem': sem,
            'sgpa': sgpa_display,
            'sgpa_numeric': sgpa_val,
            'cgpa': cgpa_display,
            'cgpa_numeric': cgpa_val,
            'credits': sem_cr,
            'has_ra': sem_has_ra,
            'total_subjects': len(sem_courses)
        })

    latest_sem = semesters_found[-1] if semesters_found else 1
    latest_gpa = semwise_gpa.get(str(latest_sem), 0)
    overall_cgpa = semwise_data[-1]['cgpa'] if semwise_data else 0
    overall_cgpa_numeric = semwise_data[-1]['cgpa_numeric'] if semwise_data else 0
    total_earned_credits = sum(
        int(c['credits']) for c in all_subjects
        if not c.get('is_non_cgpa') and str(c.get('credits', '')).isdigit() and int(c.get('credits', 0)) > 0
        and (not c.get('result') or c.get('result', '').lower() == 'pass')
        and str(c.get('grade', '')) not in ('RA', 'U')
    )
    credit_points_total = sum(
        int(c['credits']) * c['grade_points'] for c in all_subjects
        if not c.get('is_non_cgpa') and str(c.get('credits', '')).isdigit() and int(c.get('credits', 0)) > 0 and c.get('grade_points') is not None
    )

    # Sort all_subjects descending by semester (Sem 2, then Sem 1) for natural UI reading
    all_subjects.sort(key=lambda x: (x['sem'], x['course']), reverse=True)

    return {
        'all_subjects': all_subjects,
        'semwise_data': semwise_data,
        'semwise_gpa': semwise_gpa,
        'semwise_credits': semwise_credits,
        'latest_sem': latest_sem,
        'latest_gpa': latest_gpa,
        'overall_cgpa': overall_cgpa,
        'overall_cgpa_numeric': overall_cgpa_numeric,
        'total_credits': total_earned_credits,
        'credit_points_total': credit_points_total
    }


@app.route('/api/gpa', methods=['POST'])
def api_gpa():
    """Fetch all-semester GPA, CGPA and results directly from eCampus with 30-minute caching"""
    try:
        data = request.get_json() or {}
        auth_token = data.get('auth_token', '')
        force = data.get('force', False)
        
        if not auth_token:
            return jsonify({'error': 'Auth token required'}), 401
        
        try:
            creds = json.loads(auth_token)
            roll = creds.get('roll', '')
            password = creds.get('password', '')
        except:
            return jsonify({'error': 'Invalid auth token'}), 401

        import hashlib
        roll_hash = hashlib.sha256(f"{roll}:{password}:results".encode()).hexdigest()
        cache_key = f"bunker_results_v4_{roll_hash}"

        results = None
        if not force:
            results = get_disk_cache(cache_key, max_age_seconds=1800)

        if not results:
            scraper = EcampusScraper(roll, password, timeout=7, prefetch=False, force_studzone2=True)
            if not scraper.authenticated:
                return jsonify({'error': 'Authentication failed'}), 401
            results = fetch_allsem_results(scraper, roll)
            set_disk_cache(cache_key, results)

        return jsonify({
            'gpa': results['latest_gpa'],
            'latest_sem': results['latest_sem'],
            'total_credits': results['total_credits'],
            'credit_points_total': results.get('credit_points_total', 0),
            'semwise_gpa': results['semwise_gpa'],
            'semwise_credits': results['semwise_credits'],
            'semwise_data': results['semwise_data'],
            'cgpa': results['overall_cgpa'],
            'overall_cgpa': results['overall_cgpa'],
            'overall_cgpa_numeric': results.get('overall_cgpa_numeric', 0),
            'all_subjects': results['all_subjects'],
            'table': results['all_subjects']
        })

    except Exception as e:
        logger.error(f"GPA API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/api/cgpa', methods=['POST'])
def api_cgpa():
    """Fetch CGPA and all-semester academic history directly from eCampus (Zero 3rd party dependency)"""
    try:
        data = request.get_json() or {}
        auth_token = data.get('auth_token', '')
        force = data.get('force', False)
        
        if not auth_token:
            return jsonify({'error': 'Auth token required'}), 401
        
        try:
            creds = json.loads(auth_token)
            roll = creds.get('roll', '')
            password = creds.get('password', '')
        except:
            return jsonify({'error': 'Invalid auth token'}), 401

        import hashlib
        roll_hash = hashlib.sha256(f"{roll}:{password}:results".encode()).hexdigest()
        cache_key = f"bunker_results_v4_{roll_hash}"

        results = None
        if not force:
            results = get_disk_cache(cache_key, max_age_seconds=1800)

        if not results:
            scraper = EcampusScraper(roll, password, timeout=7, prefetch=False, force_studzone2=True)
            if not scraper.authenticated:
                return jsonify({'error': 'Authentication failed'}), 401
            results = fetch_allsem_results(scraper, roll)
            set_disk_cache(cache_key, results)

        return jsonify({
            'cgpa': results['overall_cgpa'],
            'overall_cgpa': results['overall_cgpa'],
            'overall_cgpa_numeric': results.get('overall_cgpa_numeric', 0),
            'total_credits': results['total_credits'],
            'credit_points_total': results.get('credit_points_total', 0),
            'semwise_data': results['semwise_data'],
            'all_subjects': results['all_subjects'],
            'table': results['all_subjects']
        })

    except Exception as e:
        logger.error(f"CGPA API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/api/exam-timetable', methods=['POST'])
def api_exam_timetable():
    """Fetch official semester / reappearance exam timetable from studzone2 FrmEpsTimetable.aspx with 1-hour cache"""
    try:
        data = request.get_json() or {}
        auth_token = data.get('auth_token', '')
        force = data.get('force', False)
        if not auth_token:
            return jsonify({'error': 'Auth token required'}), 401
            
        try:
            creds = json.loads(auth_token)
            roll = creds.get('roll', '')
            password = creds.get('password', '')
        except:
            return jsonify({'error': 'Invalid auth token'}), 401

        import hashlib
        cache_key = f"bunker_exam_tt_{hashlib.sha256(f'{roll}:{password}'.encode()).hexdigest()}"
        if not force:
            cached = get_disk_cache(cache_key, max_age_seconds=3600)
            if cached is not None:
                return jsonify(cached)
            
        scraper = EcampusScraper(roll, password, timeout=7, prefetch=False, force_studzone2=True)
        if not scraper.authenticated:
            return jsonify({'error': 'Authentication failed'}), 401
            
        scraper.ensure_studzone2_auth()
        tt_url = f"{scraper.ECAMPUS_URL}FrmEpsTimetable.aspx"
        response = scraper.session.get(tt_url, timeout=7)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        table = soup.find('table', {'id': 'DgResult'}) or soup.find(lambda x: x.name == 'table' and (x.get('id') or '').lower() == 'dgresult')
        exams = []
        current_sem = None
        
        if table:
            for row in table.find_all('tr')[1:]:
                cols = [td.get_text(strip=True) for td in row.find_all(['td', 'th'])]
                if len(cols) >= 5:
                    if cols[0] and cols[0].isdigit():
                        current_sem = int(cols[0])
                    exams.append({
                        'sem': current_sem or 1,
                        'course': cols[1].strip(),
                        'title': cols[2].strip(),
                        'date': cols[3].strip(),
                        'slot': cols[4].strip()
                    })
        res_data = {
            'success': True,
            'exams': exams
        }
        set_disk_cache(cache_key, res_data)
        return jsonify(res_data)
    except Exception as e:
        logger.error(f"Exam Timetable API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500



@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({
        'status': 'ok',
        'message': 'Smart Bunker API is running',
        'version': '2.0',
        'config': {
            'api_year': CONFIG['API_YEAR']
        }
    })


class VercelPathFix:
    def __init__(self, app):
        self.app = app
    def __call__(self, environ, start_response):
        from urllib.parse import parse_qs
        qs = parse_qs(environ.get('QUERY_STRING', ''), keep_blank_values=True)
        
        # 1. Try to use __vercel_path from query string
        if '__vercel_path' in qs:
            path = qs['__vercel_path'][0]
            environ['PATH_INFO'] = '/' + path
            
        # 2. Fallback to HTTP_X_INVOKE_PATH if available
        elif environ.get('HTTP_X_INVOKE_PATH'):
            environ['PATH_INFO'] = environ['HTTP_X_INVOKE_PATH']
            
        return self.app(environ, start_response)

app.wsgi_app = VercelPathFix(app.wsgi_app)


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
