"""
Smart Bunker - Flask Backend
============================
Attendance tracking and bunker-planning system exclusively for PSG College of Technology (PSG Tech).

┌──────────────────────────────────────────────────────────────────────────────┐
│  College  │  Roll No Format     │  Portal URL                  │  Min Att.  │
├──────────────────────────────────────────────────────────────────────────────┤
│ PSG Tech  │ 6-7 alphanumeric    │ ecampus.psgtech.ac.in        │  75% (exam)│
│           │ e.g. 22CSA01        │ /studzone/                   │  80% bunk  │
└──────────────────────────────────────────────────────────────────────────────┘

College Detection Logic (detect_college):
  - Validates roll number format against PSG Tech branch maps -> 'PSGTECH'

Scraper Classes:
  - EcampusScraper : PSG Tech (ecampus.psgtech.ac.in/studzone/)

API Endpoints:
  POST /api/login           → Authenticate + fetch attendance/timetable
  GET  /api/calendar/<roll> → Academic calendar (PSG Tech)
  POST /api/internals       → CA marks (PSG Tech)
  POST /api/gpa             → GPA / results (PSG Tech)
  POST /api/cgpa            → CGPA history (PSG Tech)
  POST /api/feedback        → Automated 5-star course & staff feedback
"""

from flask import Flask, render_template, request, jsonify, send_file, abort
import requests
from bs4 import BeautifulSoup
import math
import time
from datetime import datetime
import os
import json
import logging
import urllib3
import re
from concurrent.futures import ThreadPoolExecutor

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
# ===== AUTOMATED ACADEMIC CALENDAR RESOLVER (Zero Manual Tokens) =====
# ============================================================================

PSGTECH_BRANCH_MAP = {
    # BE Programs (4 Years)
    'A': {'degree': 'B.E.', 'name': 'Automobile Engineering', 'sandwich': False, 'years': 4},
    'D': {'degree': 'B.E.', 'name': 'Civil Engineering', 'sandwich': False, 'years': 4},
    'C': {'degree': 'B.E.', 'name': 'Computer Science & Engineering', 'sandwich': False, 'years': 4},
    'CS': {'degree': 'B.E.', 'name': 'Computer Science & Engineering', 'sandwich': False, 'years': 4},
    'Z': {'degree': 'B.E.', 'name': 'Electronics & Communication Engineering', 'sandwich': False, 'years': 4},
    'N': {'degree': 'B.E.', 'name': 'Electrical & Electronics Engineering', 'sandwich': False, 'years': 4},
    'E': {'degree': 'B.E.', 'name': 'Electronics & Instrumentation Engineering', 'sandwich': False, 'years': 4},
    'L': {'degree': 'B.E.', 'name': 'Mechanical Engineering', 'sandwich': False, 'years': 4},
    'M': {'degree': 'B.E.', 'name': 'Metallurgical Engineering', 'sandwich': False, 'years': 4},
    'Y': {'degree': 'B.E.', 'name': 'Production Engineering', 'sandwich': False, 'years': 4},
    'P': {'degree': 'B.E. (Sandwich)', 'name': 'Production Engineering (Sandwich)', 'sandwich': True, 'years': 5},
    'K': {'degree': 'B.E. (Sandwich)', 'name': 'Mechanical Engineering (Sandwich)', 'sandwich': True, 'years': 5},
    'ES': {'degree': 'B.E. (Sandwich)', 'name': 'Electrical & Electronics (Sandwich)', 'sandwich': True, 'years': 5},
    'SW': {'degree': 'B.E. (Sandwich)', 'name': 'Sandwich Engineering Program', 'sandwich': True, 'years': 5},
    'R': {'degree': 'B.E.', 'name': 'Robotics & Automation', 'sandwich': False, 'years': 4},
    'U': {'degree': 'B.E.', 'name': 'Biomedical Engineering', 'sandwich': False, 'years': 4},
    
    # BTech Programs (4 Years)
    'B': {'degree': 'B.Tech', 'name': 'Biotechnology', 'sandwich': False, 'years': 4},
    'H': {'degree': 'B.Tech', 'name': 'Fashion Technology', 'sandwich': False, 'years': 4},
    'I': {'degree': 'B.Tech', 'name': 'Information Technology', 'sandwich': False, 'years': 4},
    'T': {'degree': 'B.Tech', 'name': 'Textile Technology', 'sandwich': False, 'years': 4},
    
    # BSc Programs (3 Years)
    'S': {'degree': 'B.Sc', 'name': 'Applied Science / Computer Systems', 'sandwich': False, 'years': 3},
    'X': {'degree': 'B.Sc', 'name': 'Mathematics & Computing', 'sandwich': False, 'years': 3},
    
    # MSc Programs (5 Years Integrated or 2 Years)
    'SA': {'degree': 'M.Sc (Integrated)', 'name': 'Software Systems', 'sandwich': False, 'years': 5},
    'FD': {'degree': 'M.Sc (Integrated)', 'name': 'Data Science', 'sandwich': False, 'years': 5},
    'XW': {'degree': 'M.Sc (Integrated)', 'name': 'Cyber Security', 'sandwich': False, 'years': 5},
    'XT': {'degree': 'M.Sc (Integrated)', 'name': 'Theoretical Computer Science', 'sandwich': False, 'years': 5},
    'XD': {'degree': 'M.Sc (Integrated)', 'name': 'Decision & Computing Sciences', 'sandwich': False, 'years': 5},
    'XC': {'degree': 'M.Sc (Integrated)', 'name': 'Theoretical Computer Science', 'sandwich': False, 'years': 5},
    
    # MCA (2 Years)
    'MX': {'degree': 'M.C.A.', 'name': 'Master of Computer Applications', 'sandwich': False, 'years': 2},
    
    # ME / MTech Programs (2 Years)
    'AE': {'degree': 'M.E.', 'name': 'Automotive Engineering', 'sandwich': False, 'years': 2},
    'NB': {'degree': 'M.E.', 'name': 'Energy Engineering', 'sandwich': False, 'years': 2},
    'ZC': {'degree': 'M.E.', 'name': 'Communication Systems', 'sandwich': False, 'years': 2},
    'UC': {'degree': 'M.E.', 'name': 'Embedded & Real-Time Systems', 'sandwich': False, 'years': 2},
    'EE': {'degree': 'M.E.', 'name': 'Power Electronics & Drives', 'sandwich': False, 'years': 2},
    'MD': {'degree': 'M.E.', 'name': 'Manufacturing Engineering', 'sandwich': False, 'years': 2},
    'MN': {'degree': 'M.E.', 'name': 'Engineering Design', 'sandwich': False, 'years': 2},
    'PP': {'degree': 'M.E.', 'name': 'Computer Science & Engineering', 'sandwich': False, 'years': 2},
    'ED': {'degree': 'M.E.', 'name': 'Industrial Engineering', 'sandwich': False, 'years': 2},
    'CS': {'degree': 'M.E.', 'name': 'Computer Science & Engineering', 'sandwich': False, 'years': 2},
    'LV': {'degree': 'M.E.', 'name': 'VLSI Design', 'sandwich': False, 'years': 2},
    'BT': {'degree': 'M.Tech', 'name': 'Biotechnology', 'sandwich': False, 'years': 2},
    'LN': {'degree': 'M.Tech', 'name': 'Nano Science & Technology', 'sandwich': False, 'years': 2},
    'TT': {'degree': 'M.Tech', 'name': 'Textile Technology', 'sandwich': False, 'years': 2},
    'SE': {'degree': 'M.E.', 'name': 'Structural Engineering', 'sandwich': False, 'years': 2},
    'CE': {'degree': 'M.Tech', 'name': 'Chemical Engineering', 'sandwich': False, 'years': 2},
    'EC': {'degree': 'M.Tech', 'name': 'Electronics & Communication', 'sandwich': False, 'years': 2},
    'IT': {'degree': 'M.Tech', 'name': 'Information Technology', 'sandwich': False, 'years': 2},
    'GM': {'degree': 'M.B.A.', 'name': 'Master of Business Administration', 'sandwich': False, 'years': 2},
    'GW': {'degree': 'M.B.A.', 'name': 'Master of Business Administration', 'sandwich': False, 'years': 2}
}


class AutoCalendarResolver:
    """
    Automated Calendar & Planner Resolver for PSG College of Technology.
    Dynamically discovers current academic year and planners from official API:
    https://academicschedule.psgtech.ac.in/api/calendar
    Eliminates all manual tokens and hardcoded semester planner IDs.
    """
    _CALENDARS_INDEX_CACHE = {'data': None, 'timestamp': 0}
    _PLANNER_CACHE = {}

    @classmethod
    def get_current_academic_year(cls):
        now = datetime.now()
        # In PSG Tech, academic year runs Jun-May.
        # Jan-May belongs to the academic year starting previous calendar year.
        return now.year - 1 if (1 <= now.month <= 5) else now.year

    @classmethod
    def get_calendar_index(cls, force_refresh=False):
        now = time.time()
        if not force_refresh and cls._CALENDARS_INDEX_CACHE['data'] and (now - cls._CALENDARS_INDEX_CACHE['timestamp'] < 3600):
            return cls._CALENDARS_INDEX_CACHE['data']
            
        disk_data = get_disk_cache('psg_academic_calendar_index', max_age_seconds=3600)
        if not force_refresh and disk_data:
            cls._CALENDARS_INDEX_CACHE['data'] = disk_data
            cls._CALENDARS_INDEX_CACHE['timestamp'] = now
            return disk_data

        try:
            url = "https://academicschedule.psgtech.ac.in/api/calendar"
            res = requests.get(url, timeout=4, verify=False)
            if res.status_code == 200:
                data = res.json()
                cls._CALENDARS_INDEX_CACHE['data'] = data
                cls._CALENDARS_INDEX_CACHE['timestamp'] = now
                set_disk_cache('psg_academic_calendar_index', data)
                return data
        except Exception as e:
            logger.warning(f"Error fetching live calendar index: {e}")

        # Fallback to local cache if present
        fallback_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'all_calendars_cache.json')
        if os.path.exists(fallback_path):
            try:
                with open(fallback_path, 'r', encoding='utf-8') as f:
                    cached_planners = json.load(f)
                    planners_list = list(cached_planners.values())
                    synthesized = [{
                        'year': cls.get_current_academic_year(),
                        'planner': planners_list
                    }]
                    cls._CALENDARS_INDEX_CACHE['data'] = synthesized
                    cls._CALENDARS_INDEX_CACHE['timestamp'] = now
                    return synthesized
            except Exception as e:
                logger.error(f"Failed to read static fallback cache: {e}")

        return cls._CALENDARS_INDEX_CACHE.get('data') or []

    @classmethod
    def clean_roll_input(cls, raw_roll):
        """Sanitizes roll numbers, repairs spreadsheet scientific notation (e.g. 2.50E+119 -> 25E119), and handles lateral entry prefixes."""
        if not raw_roll:
            return ""
        roll = str(raw_roll).strip().upper()
        import re
        m = re.match(r'^(\d+)\.?(\d*)E\+(\d+)$', roll)
        if m:
            digits_before = m.group(1) + m.group(2)
            year = digits_before[:2]
            suffix = m.group(3)
            return f"{year}E{suffix}"
        # Strip optional leading 'D' for diploma / lateral entries e.g. D26U233 -> 26U233
        roll = re.sub(r'^D(\d{2}[A-Z])', r'\1', roll)
        return roll

    @classmethod
    def extract_sem_from_courses(cls, course_codes):
        """Extract dominant semester from a list of PSG Tech course codes (e.g. 23U301 -> 3)"""
        if not course_codes:
            return None
        import re
        from collections import Counter
        sems = []
        for code in course_codes:
            code = str(code).strip().upper()
            m = re.search(r'^[0-9]{2}[A-Z]+([1-9])\d{2}', code)
            if m:
                sems.append(int(m.group(1)))
            else:
                m2 = re.search(r'^[0-9]{2}[A-Z]+([1-9])\d{1}$', code)
                if m2:
                    sems.append(int(m2.group(1)))
        return Counter(sems).most_common(1)[0][0] if sems else None

    @classmethod
    def detect_ecampus_semester(cls, roll):
        """
        Attempts to detect student's active semester from eCampus cached session or course data.
        Returns dict with semester_no, year_of_study, semester_type, student_name, or None.
        """
        if not roll:
            return None
        clean_roll = cls.clean_roll_input(roll)
        import hashlib, glob
        roll_hash = hashlib.sha256(f"{clean_roll}:PSGTECH".encode()).hexdigest()
        
        # 1. Check previous attendance cache
        prev_path = f"/tmp/bunker_prev_{roll_hash}.json"
        if os.path.exists(prev_path):
            try:
                with open(prev_path, 'r', encoding='utf-8') as f:
                    d = json.load(f)
                subs = d.get('subjects', [])
                codes = [s.get('code') for s in subs if s.get('code')]
                sem = cls.extract_sem_from_courses(codes)
                if sem:
                    return {
                        'semester_no': sem,
                        'year_of_study': (sem + 1) // 2,
                        'semester_type': 'odd' if (sem % 2 == 1) else 'even',
                        'student_name': d.get('student_name'),
                        'course_count': len(codes),
                        'source': 'ecampus_attendance'
                    }
            except Exception as e:
                logger.warning(f"Error reading prev cache: {e}")

        # 2. Check allsem results cache
        results_pattern = f"/tmp/bunker_results_v4_*.json"
        for fpath in glob.glob(results_pattern):
            try:
                with open(fpath, 'r', encoding='utf-8') as f:
                    rd = json.load(f)
                if rd.get('roll') == clean_roll or (clean_roll in fpath):
                    latest_sem = rd.get('latest_sem')
                    if latest_sem and isinstance(latest_sem, int):
                        curr_sem = latest_sem + 1
                        return {
                            'semester_no': curr_sem,
                            'year_of_study': (curr_sem + 1) // 2,
                            'semester_type': 'odd' if (curr_sem % 2 == 1) else 'even',
                            'source': 'ecampus_results'
                        }
            except Exception:
                pass

        return None

    @classmethod
    def parse_student_roll(cls, roll, acad_year=None, semester=None):
        if not roll:
            return None
        roll = cls.clean_roll_input(roll)
        if len(roll) < 4:
            return None
        
        import re
        m_year = re.match(r'^(\d{2})', roll)
        if not m_year:
            return None
        admission_year = int('20' + m_year.group(1))
        
        if not acad_year:
            acad_year = cls.get_current_academic_year()
            
        m_letters = re.search(r'[A-Z]+', roll[2:])
        branch_letters = m_letters.group(0) if m_letters else ''
        
        branch_code = None
        if len(branch_letters) >= 2:
            code2 = branch_letters[:2]
            if code2 in PSGTECH_BRANCH_MAP:
                branch_code = code2
            elif code2 == 'PT':
                branch_code = 'P'
        elif len(branch_letters) == 1 and branch_letters in PSGTECH_BRANCH_MAP:
            branch_code = branch_letters

        if not branch_code or branch_code not in PSGTECH_BRANCH_MAP:
            return None
            
        branch_meta = PSGTECH_BRANCH_MAP[branch_code]

        # Serial number in roll (e.g. 25U402 -> 402, 25U201 -> 201, 22E613 -> 613)
        m_num = re.search(r'(\d+)$', roll)
        serial_num = int(m_num.group(1)) if m_num else 0

        deg = branch_meta.get('degree', 'B.E.')

        # Distinguish Sandwich sections (500-series and 600-series for E, M, P, N, L)
        is_sandwich = branch_meta.get('sandwich', False) or (500 <= serial_num <= 699 and branch_code in ['E', 'M', 'P', 'N', 'L'])

        # Detect Lateral Entry:
        # In B.E. / B.Tech, lateral entry students enter directly into Year 2 and are assigned
        # roll numbers in the 400-series (401-499) or prefixed with L/LE/D.
        is_lateral = (400 <= serial_num <= 499 and deg in ['B.E.', 'B.Tech']) or roll.startswith(('L', 'LE', 'D'))

        # Calculate nominal year of study:
        # Lateral entry enters directly into 2nd year (skips 1st year)
        if is_lateral:
            nominal_year = acad_year - admission_year + 2
        else:
            nominal_year = acad_year - admission_year + 1

        # Check eCampus cached data for this student
        ecampus_info = cls.detect_ecampus_semester(roll)

        semester_no = None
        if semester and str(semester).strip().isdigit():
            # Explicit semester number override (e.g. sem=5, sem=3)
            semester_no = int(str(semester).strip())
            year_of_study = (semester_no + 1) // 2
            semester_type = 'odd' if (semester_no % 2 == 1) else 'even'
        elif ecampus_info and ecampus_info.get('semester_no'):
            # eCampus detected semester
            semester_no = ecampus_info['semester_no']
            year_of_study = ecampus_info['year_of_study']
            semester_type = ecampus_info['semester_type']
        else:
            year_of_study = nominal_year
            now_month = datetime.now().month
            if semester and str(semester).strip().lower() in ['odd', 'even']:
                semester_type = str(semester).strip().lower()
            else:
                semester_type = 'even' if (1 <= now_month <= 5) else 'odd'
            semester_no = (year_of_study * 2) if semester_type == 'even' else (year_of_study * 2 - 1)

        is_sandwich = is_sandwich or (year_of_study == 5 and branch_code not in ['SA', 'FD', 'XW', 'XT', 'XD', 'XC'])
        max_years = 5 if is_sandwich or branch_code in ['SA', 'FD', 'XW', 'XT', 'XD', 'XC'] else branch_meta.get('years', 4)
        year_of_study = max(1, min(max_years, year_of_study))
        semester_no = max(1, min(max_years * 2, semester_no))

        is_mca = (branch_code == 'MX')
        is_msc = branch_code in ['SA', 'FD', 'XW', 'XT', 'XD', 'XC']
        is_bsc = branch_code in ['S', 'X']
        is_pg = deg in ['M.E.', 'M.Tech', 'M.B.A.']
        deg_clean = deg.replace('.', '').upper()
        if 'BTECH' in deg_clean: course_type = 'BTech'
        elif 'BSC' in deg_clean: course_type = 'BSc'
        elif 'MSC' in deg_clean: course_type = 'MSc'
        elif 'ME' in deg_clean or 'MTECH' in deg_clean or 'MBA' in deg_clean: course_type = 'ME'
        elif 'MCA' in deg_clean: course_type = 'MCA'
        else: course_type = 'BE'

        return {
            'roll': roll,
            'admission_year': admission_year,
            'academic_year': acad_year,
            'year_of_study': year_of_study,
            'semester_no': semester_no,
            'semester_type': semester_type,
            'is_lateral_entry': is_lateral,
            'entry_type': 'Lateral Entry (Direct 2nd Year)' if is_lateral else 'Regular Entry',
            'branch_code': branch_code,
            'degree': deg,
            'branch_name': branch_meta.get('name', 'Engineering'),
            'course': course_type,
            'is_sandwich': is_sandwich,
            'is_mca': is_mca,
            'is_msc': is_msc,
            'is_bsc': is_bsc,
            'is_pg': is_pg,
            'ecampus_synced': bool(ecampus_info),
            'ecampus_info': ecampus_info
        }

    @classmethod
    def match_planner(cls, planners, student_info, semester='odd'):
        import re

        def split_clauses(title):
            clean = title.lower()
            clean = clean.replace('reg & sw', 'reg_and_sw').replace('reg. & sw', 'reg_and_sw')
            clean = clean.replace('reg. &sw', 'reg_and_sw').replace('regular & sw', 'reg_and_sw')
            clean = clean.replace('regular and sw', 'reg_and_sw')
            clean = clean.replace('be / b.tech', 'be').replace('be/btech', 'be').replace('b.e / b.tech', 'be')
            clean = clean.replace('all bsc and all msc', 'all_bsc_msc').replace('all bsc & all msc', 'all_bsc_msc')
            return [cl.strip() for cl in re.split(r'[,;]|\band\b', clean) if cl.strip()]

        def score_clause(clause, s):
            c = clause.lower()
            y = s['year_of_study']
            course_norm = s.get('course', 'BE').replace('.', '').upper()

            if s['is_sandwich']:
                if not any(w in c for w in ['sw', 'sandwich']):
                    return 0
                if y == 5 and any(w in c for w in ['fifth', '5th', 'v year', 'final']): return 100
                if y == 4 and any(w in c for w in ['fourth', '4th', 'iv year']): return 100
                if y == 3 and any(w in c for w in ['third', '3rd', 'iii']): return 90
                if y == 2 and any(w in c for w in ['second', '2nd', 'ii']): return 90
                if y == 1 and any(w in c for w in ['first', '1st', 'i ']): return 90
                return 70

            # Normal student shouldn't match sandwich-only planners
            if any(w in c for w in ['fourth year be sw', 'fifth year be sw', 'final year be sandwich']):
                return 0

            if s['is_bsc'] or s['is_msc']:
                return 100 if any(w in c for w in ['bsc', 'msc', 'b.sc', 'm.sc', 'all_bsc_msc']) else 0

            if s['is_mca']:
                if 'mca' not in c: return 0
                if y == 1 and any(w in c for w in ['first', '1st', 'i year', 'i ']): return 100
                if y >= 2 and any(w in c for w in ['second', '2nd', 'ii year', 'ii ']): return 100
                return 80

            if s['is_pg']:
                if not any(w in c for w in ['me', 'mtech', 'm.tech', 'pg']): return 0
                if y == 1 and any(w in c for w in ['first', '1st', 'i year', 'i ']): return 100
                if y >= 2 and any(w in c for w in ['second', '2nd', 'ii year', 'ii ']): return 100
                return 80

            if course_norm in ['BE', 'BTECH']:
                if ('mca' in c and not any(w in c for w in ['be', 'btech'])) or ('all_bsc_msc' in c and not any(w in c for w in ['be', 'btech'])):
                    return 0
                if y == 1 and any(w in c for w in ['first year', '1st year', 'i year', 'first  year']): return 100
                elif y == 2 and any(w in c for w in ['second year', '2nd year', 'ii year']): return 100
                elif y in [3, 4] and any(w in c for w in ['3rd', '4th', 'third', 'fourth', 'iii', 'iv']): return 100

            return 0

        # Filter by semester
        semester = (semester or 'odd').lower()
        active_planners = []
        for p in planners:
            name_lower = p.get('name', '').lower()
            if semester == 'odd':
                if p.get('isPublished') or ('odd' in name_lower and 'even' not in name_lower):
                    active_planners.append(p)
            else:
                if not p.get('isPublished') or 'even' in name_lower:
                    active_planners.append(p)
                    
        if not active_planners:
            active_planners = planners

        best_planner = None
        best_score = -1
        for p in active_planners:
            clauses = split_clauses(p.get('name', ''))
            clause_max = max((score_clause(cl, student_info) for cl in clauses), default=0)
            if clause_max > best_score:
                best_score = clause_max
                best_planner = p

        return best_planner

    @classmethod
    def get_planner_details(cls, year, planner_id):
        key = f"{year}_{planner_id}"
        now = time.time()
        if key in cls._PLANNER_CACHE and (now - cls._PLANNER_CACHE[key]['time'] < 3600):
            return cls._PLANNER_CACHE[key]['data']

        disk_data = get_disk_cache(f"psg_planner_{key}", max_age_seconds=3600)
        if disk_data:
            cls._PLANNER_CACHE[key] = {'data': disk_data, 'time': now}
            return disk_data

        try:
            url = f"https://academicschedule.psgtech.ac.in/api/calendar/{year}/planner/{planner_id}"
            res = requests.get(url, timeout=4, verify=False)
            if res.status_code == 200:
                data = res.json()
                cls._PLANNER_CACHE[key] = {'data': data, 'time': now}
                set_disk_cache(f"psg_planner_{key}", data)
                return data
        except Exception as e:
            logger.warning(f"Error fetching planner {key}: {e}")

        # Check static fallback cache
        fallback_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'all_calendars_cache.json')
        if os.path.exists(fallback_path):
            try:
                with open(fallback_path, 'r', encoding='utf-8') as f:
                    cdata = json.load(f)
                    if str(planner_id) in cdata:
                        return cdata[str(planner_id)]
            except Exception:
                pass
        return None

    @classmethod
    def resolve_calendar(cls, roll, semester=None, year=None):
        """
        Main entry point to resolve calendar dynamically for any roll number.
        Returns (student_info, planner_meta, full_planner_data, all_planners_for_year).
        Supports:
          - Regular roll numbers (e.g. 24C001, 25E201)
          - Lateral Entry roll numbers (e.g. 25U402, 24M641 -> 3rd year in 2026)
          - eCampus active semester auto-detection
          - Numeric semester overrides (?sem=1..10) or season (?sem=odd|even)
        """
        all_calendars = cls.get_calendar_index()
        if not all_calendars:
            return None, None, None, []

        try:
            target_year = int(year) if year else max(c.get('year', 2026) for c in all_calendars)
        except Exception:
            target_year = cls.get_current_academic_year()

        year_entry = next((c for c in all_calendars if c.get('year') == target_year), all_calendars[0])
        year_planners = year_entry.get('planner', [])

        student = cls.parse_student_roll(roll, target_year, semester=semester)
        if not student:
            return None, None, None, year_planners

        # Determine target semester type for planner matching
        if semester and str(semester).strip().lower() in ['odd', 'even']:
            target_sem_type = str(semester).strip().lower()
        else:
            target_sem_type = student.get('semester_type', 'odd')

        matched_planner = cls.match_planner(year_planners, student, semester=target_sem_type)
        if not matched_planner and year_planners:
            matched_planner = year_planners[0]

        details = None
        if matched_planner:
            details = cls.get_planner_details(target_year, matched_planner['id'])

        return student, matched_planner, details, year_planners


# Backward compatibility CONFIG dictionary
CONFIG = {
    'API_YEAR': AutoCalendarResolver.get_current_academic_year(),
    'COURSE_CODES': {k: v['degree'] for k, v in PSGTECH_BRANCH_MAP.items()},
    'PLANNER_MAP': {}  # Handled dynamically by AutoCalendarResolver
}

# ============================================================================
# ===== END OF AUTOMATED CALENDAR SECTION =====
# ============================================================================

_CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
_TEMPLATES_DIR = os.path.join(_CURRENT_DIR, 'templates')
if not os.path.isdir(_TEMPLATES_DIR):
    _TEMPLATES_DIR = _CURRENT_DIR

_STATIC_DIR = os.path.join(_CURRENT_DIR, '..', 'static')
if not os.path.isdir(_STATIC_DIR):
    _STATIC_DIR = _CURRENT_DIR

app = Flask(__name__, template_folder=_TEMPLATES_DIR, static_folder=_STATIC_DIR)

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
                response.headers['Vary'] = 'Accept-Encoding'
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


def get_planner_id(roll_number, semester=None):
    """Get planner ID for calendar from roll number using automated resolver"""
    if not roll_number or len(roll_number) < 4:
        return None
    
    student, planner, details, _ = AutoCalendarResolver.resolve_calendar(roll_number, semester=semester)
    if planner and 'id' in planner:
        return planner['id']
        
    return None


def detect_college(roll_number):
    """
    Validate and determine if roll number belongs to PSG College of Technology.
    Returns 'PSGTECH' if valid PSG Tech student format, otherwise None.
    """
    if not roll_number:
        return None
    
    roll_number = AutoCalendarResolver.clean_roll_input(roll_number)
    
    import re
    # PSG Tech roll numbers start with 2-digit year followed by valid branch code
    m = re.match(r'^\d{2}([A-Z]+)', roll_number)
    if m:
        letters = m.group(1)
        if len(letters) >= 2:
            code2 = letters[:2]
            if code2 in PSGTECH_BRANCH_MAP or code2 == 'PT':
                return 'PSGTECH'
        elif len(letters) == 1 and letters in PSGTECH_BRANCH_MAP:
            return 'PSGTECH'

    return None


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

@app.route('/google824b5c1fd4aa93e7.html')
def serve_google_verification():
    return "google-site-verification: google824b5c1fd4aa93e7.html", 200, {'Content-Type': 'text/html; charset=utf-8'}

@app.route('/')
def index():
    """Serve main application"""
    return render_template('index.html')


@app.route('/calendar')
@app.route('/calendar.html')
def calendar_page():
    """Serve standalone Google Calendar style academic calendar & event planner (public, no auth required)"""
    try:
        return render_template('calendar.html')
    except Exception:
        cal_path = os.path.join(_CURRENT_DIR, 'calendar.html')
        if os.path.exists(cal_path):
            return send_file(cal_path)
        raise

@app.route('/static/calendar.js')
def serve_calendar_js():
    for candidate in [
        os.path.join(_CURRENT_DIR, '..', 'static', 'calendar.js'),
        os.path.join(_CURRENT_DIR, 'calendar.js')
    ]:
        if os.path.exists(candidate):
            return send_file(candidate, mimetype='application/javascript')
    return abort(404)


@app.route('/api/login', methods=['POST'])
def api_login():
    """API endpoint for login - Exclusively for PSG College of Technology"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip().upper()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Credentials required'})
        
        # Detect college from roll number
        college = detect_college(username)
        
        if college != 'PSGTECH':
            return jsonify({
                'success': False, 
                'error': 'Invalid roll number format. Bunker is exclusively for PSG College of Technology students.'
            })
        
        scraper = EcampusScraper(username, password)
        
        if not scraper.authenticated:
            return jsonify({'success': False, 'error': 'Invalid credentials'})
            
        import hashlib
        import json
        
        # Cache file path based on credentials
        cred_hash = hashlib.sha256(f"{username}:{password}:PSGTECH".encode()).hexdigest()
        cache_path = f"/tmp/bunker_cache_{cred_hash}.json"
        
        # Always fetch attendance to verify if new data has been updated from college side
        attendance_data, last_update, att_msg = scraper.get_attendance()
        
        use_cache = False
        cached_response = None
        
        if os.path.exists(cache_path):
            try:
                with open(cache_path, 'r') as f:
                    cached_data = json.load(f)
                    
                # For PSG Tech, last_update is reliable
                if cached_data.get('last_update') == last_update and last_update != "No data":
                    use_cache = True
                        
                if use_cache:
                    cached_response = cached_data.get('response')
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
        roll_hash = hashlib.sha256(f"{username.strip().upper()}:PSGTECH".encode()).hexdigest()
        prev_cache_path = f"/tmp/bunker_prev_{roll_hash}.json"

        # Prepare response data
        response_data = {
            'success': True,
            'subjects': processed_subjects,
            'timetable': weekly_schedule,
            'course_mapping': course_mapping,
            'last_update': last_update or "No data",
            'college': 'PSGTECH',
            'has_calendar': True
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
    """Returns calendar planners dynamically for all departments with caching"""
    now = time.time()
    
    # 1 hour in-memory cache
    if ALL_CALENDARS_CACHE['data'] and (now - ALL_CALENDARS_CACHE['timestamp'] < 3600):
        resp = jsonify(ALL_CALENDARS_CACHE['data'])
        resp.headers['Cache-Control'] = 'public, s-maxage=3600, stale-while-revalidate=7200'
        return resp

    # Dynamically fetch live calendar index
    calendar_index = AutoCalendarResolver.get_calendar_index()
    curr_year = AutoCalendarResolver.get_current_academic_year()
    
    target_year_entry = next((y for y in calendar_index if y.get('year') == curr_year), None)
    if not target_year_entry and calendar_index:
        target_year_entry = calendar_index[0]
        curr_year = target_year_entry.get('year', curr_year)
        
    planners_list = target_year_entry.get('planner', []) if target_year_entry else []
    
    # Fetch full planner details for active planners with concurrency/caching
    live_data = {}
    for p in planners_list:
        pid = p.get('id')
        if pid:
            p_details = AutoCalendarResolver.get_planner_details(curr_year, pid)
            if p_details:
                live_data[str(pid)] = p_details
            else:
                live_data[str(pid)] = p

    # Built-in department shortcuts for legacy UI compatibility
    departments = [
        {"id": "be_3_4", "name": "3rd & 4th Year BE / B.Tech", "planner_odd": 32, "planner_even": 40, "color": "#6366f1"},
        {"id": "be_2", "name": "2nd Year BE / B.Tech", "planner_odd": 33, "planner_even": 41, "color": "#a855f7"},
        {"id": "be_1", "name": "1st Year BE / B.Tech", "planner_odd": 39, "planner_even": 42, "color": "#ec4899"},
        {"id": "bsc_msc", "name": "B.Sc & M.Sc (All Years)", "planner_odd": 32, "planner_even": 40, "color": "#06b6d4"},
        {"id": "pg", "name": "ME / M.Tech & MCA", "planner_odd": 32, "planner_even": 40, "color": "#f59e0b"},
        {"id": "sandwich", "name": "BE Sandwich (SW)", "planner_odd": 35, "planner_even": 44, "color": "#10b981"}
    ]

    result = {
        'success': True,
        'year': curr_year,
        'planners': live_data,
        'all_planners_meta': planners_list,
        'departments': departments,
        'available_years': [y.get('year') for y in calendar_index if 'year' in y]
    }
    
    ALL_CALENDARS_CACHE['data'] = result
    ALL_CALENDARS_CACHE['timestamp'] = now
    resp = jsonify(result)
    resp.headers['Cache-Control'] = 'public, s-maxage=3600, stale-while-revalidate=7200'
    return resp


@app.route('/api/calendar/<roll>')
def api_calendar(roll):
    """
    Automated Calendar API:
    Accepts roll number (e.g. 23L101, 24C001, 22CSA01, 25MX01), or planner ID directly.
    Dynamically identifies student, year of study, program, semester, and returns matching schedule.
    Optional query params: ?sem=odd|even &year=2026
    """
    try:
        roll = AutoCalendarResolver.clean_roll_input(roll)
        sem = request.args.get('sem', '').strip().lower() or None
        target_year = request.args.get('year', '').strip() or None
        
        # Direct planner ID access (e.g., /api/calendar/33)
        if roll.isdigit() and len(roll) <= 3:
            pid = int(roll)
            curr_year = int(target_year) if target_year else AutoCalendarResolver.get_current_academic_year()
            details = AutoCalendarResolver.get_planner_details(curr_year, pid)
            if details:
                resp = jsonify(details)
                resp.headers['Cache-Control'] = 'public, s-maxage=3600, stale-while-revalidate=7200'
                return resp
            return jsonify({'error': f'Planner ID {pid} not found for year {curr_year}'}), 404

        # Detect college to determine if calendar is available
        college = detect_college(roll)
        if college != 'PSGTECH':
            return jsonify({
                'error': f"Roll number '{roll}' is not a valid PSG College of Technology roll number. The academic schedule is exclusively published for PSG College of Technology.",
                'college': 'UNKNOWN',
                'rollNumber': roll,
                'name': 'Academic Year',
                'calendar': {'holidays': []},
                'activities': []
            }), 400
            
        # Automated PSG Tech Planner Resolution
        student, matched_planner, details, year_planners = AutoCalendarResolver.resolve_calendar(
            roll, semester=sem, year=target_year
        )
        
        if not matched_planner:
            return jsonify({
                'error': 'Could not identify course/year from roll number',
                'rollNumber': roll
            }), 400

        # Construct unified backward-compatible response
        payload = dict(details) if details else dict(matched_planner)
        payload['success'] = True
        payload['student'] = student
        payload['matchedPlanner'] = matched_planner
        payload['plannerId'] = matched_planner.get('id')
        payload['semester'] = student.get('semester_type') if student else (sem or ('even' if (1 <= datetime.now().month <= 5) else 'odd'))
        payload['semesterNo'] = student.get('semester_no') if student else None
        payload['isLateralEntry'] = student.get('is_lateral_entry', False) if student else False
        payload['ecampusSynced'] = student.get('ecampus_synced', False) if student else False
        payload['academicYear'] = student.get('academic_year') if student else AutoCalendarResolver.get_current_academic_year()
        payload['availablePlanners'] = [
            {
                'id': p.get('id'),
                'name': p.get('name'),
                'isPublished': p.get('isPublished', False),
                'startDate': p.get('startDate'),
                'lastDate': p.get('lastDate')
            }
            for p in year_planners
        ]

        resp = jsonify(payload)
        resp.headers['Cache-Control'] = 'public, s-maxage=3600, stale-while-revalidate=7200'
        return resp
        
    except Exception as e:
        logger.error(f"Calendar API error for {roll}: {str(e)}")
        # Fallback to local cache if network/API fails
        try:
            fallback_path = os.path.join(os.path.dirname(__file__), '..', 'static', 'all_calendars_cache.json')
            if os.path.exists(fallback_path):
                with open(fallback_path, 'r', encoding='utf-8') as f:
                    cdata = json.load(f)
                    # Return first planner from cache as ultimate safety net
                    first_p = next(iter(cdata.values()))
                    resp = jsonify(first_p)
                    resp.headers['Cache-Control'] = 'public, s-maxage=3600, stale-while-revalidate=7200'
                    return resp
        except Exception:
            pass
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




# ============================================================================
# ===== PSG TECH STUDZONE AUTOMATED FEEDBACK ENGINE =====
# ============================================================================

FEEDBACK_BASE_URL = "https://ecampus.psgtech.ac.in"
FEEDBACK_STUDZONE_URL = f"{FEEDBACK_BASE_URL}/studzone"
FEEDBACK_INDEX_URL = f"{FEEDBACK_STUDZONE_URL}/Feedback/Index"
FEEDBACK_ENDSEM_URL = f"{FEEDBACK_STUDZONE_URL}/Feedback/endsemester"
FEEDBACK_INTERMEDIATE_URL = f"{FEEDBACK_STUDZONE_URL}/Feedback/Intermediate"

LOAD_STAFF_ENDSEM_URL = f"{FEEDBACK_STUDZONE_URL}/Feedback/LoadStaffs_endSem"
LOAD_QUES_ENDSEM_URL = f"{FEEDBACK_STUDZONE_URL}/Feedback/LoadQuestions_endSem"
SAVE_ENDSEM_URL = f"{FEEDBACK_STUDZONE_URL}/Feedback/Save_EndSem"

ANS_LIST_INTERMEDIATE_URL = f"{FEEDBACK_STUDZONE_URL}/Feedback/IntermediateAnsList"
SAVE_INTERMEDIATE_URL = f"{FEEDBACK_STUDZONE_URL}/Feedback/Save_Intermediate"

FEEDBACK_DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/134.0.0.0 Safari/537.36",
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "Accept-Language": "en-US,en;q=0.9",
    "Origin": FEEDBACK_BASE_URL,
    "Referer": FEEDBACK_INDEX_URL,
    "X-Requested-With": "XMLHttpRequest",
}


_FEEDBACK_STATUS_CACHE = {}


class FastFeedbackEngine:
    """High-speed pure HTTP automation engine for PSG Tech Studzone."""

    def __init__(self, timeout: int = 5):
        self.session = requests.Session()
        self.session.headers.update(FEEDBACK_DEFAULT_HEADERS)
        adapter = requests.adapters.HTTPAdapter(pool_connections=25, pool_maxsize=25)
        self.session.mount("https://", adapter)
        self.session.mount("http://", adapter)
        self.timeout = timeout

    def extract_antiforgery_token(self, html: str):
        soup = BeautifulSoup(html, "html.parser")
        token_el = soup.find("input", {"name": "__RequestVerificationToken"})
        if token_el and token_el.get("value"):
            return str(token_el.get("value"))
        m = re.search(r'name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"', html)
        return m.group(1) if m else None

    def login(self, rollno: str, password: str):
        clean_roll = rollno.strip().upper()
        clean_pass = password.strip()

        if not clean_roll or not clean_pass:
            return {"success": False, "error": "Roll Number and Password are required."}

        try:
            r_get = self.session.get(f"{FEEDBACK_STUDZONE_URL}/", verify=False, timeout=self.timeout)
            token = self.extract_antiforgery_token(r_get.text)
            if not token:
                return {"success": False, "error": "Unable to initialize secure session with PSG Tech portal."}

            payload = {
                "rollno": clean_roll,
                "password": clean_pass,
                "chkterms": "on",
                "__RequestVerificationToken": token
            }

            r_post = self.session.post(
                FEEDBACK_STUDZONE_URL,
                data=payload,
                verify=False,
                allow_redirects=False,
                timeout=self.timeout
            )

            if r_post.status_code in (301, 302, 303, 307, 308):
                location = r_post.headers.get("Location", "")
                if location == "/studzone" or location.endswith("/studzone/"):
                    r_check = self.session.get(f"{FEEDBACK_BASE_URL}{location}", verify=False, timeout=self.timeout)
                    if "Invalid" in r_check.text or "password" in r_check.text.lower():
                        return {"success": False, "error": "Invalid Roll Number or Password."}
                    return {"success": False, "error": "Login failed. Please verify credentials."}
                return {"success": True}

            if "Student Login" in r_post.text:
                return {"success": False, "error": "Authentication failed. Incorrect Roll Number or Password."}

            return {"success": True}
        except Exception as e:
            return {"success": False, "error": f"Network error: {str(e)}"}

    def _process_endsem(self, rating_style: str = "max") -> str:
        """Evaluate End Semester staff evaluations using verified API."""
        r_page = self.session.get(FEEDBACK_ENDSEM_URL, verify=False, timeout=self.timeout)
        if r_page.url.endswith("/Feedback/Index"):
            return "End Semester Feedback: Currently not scheduled."

        try:
            r_staff = self.session.get(LOAD_STAFF_ENDSEM_URL, verify=False, timeout=self.timeout)
            res_json = r_staff.json()
            if isinstance(res_json, list):
                staff_list = res_json
            elif isinstance(res_json, dict) and "error" in res_json:
                return f"End Semester: {res_json['error']}"
            else:
                staff_list = []
        except Exception:
            staff_list = []

        if not staff_list:
            return "End Semester: All evaluations completed or feedback closed."

        def evaluate_staff(staff):
            staff_id = staff.get("staffId")
            course_code = staff.get("courseCode")
            course_type = staff.get("courseType")
            staff_name = staff.get("staffName", "Staff")

            try:
                r_q = self.session.get(
                    LOAD_QUES_ENDSEM_URL,
                    params={"coursecode": course_code, "coursetype": course_type},
                    verify=False,
                    timeout=self.timeout
                )
                questions = r_q.json() if r_q.text.startswith("[") else []
                q_ids = [q["questionId"] for q in questions if int(q.get("questionId", 0)) > 0]

                if q_ids:
                    # Always 5-star maximum rating (score 4 is top rating in EndSem)
                    scores = [4 for _ in q_ids]

                    self.session.post(
                        SAVE_ENDSEM_URL,
                        data={
                            "coursecode": course_code,
                            "coursetype": course_type,
                            "staffId": staff_id,
                            "quesID": "^".join(map(str, q_ids)),
                            "scorWeight": "^".join(map(str, scores))
                        },
                        verify=False,
                        timeout=self.timeout
                    )
                    return staff_name, True
            except Exception:
                pass
            return staff_name, False

        with ThreadPoolExecutor(max_workers=8) as executor:
            eval_results = list(executor.map(evaluate_staff, staff_list))

        completed_count = sum(1 for _, success in eval_results if success)
        return f"End Semester: Evaluated and saved {completed_count}/{len(staff_list)} staff members successfully (5-Star Rating)!"

    def _process_intermediate(self, rating_style: str = "max") -> str:
        """Evaluate Intermediate course surveys using verified parallel API (Always 5-Star)."""
        r_page = self.session.get(FEEDBACK_INTERMEDIATE_URL, verify=False, timeout=self.timeout)
        if r_page.url.endswith("/Feedback/Index"):
            return "Intermediate Feedback: Currently not active or already 100% completed."

        soup = BeautifulSoup(r_page.text, "html.parser")
        cards = soup.find_all(class_="intermediate-card")
        if not cards:
            return "Intermediate: All course surveys completed or not open."

        tasks = []
        course_count = 0
        for card in cards:
            onclick = card.get("onclick", "")
            m = re.search(r"openQuestionSet\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)", onclick)
            if not m:
                continue
            staff_id, course_code, course_type = m.group(1), m.group(2), m.group(3)
            course_count += 1

            # Always 5-star: ans_id="1" is "Strongly Agree" (top option)
            for q in range(1, 12):
                tasks.append((course_code, staff_id, course_type, str(q), "1"))

        def send_intermediate_ans(item):
            cc, sid, ct, qid, aid = item
            try:
                self.session.post(
                    SAVE_INTERMEDIATE_URL,
                    data={
                        "coursecode": cc,
                        "staffId": sid,
                        "questype": ct,
                        "quesID": qid,
                        "ansid": aid
                    },
                    verify=False,
                    timeout=self.timeout
                )
            except Exception:
                pass

        # Parallel multi-threading for instant submission (< 0.8s for all courses)
        with ThreadPoolExecutor(max_workers=12) as executor:
            list(executor.map(send_intermediate_ans, tasks))

        return f"Intermediate: Evaluated and saved all {course_count} courses (100% complete)!"

    def get_portal_schedules(self):
        """Fetch schedule dates from Feedback/Index to auto-detect active feedback."""
        schedules = {"endsem": "NOT SCHEDULED", "intermediate": "NOT SCHEDULED"}
        try:
            r = self.session.get(FEEDBACK_INDEX_URL, verify=False, timeout=self.timeout)
            soup = BeautifulSoup(r.text, "html.parser")
            for card in soup.find_all(class_="menu-cards"):
                title_el = card.find(class_="card-title")
                dates_el = card.find("small")
                if title_el:
                    title = title_el.text.strip().lower()
                    dates = re.sub(r"\s+", " ", dates_el.text.strip()) if dates_el else "NOT SCHEDULED"
                    if "end" in title or "sem" in title:
                        schedules["endsem"] = dates
                    elif "inter" in title:
                        schedules["intermediate"] = dates
        except Exception:
            pass
        return schedules

    def check_pending_feedback(self):
        """Check if any feedback surveys are actively pending on eCampus for this student."""
        schedules = self.get_portal_schedules()
        inter_dates = schedules.get("intermediate", "NOT SCHEDULED")
        endsem_dates = schedules.get("endsem", "NOT SCHEDULED")

        inter_active = "NOT SCHEDULED" not in inter_dates.upper()
        endsem_active = "NOT SCHEDULED" not in endsem_dates.upper()

        if not inter_active and not endsem_active:
            return {
                "has_pending": False,
                "reason": "not_scheduled",
                "intermediate_count": 0,
                "endsem_count": 0,
                "total_pending": 0,
                "schedules": schedules
            }

        inter_pending = 0
        endsem_pending = 0

        def check_intermediate():
            nonlocal inter_pending
            try:
                r_page = self.session.get(FEEDBACK_INTERMEDIATE_URL, verify=False, timeout=self.timeout)
                if not r_page.url.endswith("/Feedback/Index"):
                    soup = BeautifulSoup(r_page.text, "html.parser")
                    cards = soup.find_all(class_="intermediate-card")
                    inter_pending = len(cards)
            except Exception as e:
                logger.debug(f"Intermediate status check error: {e}")

        def check_endsem():
            nonlocal endsem_pending
            try:
                r_page = self.session.get(FEEDBACK_ENDSEM_URL, verify=False, timeout=self.timeout)
                if not r_page.url.endswith("/Feedback/Index"):
                    r_staff = self.session.get(LOAD_STAFF_ENDSEM_URL, verify=False, timeout=self.timeout)
                    if r_staff.text.strip().startswith("["):
                        staff_list = r_staff.json()
                        if isinstance(staff_list, list):
                            endsem_pending = len(staff_list)
            except Exception as e:
                logger.debug(f"EndSem status check error: {e}")

        threads = []
        if inter_active:
            threads.append(check_intermediate)
        if endsem_active:
            threads.append(check_endsem)

        if len(threads) == 1:
            threads[0]()
        elif len(threads) > 1:
            with ThreadPoolExecutor(max_workers=2) as executor:
                list(executor.map(lambda fn: fn(), threads))

        total = inter_pending + endsem_pending
        return {
            "has_pending": total > 0,
            "reason": "pending_found" if total > 0 else "already_completed",
            "intermediate_count": inter_pending,
            "endsem_count": endsem_pending,
            "total_pending": total,
            "schedules": schedules
        }

    def execute_feedback(self, mode: str = "auto", rating_style: str = "max"):
        start = time.time()
        results = []

        try:
            if mode == "auto":
                schedules = self.get_portal_schedules()
                inter_dates = schedules.get("intermediate", "NOT SCHEDULED")
                endsem_dates = schedules.get("endsem", "NOT SCHEDULED")

                inter_active = "NOT SCHEDULED" not in inter_dates.upper()
                endsem_active = "NOT SCHEDULED" not in endsem_dates.upper()

                # 1. Process Intermediate if scheduled
                if inter_active:
                    inter_res = self._process_intermediate(rating_style)
                    results.append(f"Intermediate ({inter_dates}): {inter_res}")

                # 2. Process End Semester if scheduled
                if endsem_active:
                    endsem_res = self._process_endsem(rating_style)
                    results.append(f"End Semester ({endsem_dates}): {endsem_res}")

                # 3. If neither was scheduled on the portal
                if not inter_active and not endsem_active:
                    results.append(f"No feedback currently active. (Intermediate: {inter_dates}, End Sem: {endsem_dates})")

            elif mode == "endsem":
                endsem_res = self._process_endsem(rating_style)
                results.append(endsem_res)
            elif mode == "intermediate":
                inter_res = self._process_intermediate(rating_style)
                results.append(inter_res)
            else:
                return {"success": False, "error": f"Invalid mode '{mode}'. Choose 'auto', 'intermediate', or 'endsem'."}

            elapsed = round(time.time() - start, 2)
            return {
                "success": True,
                "elapsed": elapsed,
                "summary": results,
                "message": f"Completed in {elapsed}s! " + " • ".join(results)
            }
        except Exception as e:
            return {"success": False, "error": f"Execution error: {str(e)}"}


@app.route('/feedback')
@app.route('/feedback.html')
def feedback_page():
    """Serve standalone PSG Tech Feedback Automation Web Interface"""
    return render_template('feedback.html')


@app.route('/api/feedback', methods=['GET', 'POST', 'OPTIONS'])
def api_feedback():
    """API endpoint for PSG Tech automated feedback evaluation"""
    if request.method == 'OPTIONS':
        return '', 200

    if request.method == 'GET':
        return jsonify({
            'status': 'online',
            'service': 'PSG Tech Studzone Feedback Rapid API',
            'version': '3.0-turbo-api'
        })

    try:
        data = request.get_json() or {}
        rollno = data.get('rollno', '').strip().upper()
        password = data.get('password', '').strip()
        mode = data.get('mode', 'auto').strip().lower()
        rating_style = data.get('rating_style', 'max').strip().lower()

        # If not passed in body, try parsing bunker_credentials / auth token
        if not rollno or not password:
            auth_token = data.get('auth_token')
            if auth_token:
                try:
                    parsed = json.loads(auth_token)
                    rollno = parsed.get('roll', '').strip().upper()
                    password = parsed.get('password', '').strip()
                except:
                    pass

        if not rollno or not password:
            return jsonify({'success': False, 'error': 'Roll Number and Password are required.'}), 400

        engine = FastFeedbackEngine(timeout=6)
        login_res = engine.login(rollno, password)
        if not login_res.get('success'):
            return jsonify(login_res), 401

        fb_res = engine.execute_feedback(mode=mode, rating_style=rating_style)
        if fb_res.get('success') and rollno:
            _FEEDBACK_STATUS_CACHE[rollno] = {
                'ts': time.time(),
                'data': {
                    'has_pending': False,
                    'reason': 'already_completed',
                    'intermediate_count': 0,
                    'endsem_count': 0,
                    'total_pending': 0
                }
            }
        return jsonify(fb_res), (200 if fb_res.get('success') else 500)
    except Exception as e:
        logger.error(f"Feedback API error: {str(e)}")
        return jsonify({'success': False, 'error': f'Feedback processing error: {str(e)}'}), 500


@app.route('/api/feedback/status', methods=['GET', 'POST', 'OPTIONS'])
def api_feedback_status():
    """Lightweight check to see if student has pending feedback surveys on eCampus"""
    if request.method == 'OPTIONS':
        return '', 200

    try:
        data = request.get_json(silent=True) or {}
        rollno = data.get('rollno', '').strip().upper()
        password = data.get('password', '').strip()

        if not rollno or not password:
            auth_token = data.get('auth_token')
            if auth_token:
                try:
                    parsed = json.loads(auth_token)
                    rollno = parsed.get('roll', '').strip().upper()
                    password = parsed.get('password', '').strip()
                except:
                    pass

        # Demo or missing credentials -> zero delay, no eCampus call
        if not rollno or not password or rollno == 'DEMO':
            return jsonify({'success': True, 'has_pending': False, 'reason': 'demo_or_no_creds'})

        # In-memory cache for fast repeated checks (TTL 300s = 5 minutes)
        now = time.time()
        cached = _FEEDBACK_STATUS_CACHE.get(rollno)
        if cached and (now - cached.get('ts', 0)) < 300:
            return jsonify({'success': True, **cached.get('data', {}), 'cached': True})

        engine = FastFeedbackEngine(timeout=5)
        login_res = engine.login(rollno, password)
        if not login_res.get('success'):
            return jsonify({'success': False, 'has_pending': False, 'error': login_res.get('error')}), 200

        status_data = engine.check_pending_feedback()
        _FEEDBACK_STATUS_CACHE[rollno] = {'ts': now, 'data': status_data}
        return jsonify({'success': True, **status_data})
    except Exception as e:
        logger.error(f"Feedback status check error: {str(e)}")
        return jsonify({'success': False, 'has_pending': False, 'error': str(e)}), 200


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
