from flask import Flask, render_template, request, jsonify, session
import requests
from bs4 import BeautifulSoup
import math
from datetime import datetime, timedelta
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder='templates')

session_secret = os.environ.get("SESSION_SECRET")
if not session_secret:
    logger.warning("SESSION_SECRET not set - using development fallback. Set SESSION_SECRET in production!")
    session_secret = "bunker-dev-secret-key-change-in-production"

app.secret_key = session_secret
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

class EcampusScraper:
    """Web scraper for eCampus attendance data"""
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
                '__VIEWSTATE': view_state.get('value', '') if view_state else '',
                '__VIEWSTATEGENERATOR': view_state_gen.get('value', '') if view_state_gen else '',
                '__EVENTVALIDATION': event_validation.get('value', '') if event_validation else '',
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
            return None, "Authentication failed"
        
        try:
            attendance_url = f"{self.ECAMPUS_URL}AttWfPercView.aspx"
            response = self.session.get(attendance_url, timeout=30)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            table = soup.find('table', {'class': 'cssbody'})
            if not table:
                return None, "Attendance data not available"
            
            attendance_data = []
            rows = table.find_all('tr')[1:]
            
            for row in rows:
                cols = [col.text.strip() for col in row.find_all('td')] if hasattr(row, 'find_all') else []
                if len(cols) >= 10:
                    try:
                        total_hours = int(cols[1])
                        total_present = int(cols[4])
                        percentage = float(cols[5])
                        
                        bunk_info = self._calculate_bunk_info(percentage, total_hours, total_present)
                        
                        subject_data = {
                            'course_code': cols[0],
                            'name': cols[0],
                            'total': total_hours,
                            'attended': total_present,
                            'percentage': percentage,
                            'bunk_info': bunk_info
                        }
                        attendance_data.append(subject_data)
                    except (ValueError, IndexError):
                        continue
            
            return attendance_data, "Success"
        except Exception as e:
            logger.error(f"Attendance fetch error: {str(e)}")
            return None, f"Error fetching attendance: {str(e)}"
    
    def _calculate_bunk_info(self, percentage, total_hours, total_present, threshold=75):
        """Calculate bunk possibilities"""
        result = {}
        if percentage <= threshold:
            result['action'] = 'attend'
            result['count'] = math.ceil((threshold/100 * total_hours - total_present) / (1 - threshold/100))
        else:
            result['action'] = 'can_bunk'
            result['count'] = math.floor((total_present - (threshold/100 * total_hours)) / (threshold/100))
        return result
    
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
            rows = table.find_all('tr')[1:] if hasattr(table, 'find_all') else []
            for row in rows:
                tds = row.find_all('td') if hasattr(row, 'find_all') else []
                cols = [col.text.strip() for col in tds]
                if len(cols) >= 2:
                    course_mapping[cols[0]] = cols[1]
            
            return course_mapping, "Success"
        except Exception as e:
            logger.error(f"Timetable fetch error: {str(e)}")
            return {}, f"Error: {str(e)}"
    
    def get_weekly_schedule(self):
        """Fetch weekly timetable with days and periods"""
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
                rows = table.find_all('tr') if hasattr(table, 'find_all') else []
                start_idx = 0
                for i, row in enumerate(rows):
                    row_text = row.get_text(strip=True).lower() if hasattr(row, 'get_text') else ''
                    if 'mon' in row_text or i > 1:
                        start_idx = i
                        break
                
                for day_idx, day in enumerate(days):
                    row_idx = start_idx + day_idx
                    if row_idx < len(rows):
                        row = rows[row_idx]
                        cols = row.find_all('td') if hasattr(row, 'find_all') else []
                        
                        for col in cols[1:]:
                            content = col.get_text(strip=True)
                            if content and content.lower() != 'free':
                                matched_code = None
                                for course_code in course_mapping.keys():
                                    if course_code.lower() in content.lower() or content.lower().startswith(course_code.lower()):
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
            days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri']
            return {day: [] for day in days}, f"Error: {str(e)}"
    
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

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/login', methods=['POST'])
def api_login():
    """API endpoint for login"""
    try:
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Credentials required'})
        
        scraper = EcampusScraper(username, password)
        
        if not scraper.authenticated:
            return jsonify({'success': False, 'error': 'Invalid credentials'})
        
        attendance_data, att_msg = scraper.get_attendance()
        if not attendance_data:
            return jsonify({'success': False, 'error': 'Attendance is currently being updated or temporarily stopped by the college.Please check back later.'})
        
        course_mapping, _ = scraper.get_timetable()
        weekly_schedule, _ = scraper.get_weekly_schedule()
        student_name = scraper.get_student_name()
        
        processed_subjects = []
        for subject in attendance_data:
            processed_subjects.append({
                'code': subject['course_code'],
                'name': course_mapping.get(subject['course_code'], subject['course_code']),
                'total': subject['total'],
                'attended': subject['attended'],
                'percentage': subject['percentage']
            })
        
        session['username'] = username
        session['subjects'] = processed_subjects
        session.modified = True
        
        return jsonify({
            'success': True,
            'student_name': student_name,
            'subjects': processed_subjects,
            'timetable': weekly_schedule
        })
    
    except Exception as e:
        logger.error(f"Login API error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/dashboard')
def dashboard():
    return render_template('index.html')

@app.route('/timetable')
def timetable():
    return render_template('index.html')

@app.route('/settings')
def settings():
    return render_template('index.html')

@app.route('/api/manual-attendance', methods=['POST'])
def manual_attendance():
    try:
        data = request.get_json()
        if 'manual_attendance' not in session:
            session['manual_attendance'] = []
        
        entry = {
            'id': datetime.now().timestamp(),
            'subject': data.get('subject'),
            'status': data.get('status'),
            'timestamp': datetime.now().isoformat()
        }
        
        session['manual_attendance'].append(entry)
        session.modified = True
        
        return jsonify({'success': True})
    except Exception as e:
        logger.error(f"Manual attendance error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/clear-manual', methods=['POST'])
def clear_manual():
    session.pop('manual_attendance', None)
    return jsonify({'success': True})

@app.route('/api/get-session-data', methods=['GET'])
def get_session_data():
    """Get current session data (subjects and timetable)"""
    try:
        if 'subjects' not in session:
            return jsonify({'success': False, 'error': 'No session data'})
        
        return jsonify({
            'success': True,
            'subjects': session.get('subjects', []),
            'timetable': session.get('timetable', {}),
            'manual_attendance': session.get('manual_attendance', [])
        })
    except Exception as e:
        logger.error(f"Session data error: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})

@app.route('/logout')
def logout():
    session.clear()
    return jsonify({'success': True})

@app.route('/api/health')
def health():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'Bunker API is running'})

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
