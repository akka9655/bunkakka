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
from datetime import datetime
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
        "BE_1": 36, "BTech_1": 36,
        "BE_2": 33, "BTech_2": 33,
        "BE_3": 32, "BTech_3": 32,
        "BE_4": 32, "BTech_4": 32,
        "BE_5": 35,
        
        # BSc Programs (ALL YEARS - same calendar)
        "BSc_1": 32, "BSc_2": 32, "BSc_3": 32,
        
        # MSc Programs (ALL YEARS - same calendar)
        "MSc_1": 32, "MSc_2": 32,
        
        # ME/MTech Programs
        "ME_1": 36, "MTech_1": 36,
        "ME_2": 32, "MTech_2": 32,
        
        # MCA Program
        "MCA_1": 36, "MCA_2": 36,
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
    """Check if the student follows the Absolute Grading System (admitted 2025-26 onwards)"""
    if not roll_number:
        return False
    roll_number = roll_number.strip().upper()
    try:
        admission_year = int('20' + roll_number[:2])
        return admission_year >= 2025
    except:
        return False


class EcampusScraper:
    """
    Web scraper for PSG College of Technology (PSG Tech) eCampus portal.

    Portal   : https://ecampus.psgtech.ac.in/studzone2/
    College  : PSG College of Technology, Coimbatore
    Roll No  : 6-7 alphanumeric characters (e.g. 22CSA01, 22U315)
    Min Att. : 75% to write exams; Bunker uses 80% as safe planning threshold
    Features : Attendance, Timetable, Weekly Schedule, CA Marks, GPA, CGPA

    Login flow:
      1. GET /studzone2/ → grab ViewState + EventValidation tokens
      2. POST /studzone2/ with rdolst=S (student mode) + credentials
    """
    ECAMPUS_URL = "https://ecampus.psgtech.ac.in/studzone2/"
    
    def __init__(self, username, password):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.username = username
        self.authenticated = self._login(username, password)
    
    def _login(self, username, password):
        """Authenticate with eCampus"""
        try:
            login_page = self.session.get(self.ECAMPUS_URL, timeout=30)
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
                'txtusercheck': username,
                'txtpwdcheck': password,
                'abcd3': 'Login'
            }
            
            response = self.session.post(login_page.url, data=login_data, timeout=30)
            
            if 'Invalid' in response.text or response.status_code != 200:
                return False
            
            return True
        except Exception as e:
            logger.error(f"Login error: {str(e)}")
            return False
    
    def get_attendance(self):
        """Fetch attendance data from eCampus"""
        if not self.authenticated:
            return None, None, "Authentication failed"
        
        try:
            attendance_url = f"{self.ECAMPUS_URL}AttWfPercView.aspx"
            response = self.session.get(attendance_url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            table = soup.find('table', {'class': 'cssbody'})
            if not table:
                return None, "No data", "Attendance data not available"
            
            attendance_data = []
            last_update = None
            rows = table.find_all('tr')[1:]  # Skip header row
            
            for row in rows:
                cols = [col.text.strip() for col in row.find_all('td')]
                if len(cols) >= 10:
                    try:
                        # Table columns:
                        # 0: COURSE CODE
                        # 1: TOTAL HOURS
                        # 2: EXEMPTION HOURS
                        # 3: TOTAL ABSENT
                        # 4: TOTAL PRESENT
                        # 5: PERCENTAGE OF ATTENDANCE (normal)
                        # 6: PERCENTAGE WITH EXEMP
                        # 7: PERCENTAGE WITH EXEMP MED
                        # 8: ATTENDANCE PERCENTAGE FROM
                        # 9: ATTENDANCE PERCENTAGE TO

                        def safe_int(v):
                            try: return int(v)
                            except: return 0
                        
                        def safe_float(v):
                            try: return float(v.replace('%','').strip())
                            except: return 0.0

                        total = safe_int(cols[1])
                        exemption = safe_int(cols[2])
                        attended = safe_int(cols[4])  # TOTAL PRESENT

                        attendance_data.append({
                            'code': cols[0],
                            'name': cols[0],
                            'total': total,
                            'attended': attended,
                            'exemption': exemption,
                            'percentage': safe_float(cols[5]),       # normal
                            'pct_exemp': safe_float(cols[6]),        # with exemption
                            'pct_medical': safe_float(cols[7]),      # with medical
                        })
                        
                        # Extract last update date from "ATTENDANCE PERCENTAGE TO" column (index 9)
                        if not last_update and cols[9]:
                            date_str = cols[9].strip()
                            try:
                                from datetime import datetime as dt
                                date_obj = dt.strptime(date_str, '%d-%m-%Y')
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
    
    def get_timetable(self):
        """Fetch course codes mapping"""
        if not self.authenticated:
            return {}, "Authentication failed"
        
        try:
            timetable_url = f"{self.ECAMPUS_URL}AttWfStudTimtab.aspx"
            response = self.session.get(timetable_url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            table = soup.find('table', {'id': 'TbCourDesc'})
            if not table:
                return {}, "Timetable not available"
            
            course_mapping = {}
            rows = table.find_all('tr')[1:]
            for row in rows:
                cols = [col.text.strip() for col in row.find_all('td')]
                if len(cols) >= 2:
                    course_mapping[cols[0]] = cols[1]
            
            return course_mapping, "Success"
        except Exception as e:
            logger.error(f"Timetable fetch error: {str(e)}")
            return {}, f"Error: {str(e)}"
    
    def get_weekly_schedule(self):
        """Fetch weekly timetable"""
        if not self.authenticated:
            return {}, "Authentication failed"
        
        try:
            import re
            timetable_url = f"{self.ECAMPUS_URL}AttWfStudTimtab.aspx"
            response = self.session.get(timetable_url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            course_mapping, _ = self.get_timetable()
            
            schedule = {}
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
            
            for day in days:
                schedule[day] = []
            
            table = soup.find('table', {'id': 'DtStfTimtab'})
            
            if table:
                rows = table.find_all('tr')
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
                                    if codes:
                                        course_code = next((c for c in codes if len(c) >= 5 and any(ch.isdigit() for ch in c)), codes[0] if codes else 'Unknown')
                                        schedule[day].append(course_code)
                                    else:
                                        schedule[day].append('Free')
                            else:
                                schedule[day].append('Free')
            
            return schedule, "Success"
        except Exception as e:
            logger.error(f"Weekly schedule fetch error: {str(e)}")
            return {day: [] for day in ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']}, f"Error: {str(e)}"
    
    def get_student_name(self):
        """Get student name"""
        if not self.authenticated:
            return "Student"
        
        try:
            timetable_url = f"{self.ECAMPUS_URL}AttWfStudTimtab.aspx"
            response = self.session.get(timetable_url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            name_element = soup.find('span', {'id': 'lbluser'})
            return name_element.text.strip() if name_element else "Student"
        except Exception as e:
            logger.error(f"Student name fetch error: {str(e)}")
            return "Student"


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
            login_page = self.session.get(login_url, timeout=30)
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
                                        data=login_data, timeout=30, allow_redirects=True)
            
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
            response = self.session.get(attendance_url, timeout=30)
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
            response = self.session.get(home_url, timeout=30)
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
            logger.error(f"PSG IAS Student name fetch error: {str(e)}")
            return "Student"



class EcampusCEGScraper:
    """
    Web scraper for Anna University CeGov portal — covers CEG and all constituent colleges.

    Portal   : https://www.auegov.ac.in/
    College  : College of Engineering Guindy (CEG) & other Anna University constituent colleges
    Roll No  : Exactly 10 numeric digits, e.g. 2023103001
               Format: YYYY + dept code digits + sequence
    Min Att. : 75% (as per Anna University regulations)
    Features : Attendance, Course name mapping
               NOTE: CA Marks / GPA / CGPA are NOT available on this portal.
               NOTE: Weekly timetable scraping not yet implemented (returns empty).

    Login flow:
      1. GET /Login/UserLogin → Establish session cookies
      2. POST /Login/LoginVerification (AJAX) with inRegNo + inPassword
      3. POST /Login/SetUserSessionData (AJAX) to finalize session variables
    """
    ECAMPUS_URL = "https://www.auegov.ac.in/"
    MIN_ATTENDANCE = 75

    def __init__(self, username, password):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'application/json, text/javascript, */*; q=0.01',
            'Accept-Language': 'en-IN,en;q=0.5',
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
            self.session.get(login_url, timeout=30)

            # 2. POST to LoginVerification
            verification_url = f"{self.ECAMPUS_URL}Login/LoginVerification"
            login_data = {
                'inRegNo': username,
                'inPassword': password
            }
            
            response = self.session.post(verification_url, data=login_data, timeout=30)
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
            self.session.post(session_data_url, data=session_payload, timeout=30)
            
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
            courses_resp = self.session.post(courses_url, headers=headers, timeout=30)
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
                detail_resp = self.session.post(detail_url, data=payload, headers=headers, timeout=30)
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
            response = self.session.get(home_url, timeout=20)
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

@app.route('/')
def index():
    """Serve main application"""
    return render_template('index.html')


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
        
        # Fetch all data
        attendance_data, last_update, att_msg = scraper.get_attendance()
        course_mapping, _ = scraper.get_timetable()
        weekly_schedule, _ = scraper.get_weekly_schedule()
        student_name = scraper.get_student_name()
        
        # For CEG: success is based on having attendance data (timetable is optional/synthetic)
        # For PSG: must have timetable+course_mapping
        if college == 'CEG':
            if not attendance_data:
                return jsonify({
                    'success': False,
                    'error': 'Unable to fetch attendance data. Please try again.'
                })
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
        
        # Add student name if available
        if college in ('PSGIAS', 'CEG'):
            student_name = scraper.get_student_name()
            if student_name and student_name != "Student":
                response_data['student_name'] = student_name

        # For CEG, expose minimum attendance so frontend can show correct threshold
        if college == 'CEG':
            response_data['min_attendance'] = EcampusCEGScraper.MIN_ATTENDANCE

        return jsonify(response_data)
    
    except Exception as e:
        logger.error(f"Login API error: {str(e)}")
        return jsonify({'success': False, 'error': f"Server error: {str(e)}"})


@app.route('/api/calendar/<roll>')
def api_calendar(roll):
    """Proxy calendar API to avoid CORS issues"""
    try:
        roll = roll.strip().upper()
        
        # Detect college to determine if calendar is available
        college = detect_college(roll)
        
        if college == 'PSGIAS':
            # Return empty placeholder for PSG IAS
            from datetime import datetime
            return jsonify({
                'name': 'PSG IAS Academic Year',
                'startDate': datetime.now().isoformat(),
                'lastDate': datetime.now().isoformat(),
                'calendar': {'holidays': []},
                'activities': []
            })

        if college == 'CEG':
            # CEG (Anna University) does not expose a calendar via the same API
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
        
        response = requests.get(calendar_url, timeout=10)
        
        if response.status_code != 200:
            return jsonify({'error': 'Failed to fetch calendar data'}), response.status_code
        
        return jsonify(response.json())
        
    except Exception as e:
        logger.error(f"Calendar API error: {str(e)}")
        return jsonify({'error': 'Server error fetching calendar'}), 500


@app.route('/api/internals', methods=['POST'])
def api_internals():
    """Fetch CA internal marks from eCampus"""
    try:
        data = request.get_json()
        auth_token = data.get('auth_token', '')
        
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

        scraper = EcampusScraper(roll, password)
        if not scraper.authenticated:
            return jsonify({'error': 'Authentication failed'}), 401

        ca_url = f"{scraper.ECAMPUS_URL}CAMarks_View.aspx"
        response = scraper.session.get(ca_url, timeout=30)
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

        return jsonify(internals)

    except Exception as e:
        logger.error(f"Internals API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/api/gpa', methods=['POST'])
def api_gpa():
    """Fetch GPA / semester result from eCampus"""
    try:
        data = request.get_json()
        auth_token = data.get('auth_token', '')
        
        if not auth_token:
            return jsonify({'error': 'Auth token required'}), 401
        
        import json as _json
        try:
            creds = _json.loads(auth_token)
            roll = creds.get('roll', '')
            password = creds.get('password', '')
        except:
            return jsonify({'error': 'Invalid auth token'}), 401

        scraper = EcampusScraper(roll, password)
        if not scraper.authenticated:
            return jsonify({'error': 'Authentication failed'}), 401

        gpa_url = f"{scraper.ECAMPUS_URL}FrmEpsStudResult.aspx"
        response = scraper.session.get(gpa_url, timeout=30)
        soup = BeautifulSoup(response.text, 'html.parser')

        result_table = soup.find('table', id='DgResult')
        courses = []
        current_sem = None

        if result_table:
            rows = result_table.find_all('tr')[1:]  # skip header
            for row in rows:
                cols = [td.get_text(strip=True) for td in row.find_all('td')]
                if len(cols) >= 5:
                    sem_cell = cols[0].strip()
                    if sem_cell and sem_cell.isdigit():
                        current_sem = int(sem_cell)
                    
                    course_code = cols[1].strip()
                    title = cols[2].strip()
                    credits = cols[3].strip()
                    mark_raw = cols[4].strip()
                    result = cols[5].strip() if len(cols) > 5 else ''

                    # Parse grade from mark string like "7    B+"
                    parts = mark_raw.split()
                    grade_points = None
                    grade = mark_raw
                    if len(parts) >= 2:
                        try:
                            gp_val = float(parts[0])
                            grade_points = int(gp_val) if gp_val.is_integer() else gp_val
                            grade = ' '.join(parts)
                        except:
                            pass
                    elif mark_raw.lower() == 'completed':
                        grade = 'Completed'

                    courses.append({
                        'sem': current_sem or 1,
                        'course': course_code,
                        'title': title,
                        'credits': credits,
                        'grade': grade,
                        'grade_points': grade_points,
                        'result': result
                    })

        # Calculate GPA for the latest semester
        if courses:
            latest_sem = max(c['sem'] for c in courses)
            latest_courses = [c for c in courses if c['sem'] == latest_sem]
            
            total_credits = 0
            total_cp = 0
            has_ra = False
            
            for c in latest_courses:
                cr = int(c['credits']) if str(c['credits']).isdigit() else 0
                if cr == 0:
                    continue
                gp = c.get('grade_points')
                if gp is None:
                    if c['grade'].startswith('RA') or c['grade'].startswith('0 '):
                        has_ra = True
                else:
                    total_credits += cr
                    total_cp += gp * cr

            gpa = 'RA' if has_ra else (round(total_cp / total_credits, 2) if total_credits > 0 else 0)
        else:
            gpa = 0
            total_credits = 0

        return jsonify({
            'gpa': gpa,
            'total_credits': total_credits,
            'table': courses
        })

    except Exception as e:
        logger.error(f"GPA API error: {str(e)}")
        return jsonify({'error': f'Server error: {str(e)}'}), 500


@app.route('/api/cgpa', methods=['POST'])
def api_cgpa():
    """Fetch CGPA from easycollege API (all semesters) and local scraping for subjects"""
    try:
        data = request.get_json()
        auth_token = data.get('auth_token', '')
        
        if not auth_token:
            return jsonify({'error': 'Auth token required'}), 401
        
        import json as _json
        try:
            creds = _json.loads(auth_token)
            roll = creds.get('roll', '')
            password = creds.get('password', '')
        except:
            return jsonify({'error': 'Invalid auth token'}), 401

        # -------------------------------------------------------------------
        # 1. Local Scraping for 'all_subjects' (Detailed current sem marks)
        # -------------------------------------------------------------------
        scraper = EcampusScraper(roll, password)
        all_subjects = []
        if scraper.authenticated:
            gpa_url = f"{scraper.ECAMPUS_URL}FrmEpsStudResult.aspx"
            response = scraper.session.get(gpa_url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')

            result_table = soup.find('table', id='DgResult')
            current_sem = None

            if is_absolute_grading(roll):
                grades_map = {
                    'S': 10, 'A+': 9, 'A': 8, 'B+': 7, 'B': 6.5, 'C+': 6, 'C': 5, 
                    'U': 0, 'RA': 0, 'SA': 0, 'WC': 0
                }
            else:
                grades_map = {
                    'O': 10, 'A+': 9, 'A': 8, 'B+': 7, 'B': 6, 'C': 5, 'RA': 0
                }

            if result_table:
                rows = result_table.find_all('tr')[1:]
                for row in rows:
                    cols = [td.get_text(strip=True) for td in row.find_all('td')]
                    if len(cols) >= 5:
                        sem_cell = cols[0].strip()
                        if sem_cell and sem_cell.isdigit():
                            current_sem = int(sem_cell)

                        course_code = cols[1].strip()
                        title = cols[2].strip()
                        credits = cols[3].strip()
                        mark_raw = cols[4].strip()

                        parts = mark_raw.split()
                        grade = None
                        grade_points_scraped = None
                        if mark_raw.lower() == 'completed':
                            grade = 'Completed'
                        elif len(parts) >= 2:
                            try:
                                gp_val = float(parts[0])
                                grade_points_scraped = int(gp_val) if gp_val.is_integer() else gp_val
                            except ValueError:
                                pass
                            
                            grade_letter = parts[-1].strip()
                            if grade_letter in grades_map:
                                grade = grade_letter
                            else:
                                grade = mark_raw
                        elif mark_raw.startswith('RA'):
                            grade = 'RA'
                        else:
                            grade = mark_raw

                        all_subjects.append({
                            'sem': current_sem or 1,
                            'course': course_code,
                            'title': title,
                            'credits': credits,
                            'grade': grade,
                            'grade_points': grade_points_scraped
                        })
        
        # -------------------------------------------------------------------
        # 2. Proxy to easycollege API to get full previous semester CGPA data
        # -------------------------------------------------------------------
        import requests
        API = "https://easycollege-4fiy.onrender.com"
        
        login_res = requests.post(f"{API}/api/login", json={
            "roll_number": roll.upper(),
            "password": password,
            "login_type": "S"
        }, timeout=30)
        
        if login_res.status_code != 200:
            return jsonify({'error': 'External API login failed'}), 500
            
        login_data = login_res.json()
        if not login_data.get('success'):
            return jsonify({'error': login_data.get('error', 'External Login failed')}), 401
            
        ext_token = login_data.get('auth_token')
        
        cgpa_res = requests.post(f"{API}/api/cgpa", json={
            "auth_token": ext_token
        }, timeout=30)
        
        if cgpa_res.status_code != 200:
            return jsonify({'error': 'External API CGPA fetch failed'}), 500
            
        ext_data = cgpa_res.json()
        
        # -------------------------------------------------------------------
        # 3. Format data for the frontend
        # -------------------------------------------------------------------
        semesters = ext_data.get('semwise_data') or ext_data.get('semesters') or []
        if isinstance(semesters, dict):
            semesters = list(semesters.values())
            
        cgpa_field = ext_data.get('cgpa')
        if isinstance(cgpa_field, dict):
            overall_cgpa = cgpa_field.get('cgpa') or ext_data.get('overall_cgpa')
            total_credits = cgpa_field.get('total_credits') or ext_data.get('total_credits') or 0
        else:
            overall_cgpa = cgpa_field or ext_data.get('overall_cgpa')
            total_credits = ext_data.get('total_credits') or 0
        
        semwise_formatted = []
        for s in semesters:
            try:
                sgpa_val = float(s.get('sgpa') or s.get('gpa') or 0)
                sem_cgpa_val = float(s.get('cgpa') or s.get('credits') or 0)
                semwise_formatted.append({
                    'sem': int(s.get('sem') or 1),
                    'sgpa': sgpa_val,
                    'cgpa': sem_cgpa_val
                })
            except:
                pass
                
        semwise_formatted.sort(key=lambda x: x['sem'])

        return jsonify({
            'cgpa': overall_cgpa,
            'total_credits': total_credits,
            'semwise_data': semwise_formatted,
            'all_subjects': all_subjects
        })

    except Exception as e:
        logger.error(f"CGPA API proxy error: {str(e)}")
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


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
