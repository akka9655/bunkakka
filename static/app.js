const CONFIG = {
    API_YEAR: 2025,
    PLANNER_MAP: { "BE_1": 31, "BTech_1": 31, "BE_2": 30, "BTech_2": 30, "BE_3": 29, "BTech_3": 29, "BE_4": 28, "BTech_4": 28, "BE_5": 28, "BSc_1": 29, "BSc_2": 29, "BSc_3": 29, "MSc_1": 29, "MSc_2": 29, "ME_1": 31, "MTech_1": 31, "ME_2": 29, "MTech_2": 29, "MCA_1": 31, "MCA_2": 29 },
    COURSE_CODES: { 'U': 'BE', 'A': 'BE', 'D': 'BE', 'C': 'BE', 'Z': 'BE', 'N': 'BE', 'E': 'BE', 'L': 'BE', 'M': 'BE', 'Y': 'BE', 'P': 'BE', 'R': 'BE', 'B': 'BTech', 'H': 'BTech', 'I': 'BTech', 'T': 'BTech', 'S': 'BSc', 'X': 'BSc', 'AE': 'ME', 'NB': 'ME', 'ZC': 'ME', 'UC': 'ME', 'EE': 'ME', 'MD': 'ME', 'MN': 'ME', 'PP': 'ME', 'ED': 'ME', 'CS': 'ME', 'LV': 'ME', 'BT': 'ME', 'CE': 'MTech', 'EC': 'MTech', 'IT': 'MTech', 'ME': 'MTech', 'MX': 'MCA' }
};
const BASE_URL = `https://academicschedule.psgtech.ac.in/api/calendar/${CONFIG.API_YEAR}`;
const PLANNER_URL = `${BASE_URL}/planner/`;
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri'];
let ACADEMIC_DATA = { name: "Loading...", startDate: new Date().toISOString(), lastDate: new Date().toISOString(), fullCalendar: [] };
let state = {
    rollNumber: localStorage.getItem('bunker_roll') || null,
    college: localStorage.getItem('bunker_college') || 'PSGTECH',
    hasCalendar: localStorage.getItem('bunker_has_calendar') !== 'false',
    subjects: JSON.parse(localStorage.getItem('bunker_subjects') || '[]'),
    timetable: JSON.parse(localStorage.getItem('bunker_timetable') || '{}'),
    courseMapping: JSON.parse(localStorage.getItem('bunker_course_mapping') || '{}'),
    manual: JSON.parse(localStorage.getItem(`bunker_manual_${localStorage.getItem('bunker_roll')}`) || '[]'),
    includeManual: localStorage.getItem(`bunker_include_manual_${localStorage.getItem('bunker_roll')}`) === 'true',
    viewManualAdjusted: localStorage.getItem(`bunker_view_manual_${localStorage.getItem('bunker_roll')}`) === 'true',
    attendanceMode: localStorage.getItem(`bunker_att_mode_${localStorage.getItem('bunker_roll')}`) || 'normal', // 'normal' | 'exemp' | 'medical'
    calendarCache: JSON.parse(localStorage.getItem('bunker_calendar_cache') || 'null'),
    threshold: 80, plannerBunks: {}, activePlannerDay: DAYS[new Date().getDay() - 1] || 'Mon',
    academics: { internals: null, gpa: null, cgpa: null, loaded: false }
};

function getAcademicYear(roll) { if (!roll || roll.length < 2) return null; const y = parseInt('20' + roll.substring(0, 2)), c = new Date().getFullYear(), m = new Date().getMonth() + 1; return Math.max(1, Math.min(5, (m >= 1 && m <= 5 ? c - 1 : c) - y + 1)); }
function getCourseType(roll) { if (!roll || roll.length < 3) return null; const l = roll.substring(2); if (l.length >= 2 && CONFIG.COURSE_CODES[l.substring(0, 2).toUpperCase()]) return CONFIG.COURSE_CODES[l.substring(0, 2).toUpperCase()]; return CONFIG.COURSE_CODES[l.charAt(0).toUpperCase()] || null; }
function getPlannerId(roll) { return CONFIG.PLANNER_MAP[`${getCourseType(roll)}_${getAcademicYear(roll)}`] || null; }

document.addEventListener('DOMContentLoaded', () => {
    // --- AUTO-LOGIN: Check for stored credentials ---
    const savedCreds = (() => { try { return JSON.parse(localStorage.getItem('bunker_credentials') || 'null'); } catch { return null; } })();
    const savedRoll = savedCreds?.roll;
    const cachedSubjects = savedRoll ? localStorage.getItem(`bunker_subjects_${savedRoll}`) : null;

    if (savedCreds && savedRoll && cachedSubjects) {
        // Restore full state from cache
        state.rollNumber = savedRoll;
        state.subjects = JSON.parse(cachedSubjects);
        state.timetable = JSON.parse(localStorage.getItem('bunker_timetable') || '{}');
        state.courseMapping = JSON.parse(localStorage.getItem('bunker_course_mapping') || '{}');
        state.college = localStorage.getItem('bunker_college') || 'PSGTECH';
        state.hasCalendar = localStorage.getItem('bunker_has_calendar') !== 'false';
        state.manual = JSON.parse(localStorage.getItem(`bunker_manual_${savedRoll}`) || '[]');
        state.includeManual = localStorage.getItem(`bunker_include_manual_${savedRoll}`) === 'true';
        state.viewManualAdjusted = localStorage.getItem(`bunker_view_manual_${savedRoll}`) === 'true';
        state.attendanceMode = localStorage.getItem(`bunker_att_mode_${savedRoll}`) || 'normal';
        const cachedCalendar = localStorage.getItem('bunker_calendar_cache');
        if (cachedCalendar) { try { ACADEMIC_DATA = JSON.parse(cachedCalendar); state.calendarCache = ACADEMIC_DATA; } catch { } }

        localStorage.setItem('bunker_roll', savedRoll);

        // Show dashboard immediately with cached data
        enterApp();
        // Start background sync
        backgroundSync(savedCreds.roll, savedCreds.password);
    } else {
        document.getElementById('login-view').classList.remove('hidden');
    }

    if (window.pwaManager) updateInstallUI();

    // Dismiss splash screen and reveal app
    setTimeout(() => {
        const splash = document.getElementById('premium-splash');
        const app = document.getElementById('app');
        if (splash) {
            splash.style.opacity = '0';
            splash.style.pointerEvents = 'none';
            setTimeout(() => splash.remove(), 700);
        }
        if (app) app.style.opacity = '1';
    }, 1200); // 1.2s delay for the animation to play out
});

async function backgroundSync(roll, password) {
    showSyncIndicator('syncing');
    try {
        const loginResponse = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: roll, password: password })
        });
        const loginData = await loginResponse.json();

        if (!loginData.success) {
            showSyncIndicator('offline');
            // Remains visible permanently until next successful sync or app restart
            return;
        }

        // Update state with fresh data
        state.subjects = loginData.subjects || state.subjects;
        state.timetable = loginData.timetable || state.timetable;
        state.courseMapping = loginData.course_mapping || state.courseMapping;
        state.college = loginData.college || state.college;
        state.hasCalendar = loginData.has_calendar !== false;

        // Persist fresh data
        localStorage.setItem('bunker_subjects', JSON.stringify(state.subjects));
        localStorage.setItem(`bunker_subjects_${roll}`, JSON.stringify(state.subjects));
        localStorage.setItem('bunker_timetable', JSON.stringify(state.timetable));
        localStorage.setItem('bunker_course_mapping', JSON.stringify(state.courseMapping));
        localStorage.setItem('bunker_college', state.college);
        localStorage.setItem('bunker_has_calendar', state.hasCalendar);
        localStorage.setItem('bunker_last_update', loginData.last_update || '');

        // Fetch calendar too
        try {
            const calRes = await fetch(`/api/calendar/${roll}`);
            const calData = await calRes.json();
            if (!calData.error) processCalendarData(calData, roll);
        } catch { }

        // Run cleanup with fresh last_update, then refresh UI
        cleanupManualEntries();
        renderSemesterHero(); renderWidgets(); renderSubjects(); initPlanner(); initManual();

        showSyncIndicator('done');
        setTimeout(() => hideSyncIndicator(), 2500);
    } catch (err) {
        console.error('Background sync error:', err);
        showSyncIndicator('offline');
        // Remains visible permanently until next successful sync or app restart
    }
}

function showSyncIndicator(status) {
    let el = document.getElementById('sync-indicator');
    if (!el) return;
    el.classList.remove('hidden', 'translate-y-[-20px]', 'opacity-0');

    // Add slide-down animation classes if not present
    if (!el.classList.contains('translate-y-0')) {
        el.className += ' translate-y-0 opacity-100';
    }

    const dot = el.querySelector('#sync-dot');
    const txt = el.querySelector('#sync-text');

    // Base premium classes for the pill (in-flow, no longer fixed top)
    const basePill = 'flex justify-center items-center gap-2.5 px-4 py-2 mt-4 mx-auto w-max rounded-full backdrop-blur-xl shadow-lg transition-all duration-500 border';

    if (status === 'syncing') {
        el.className = `${basePill} bg-indigo-500/10 border-indigo-500/20 shadow-indigo-500/10`;
        dot.className = 'w-1.5 h-1.5 rounded-full bg-indigo-400 animate-pulse shadow-[0_0_8px_rgba(129,140,248,0.8)]';
        txt.className = 'text-[10px] font-bold text-indigo-200 tracking-wide uppercase';
        txt.innerHTML = 'Syncing Data <span class="tracking-widest animate-pulse">...</span>';
    } else if (status === 'done') {
        el.className = `${basePill} bg-emerald-500/10 border-emerald-500/20 shadow-emerald-500/10`;
        dot.className = 'w-1.5 h-1.5 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.8)]';
        txt.className = 'text-[10px] font-bold text-emerald-200 tracking-wide uppercase';
        txt.innerText = 'Up to Date';
    } else if (status === 'offline') {
        el.className = `${basePill} bg-amber-500/10 border-amber-500/20 shadow-amber-500/10`;
        dot.className = 'w-1.5 h-1.5 rounded-full bg-amber-400 shadow-[0_0_8px_rgba(251,191,36,0.8)]';
        txt.className = 'text-[10px] font-bold text-amber-200 tracking-wide uppercase';
        txt.innerText = 'Offline Mode';
    }
}


function hideSyncIndicator() {
    const el = document.getElementById('sync-indicator');
    if (el) {
        // Slide up and fade out
        el.classList.add('translate-y-[-20px]', 'opacity-0');
        el.classList.remove('translate-y-0', 'opacity-100');
        setTimeout(() => el.classList.add('hidden'), 500); // Wait for transition
    }
}


document.getElementById('login-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const roll = document.getElementById('username').value.trim().toUpperCase();
    const password = document.getElementById('password').value.trim();

    if (roll.length !== 6 && roll.length !== 7) {
        document.getElementById('login-error').innerText = "Please enter valid roll number (6 or 7 digits)";
        document.getElementById('login-error').classList.remove('hidden');
        return;
    }

    document.getElementById('login-error').classList.add('hidden');
    document.getElementById('updating-overlay').classList.remove('hidden');

    try {
        const loginResponse = await fetch('/api/login', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ username: roll, password: password })
        });

        const loginData = await loginResponse.json();

        if (!loginData.success) {
            setTimeout(() => {
                document.getElementById('updating-overlay').classList.add('hidden');
                document.getElementById('login-error').innerText = loginData.error || "Login failed";
                document.getElementById('login-error').classList.remove('hidden');
            }, 1000);
            return;
        }

        // Store credentials for auto-login
        localStorage.setItem('bunker_credentials', JSON.stringify({ roll, password }));

        // Fetch calendar data
        const calendarResponse = await fetch(`/api/calendar/${roll}`);
        const calendarData = await calendarResponse.json();
        if (calendarData.error) console.warn('Calendar fetch failed:', calendarData.error);
        processCalendarData(calendarData, roll);

        // Store login data in state
        state.subjects = loginData.subjects || [];
        state.timetable = loginData.timetable || {};
        state.courseMapping = loginData.course_mapping || {};
        state.college = loginData.college || 'PSGTECH';
        state.hasCalendar = loginData.has_calendar !== false;

        localStorage.setItem('bunker_subjects', JSON.stringify(state.subjects));
        localStorage.setItem(`bunker_subjects_${roll}`, JSON.stringify(state.subjects));
        localStorage.setItem('bunker_timetable', JSON.stringify(state.timetable));
        localStorage.setItem('bunker_course_mapping', JSON.stringify(state.courseMapping));
        localStorage.setItem('bunker_college', state.college);
        localStorage.setItem('bunker_has_calendar', state.hasCalendar);
        localStorage.setItem('bunker_last_update', loginData.last_update || 'No data');

        // Load per-user manual and preferences (stored from previous sessions)
        state.rollNumber = roll;
        state.manual = JSON.parse(localStorage.getItem(`bunker_manual_${roll}`) || '[]');
        state.includeManual = localStorage.getItem(`bunker_include_manual_${roll}`) === 'true';
        state.viewManualAdjusted = localStorage.getItem(`bunker_view_manual_${roll}`) === 'true';
        state.attendanceMode = localStorage.getItem(`bunker_att_mode_${roll}`) || 'normal';

        setTimeout(() => {
            document.getElementById('updating-overlay').classList.add('hidden');
            enterApp();
        }, 50); // Lightning fast transition

    } catch (err) {
        console.error('Login error:', err);
        setTimeout(() => {
            document.getElementById('updating-overlay').classList.add('hidden');
            document.getElementById('login-error').innerText = "Connection failed. Please try again.";
            document.getElementById('login-error').classList.remove('hidden');
        }, 1000);
    }
});


function processCalendarData(data, roll) {
    const fullCalendar = [];
    if (data.calendar.holidays) data.calendar.holidays.forEach(h => fullCalendar.push({ name: h.name, date: h.date, type: 'Holiday' }));
    if (data.activities) data.activities.forEach(a => {
        let type = 'Event';
        const n = a.name.toLowerCase();
        if (n.includes('exam') || n.includes('test') || n.includes('assessment')) type = 'Exam';
        else if (n.includes('start') || n.includes('re-opening')) type = 'Start';
        else if (n.includes('last working')) type = 'End';
        fullCalendar.push({ name: a.name, date: a.date, type: type });
    });
    ACADEMIC_DATA = { name: data.name, startDate: data.startDate, lastDate: data.lastDate, fullCalendar: fullCalendar };
    state.rollNumber = roll; state.calendarCache = ACADEMIC_DATA;
    localStorage.setItem('bunker_roll', roll);
    localStorage.setItem('bunker_calendar_cache', JSON.stringify(ACADEMIC_DATA));

    if (state.subjects.length === 0) saveState();
}

// NEW: Load Cached Function
function loadCachedAttendance() {
    const roll = state.rollNumber;
    if (!roll) return;
    const cached = localStorage.getItem(`bunker_subjects_${roll}`);
    if (cached) {
        try {
            state.subjects = JSON.parse(cached);
            // Also update the generic key so it persists on reload until cleared
            localStorage.setItem('bunker_subjects', cached);

            // Full UI Refresh to enable Manual Tracking & Planner with restored data
            renderSemesterHero();
            renderWidgets();
            renderSubjects();
            initPlanner();
            initManual();

            showToast('Loaded previous attendance');
        } catch (e) {
            showToast('Failed to load cache', 'error');
        }
    }
}

function loadDemo() {
    document.getElementById('updating-overlay').classList.remove('hidden');
    setTimeout(() => {
        state.rollNumber = "DEMO";
        const today = new Date();
        ACADEMIC_DATA = {
            name: "Demo Semester",
            startDate: new Date(today.getFullYear(), 0, 1).toISOString(),
            lastDate: new Date(today.getFullYear(), 5, 30).toISOString(),
            fullCalendar: [
                { name: "Pongal", date: new Date(today.getFullYear(), 0, 14).toISOString(), type: 'Holiday' },
                { name: "Republic Day", date: new Date(today.getFullYear(), 0, 26).toISOString(), type: 'Holiday' },
                { name: "Independence Day", date: new Date(today.getFullYear(), 7, 15).toISOString(), type: 'Holiday' },
                { name: "Diwali", date: new Date(today.getFullYear(), 9, 20).toISOString(), type: 'Holiday' },
                { name: "Christmas", date: new Date(today.getFullYear(), 11, 25).toISOString(), type: 'Holiday' },
                { name: "Next Pongal", date: new Date(today.getFullYear() + 1, 0, 14).toISOString(), type: 'Holiday' },
                { name: "Demo Exam", date: new Date(today.getTime() + 86400000 * 10).toISOString(), type: 'Exam' }
            ]
        };
        state.subjects = [
            { code: "CS201", name: "Data Structures", attended: 28, total: 32 },
            { code: "MA203", name: "Applied Math III", attended: 18, total: 24 },
            { code: "CS205", name: "Computer Arch", attended: 15, total: 26 },
            { code: "HU201", name: "Economics", attended: 22, total: 22 },
            { code: "CS208", name: "Digital Logic", attended: 20, total: 28 }
        ];
        state.timetable = {
            "Mon": ["CS201", "CS205", "Free", "MA203"], "Tue": ["CS208", "CS201", "CS201", "HU201"],
            "Wed": ["CS205", "Free", "MA203", "CS208"], "Thu": ["MA203", "HU201", "CS205", "Free"], "Fri": ["CS208", "CS201", "CS205", "MA203"]
        };
        saveState();
        document.getElementById('updating-overlay').classList.add('hidden');
        enterApp();
    }, 1000);
}

// PWA UI Logic
function getDeviceName() {
    const ua = navigator.userAgent;
    // Check specific brands first
    if (/Nothing Phone/i.test(ua)) return 'Nothing Phone';
    if (/OnePlus/i.test(ua)) return 'OnePlus';
    if (/Realme|RMX/i.test(ua)) return 'Realme';
    if (/Oppo/i.test(ua)) return 'Oppo';
    if (/Vivo/i.test(ua)) return 'Vivo';
    if (/iQOO/i.test(ua)) return 'iQOO';
    if (/POCO/i.test(ua)) return 'POCO';

    // Redmi/Xiaomi Detection
    // Standard:
    if (/Redmi|HM|Note/i.test(ua) && /Xiaomi|Mi|Redmi/i.test(ua)) return 'Redmi';
    if (/Redmi/i.test(ua)) return 'Redmi';
    if (/Xiaomi|Mi |Mi-/i.test(ua)) return 'Xiaomi';

    // Specific Heuristic for User's Redmi Note 8 (Privacy UA: "Android 10; k")
    // This handles the case where manufacturer info is stripped
    if (/Android 10;\s*k\)/i.test(ua)) return 'Redmi';

    if (/Motorola|Moto/i.test(ua)) return 'Motorola';
    if (/Samsung|SM-|GT-/i.test(ua)) return 'Samsung';
    if (/Pixel/i.test(ua)) return 'Pixel';
    if (/iPhone/i.test(ua)) return 'iPhone';
    if (/iPad/i.test(ua)) return 'iPad';
    return 'Device';
}

function updateInstallUI() {
    if (!window.pwaManager) return;
    const isInstalled = window.pwaManager.isStandalone || window.pwaManager.isAppInstalled;
    const isIOS = window.pwaManager.isIOS;
    const canInstall = !!window.pwaManager.deferredPrompt;
    const prompt = document.getElementById('login-install-prompt');
    const settingBtn = document.getElementById('settings-install-btn');
    const installText = document.getElementById('install-text');

    // Personalize Text (Simple: Android vs iPhone)
    if (installText) {
        if (isIOS) {
            installText.textContent = 'Install on iPhone';
        } else {
            installText.textContent = 'Install Bunker.';
        }
    }

    // Login Page Prompt
    if (prompt) {
        if (isInstalled) {
            prompt.classList.add('hidden');
        } else {
            // ALWAYS SHOW if not installed for easier testing/access
            prompt.classList.remove('hidden');
        }
    }

    // Settings Button
    if (settingBtn) {
        if (isInstalled) {
            settingBtn.classList.add('hidden');
        } else {
            if (canInstall || isIOS) settingBtn.classList.remove('hidden');
            else settingBtn.classList.add('hidden');
        }
    }
}

function triggerInstall() {
    if (window.pwaManager.isIOS) {
        // Show iOS Instructions
        const modal = document.createElement('div');
        modal.className = "fixed inset-0 z-50 flex items-end justify-center bg-black/80 backdrop-blur-sm p-4 fade-in-up";
        modal.onclick = (e) => { if (e.target === modal) modal.remove(); };
        modal.innerHTML = `
                    <div class="bg-[#1c1c1e] w-full max-w-sm rounded-[2rem] p-6 pb-12 relative overflow-hidden text-center border border-white/10 shadow-2xl">
                        <div class="mx-auto w-16 h-1 bg-white/20 rounded-full mb-6"></div>
                        <img src="/static/icon.png" class="w-20 h-20 rounded-[1.2rem] mx-auto mb-4 shadow-2xl border border-white/10">
                        <h3 class="text-xl font-bold text-white mb-2">Install App</h3>
                        <p class="text-gray-400 text-sm mb-6 leading-relaxed">
                            For the best experience, open in <span class="text-blue-400 font-bold">Safari</span>.<br>
                            Tap <span class="text-blue-400 font-bold"><i class="fas fa-share-from-square"></i> Share</span> below and select <span class="text-white font-bold"><i class="fas fa-plus-square"></i> Add to Home Screen</span>.
                        </p>
                        <i class="fas fa-arrow-down text-blue-500 text-2xl animate-bounce"></i>
                    </div>
                 `;
        document.body.appendChild(modal);
    } else {
        // Android/Desktop Helper
        if (window.pwaManager.deferredPrompt) {
            window.pwaManager.deferredPrompt.prompt();
            window.pwaManager.deferredPrompt.userChoice.then((choice) => {
                if (choice.outcome === 'accepted') {
                    // User clicked "Install" in Chrome dialog
                    // Show helpful toast about installation process
                    showInstallationGuidance();
                }
                window.pwaManager.deferredPrompt = null;
                updateInstallUI();
            });
        } else {
            // No install prompt available - provide helpful feedback
            if (window.pwaManager.isStandalone || window.pwaManager.isAppInstalled) {
                showToast('App already installed! Check your home screen or apps', 'success');
            } else if (location.protocol === 'http:' && location.hostname !== 'localhost') {
                showToast('Install requires HTTPS. Deploy to production first!', 'error');
            } else {
                showToast('Install via browser menu (⋮ → Install app)', 'info');
            }
        }
    }
}

function showInstallationGuidance() {
    // Create beautiful installation guidance toast
    const toast = document.createElement('div');
    toast.className = "fixed top-4 left-1/2 -translate-x-1/2 z-[999] max-w-[90%] sm:max-w-md px-4";
    toast.id = 'install-guidance-toast';
    toast.style.opacity = '0';
    toast.style.transform = 'translate(-50%, -30px)';

    toast.innerHTML = `
        <div class="relative bg-[#0a0a0a]/98 backdrop-blur-md rounded-2xl p-4 shadow-2xl border border-white/5 flex items-center gap-3.5">
            <!-- Icon -->
            <div class="w-10 h-10 bg-indigo-500/10 rounded-xl flex items-center justify-center flex-shrink-0 ring-1 ring-indigo-500/20">
                <i class="fas fa-download text-indigo-400 text-sm" style="animation: floatIcon 3s ease-in-out infinite"></i>
            </div>
            
            <!-- Content -->
            <div class="flex-1 min-w-0">
                <h4 class="text-white font-medium text-[13px] leading-tight mb-0.5">Installing Bunker...</h4>
                <p class="text-gray-400 text-[11px] leading-tight truncate">Check notification bar for progress</p>
            </div>
            
            <!-- Close -->
            <button onclick="dismissInstallToast()" class="w-8 h-8 flex items-center justify-center rounded-lg text-gray-500 hover:text-white hover:bg-white/5 transition-colors">
                <i class="fas fa-times text-xs"></i>
            </button>
        </div>
    `;

    document.body.appendChild(toast);

    // Smooth entrance with bounce easing
    requestAnimationFrame(() => {
        toast.style.transition = 'all 0.5s cubic-bezier(0.34, 1.56, 0.64, 1)';
        toast.style.opacity = '1';
        toast.style.transform = 'translate(-50%, 0)';
    });

    // Auto-dismiss after 8 seconds
    setTimeout(() => dismissInstallToast(), 8000);
}

function dismissInstallToast() {
    const toast = document.getElementById('install-guidance-toast');
    if (toast) {
        toast.style.transition = 'all 0.3s ease-out';
        toast.style.opacity = '0';
        toast.style.transform = 'translate(-50%, -20px)';
        setTimeout(() => toast.remove(), 300);
    }
}

// Debug function removed for production

function showPrivacyPolicy() {
    if (typeof LEGAL_TEXT === 'undefined') return;

    // Prevent duplicate modals
    if (document.getElementById('legal-modal')) return;

    const modal = document.createElement('div');
    modal.className = "fixed inset-0 z-[100] flex items-end sm:items-center justify-center bg-black/80 backdrop-blur-sm p-0 sm:p-4 fade-in-up";
    modal.onclick = (e) => { if (e.target === modal) closeLegal(); };
    modal.id = 'legal-modal';

    modal.innerHTML = `
        <div class="bg-[#121212] w-full max-w-lg sm:rounded-[2rem] rounded-t-[2rem] h-[85vh] sm:h-[80vh] flex flex-col relative overflow-hidden shadow-2xl border border-white/10">
            <!-- Header -->
            <div class="p-6 border-b border-white/5 flex justify-between items-center bg-[#18181b]">
                <h3 class="text-lg font-bold text-white">Legal & Privacy</h3>
                <button onclick="closeLegal()" class="w-8 h-8 rounded-full bg-white/5 flex items-center justify-center text-gray-400 hover:text-white transition">
                    <i class="fas fa-times"></i>
                </button>
            </div>
            
            <!-- Content -->
            <div class="p-6 overflow-y-auto custom-scrollbar flex-1 pb-20">
                ${LEGAL_TEXT}
            </div>

            <!-- Bottom Fade -->
            <div class="absolute bottom-0 left-0 right-0 h-20 bg-gradient-to-t from-[#121212] to-transparent pointer-events-none"></div>
        </div>
    `;
    document.body.appendChild(modal);
    // Disable body scroll
    document.body.style.overflow = 'hidden';

    // Add Esc key support
    const handleEscape = (e) => {
        if (e.key === 'Escape') closeLegal();
    };
    document.addEventListener('keydown', handleEscape);
    modal.dataset.escListener = 'true';
}

function closeLegal() {
    const m = document.getElementById('legal-modal');
    if (m) {
        // Remove Esc listener if it exists
        if (m.dataset.escListener) {
            const handleEscape = (e) => {
                if (e.key === 'Escape') closeLegal();
            };
            document.removeEventListener('keydown', handleEscape);
        }

        m.classList.remove('fade-in-up');
        m.classList.add('fade-out-down');
        setTimeout(() => m.remove(), 200);

        // Restore scroll only if modal exists
        document.body.style.overflow = '';
    }
}

function enterApp() {
    // Re-load manual data for the correct user BEFORE cleanup
    const roll = state.rollNumber;
    if (roll) {
        state.manual = JSON.parse(localStorage.getItem(`bunker_manual_${roll}`) || '[]');
        state.includeManual = localStorage.getItem(`bunker_include_manual_${roll}`) === 'true';
        state.viewManualAdjusted = localStorage.getItem(`bunker_view_manual_${roll}`) === 'true';
        state.attendanceMode = localStorage.getItem(`bunker_att_mode_${roll}`) || 'normal';
    }

    // Now cleanup stale manual entries (entries covered by official update)
    cleanupManualEntries();
    const login = document.getElementById('login-view');
    const dash = document.getElementById('dashboard-view');
    const aurora = document.getElementById('aurora-bg');
    if (aurora) aurora.style.opacity = "0.25";
    if (typeof anime !== 'undefined') {
        anime({
            targets: login, opacity: 0, scale: 0.9, duration: 500, easing: 'easeInOutQuad',
            complete: () => {
                login.classList.add('hidden'); dash.classList.remove('hidden');
                initDashboard();
                anime({ targets: dash, opacity: [0, 1], scale: [1.05, 1], duration: 500, easing: 'easeOutQuad' });
            }
        });
    } else { login.classList.add('hidden'); dash.classList.remove('hidden'); initDashboard(); }
}

// Helper: Get 'Current' Date (Real or Simulated)
function getToday() {
    if (state.simulatedDate) return new Date(state.simulatedDate);
    return new Date();
}

// Demo Time Travel Handler
function updateSimDate(el) {
    if (!el.value) {
        state.simulatedDate = null;
    } else {
        state.simulatedDate = el.value; // Store YYYY-MM-DD string
    }
    initDashboard(); // Re-render everything with new "Today"
}

function renderSemesterHero() {
    const start = new Date(ACADEMIC_DATA.startDate);
    const end = new Date(ACADEMIC_DATA.lastDate);
    const today = getToday();
    const totalTime = end - start;
    const elapsed = today - start;
    let pct = Math.min(100, Math.max(0, (elapsed / totalTime) * 100));
    if (isNaN(pct)) pct = 0;

    const heroContainer = document.getElementById('hero-widget-container');

    // Check if calendar is available (PSG IAS workaround)
    if (!state.hasCalendar) {
        heroContainer.innerHTML = `
            <div class="glass-panel rounded-[32px] p-5 relative overflow-hidden border border-white/5 border-l-4" style="border-left-color: var(--primary);">
                 <div class="flex justify-between items-center h-full">
                    <div>
                        <h3 class="text-[9px] font-bold text-gray-400 uppercase tracking-widest mb-0.5">Academic Year</h3>
                        <div class="text-xs text-indigo-300 font-bold truncate max-w-[150px]">PSG IAS</div>
                    </div>
                    <div class="text-right">
                         <span class="text-2xl font-black text-white/50">---</span>
                    </div>
                 </div>
                 <div class="mt-4 flex justify-between text-[9px] font-bold text-gray-500 uppercase tracking-widest">
                    <span>---</span>
                    <span>---</span>
                 </div>
            </div>
        `;
        return;
    }

    heroContainer.innerHTML = `
                <div class="glass-panel rounded-[32px] p-5 relative overflow-hidden border border-white/5 border-l-4" style="border-left-color: var(--primary);">
                    <div class="flex justify-between items-end mb-4 relative z-10">
                        <div>
                            <h3 class="text-[9px] font-bold text-gray-400 uppercase tracking-widest mb-0.5">Progress</h3>
                            <div class="text-xs text-indigo-300 font-bold truncate max-w-[150px]">${ACADEMIC_DATA.name}</div>
                        </div>
                        <div class="text-right">
                            <span class="text-3xl font-black text-transparent bg-clip-text bg-gradient-to-br from-white to-gray-500 tracking-tighter">${Math.round(pct)}%</span>
                        </div>
                    </div>
                    <div class="relative h-2 w-full bg-white/5 rounded-full mb-2 overflow-hidden">
                        <div class="absolute left-0 top-0 bottom-0 rounded-full transition-all duration-1000 w-0" style="width:${pct}%; background: linear-gradient(90deg, var(--primary), var(--accent)); box-shadow: 0 0 20px var(--primary);"></div>
                    </div>
                    <div class="flex justify-between text-[9px] font-bold text-gray-500 uppercase tracking-widest">
                        <span>${start.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                        <span>${end.toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}</span>
                    </div>
                </div>
            `;
}

function initDashboard() {
    const today = getToday();
    document.getElementById('current-date').innerText = today.toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric' });

    // College Tag Logic
    const rollEl = document.getElementById('settings-roll');
    if (rollEl) {
        if (state.college === 'PSGIAS') {
            rollEl.innerHTML = `
                <span class="bg-indigo-500/20 text-indigo-300 px-2 py-0.5 rounded text-[10px] font-bold mr-2 border border-indigo-500/30">IAS BUNKER</span>
                ${state.rollNumber || "GUEST"}
            `;
        } else {
            rollEl.innerText = state.rollNumber || "GUEST";
        }
    }

    // Show Date Picker in Settings for Demo Mode
    const datePickerContainer = document.getElementById('demo-date-picker');
    if (datePickerContainer) {
        if (state.rollNumber === 'DEMO') {
            datePickerContainer.classList.remove('hidden');
            const iso = today.toISOString().split('T')[0];
            document.getElementById('sim-date-input').value = iso;
        } else {
            datePickerContainer.classList.add('hidden');
        }
    }

    // PHASE 1: Immediate (Critical UI) - Renders in <50ms
    renderSemesterHero();
    renderWidgets();
    renderSubjects();

    // PHASE 2: Deferred (Heavy Components) - Schedules after paint
    // Use setTimeout with 0ms to push to next event loop cycle
    // This allows browser to paint Phase 1 first
    setTimeout(() => {
        initAcademicCalendar();
        initPlanner();
        initManual();

        // Init nav only on first load
        if (!state.simulatedDate) switchTab('home', 0);
        if (window.pwaManager) updateInstallUI();
    }, 0);
}

function getSubjectStats(code) {
    const s = state.subjects.find(x => x.code === code); if (!s) return null;

    // Determine base attendance based on selected mode (PSG Tech only)
    let baseAtt = s.attended;
    let baseTot = s.total;

    if (state.college === 'PSGTECH') {
        if (state.attendanceMode === 'exemp' && s.pct_exemp !== undefined) {
            // With exemption: reduce total by exemption hours
            const exemp = s.exemption || 0;
            baseTot = Math.max(s.total - exemp, s.attended); // avoid negative
        } else if (state.attendanceMode === 'medical' && s.pct_medical !== undefined) {
            // With medical: use backend precomputed %, back-calculate effective total
            // pct_medical = attended / effective_total => effective_total = attended / (pct_medical/100)
            const pctMed = s.pct_medical || 0;
            baseTot = pctMed > 0 ? Math.round(s.attended / (pctMed / 100)) : s.total;
        }
    }

    // Only include manual stats if toggle is ON
    let p = 0;
    let b = 0;

    if (state.includeManual) {
        const m = state.manual.filter(x => x.code === code);
        p = m.filter(x => x.status === 'Present').length;
        b = m.filter(x => x.status === 'Absent').length;
    }

    const a = baseAtt + p, t = baseTot + p + b;
    return { ...s, att: a, tot: t, pct: t === 0 ? 0 : (a / t) * 100 };
}
function renderSubjects() {
    const c = document.getElementById('subject-list-container'); c.innerHTML = '';

    // Display last update date from backend (not today's date)
    const lastUpdate = localStorage.getItem('bunker_last_update') || 'No data';
    if (document.getElementById('last-updated-date')) document.getElementById('last-updated-date').innerText = lastUpdate;

    if (state.subjects.length === 0) {
        // Check if we have cached data for this user
        const roll = state.rollNumber;
        const hasCache = roll && localStorage.getItem(`bunker_subjects_${roll}`);

        let cacheBtn = '';
        if (hasCache) {
            cacheBtn = `
                        <button onclick="loadCachedAttendance()" class="mt-6 px-5 py-2.5 rounded-xl bg-white/10 hover:bg-white/20 border border-white/10 text-white text-xs font-bold transition-all active:scale-95 flex items-center gap-2 mx-auto">
                            <i class="fas fa-history text-indigo-400"></i> View Previous Attendance
                        </button>
                    `;
        }

        c.innerHTML = `
                    <div class="doll-container">
                        <svg class="ghost w-32 h-32" viewBox="0 0 100 120">
                            <path class="ghost-shadow" d="M30,115 h40 a1,0.3 0 0,0 0,0" />
                            <path class="ghost-body" d="M20,100 c0,-40 10,-80 30,-80 s30,40 30,80 c0,10 -10,10 -10,0 s-10,10 -20,0 s-10,10 -20,0 s-10,10 -10,0" />
                            <circle class="ghost-eyes" cx="40" cy="50" r="3" />
                            <circle class="ghost-eyes" cx="60" cy="50" r="3" />
                            <path class="ghost-eyes" d="M47,60 q3,3 6,0" fill="none" stroke="#1e1b4b" stroke-width="1.5" stroke-linecap="round" />
                        </svg>
                        <h3 class="text-white font-bold text-lg mt-4">Attendance Updating</h3>
                        <p class="text-gray-500 text-xs mt-1 text-center max-w-[200px] leading-relaxed">
                            Attendance data has been stopped or is currently being updated by the college.
                        </p>
                        <div class="mt-4 px-4 py-2 rounded-full bg-white/5 border border-white/10 text-[10px] text-indigo-300 font-bold uppercase tracking-widest animate-pulse">
                            Status: Pending
                        </div>
                        ${cacheBtn}
                    </div>
                `;
        return;
    }

    state.subjects.forEach((raw, i) => {
        const sub = getSubjectStats(raw.code), pct = sub.pct.toFixed(1);
        const pctVal = parseFloat(pct);

        // New Color Logic
        let col, bar, bor;
        if (pctVal === 100) { col = 'text-[#22C55E]'; bar = 'bg-[#22C55E]'; bor = 'border-[#22C55E]'; }
        else if (pctVal >= 95) { col = 'text-[#6366F1]'; bar = 'bg-[#6366F1]'; bor = 'border-[#6366F1]'; }
        else if (pctVal >= 85) { col = 'text-[#3B82F6]'; bar = 'bg-[#3B82F6]'; bor = 'border-[#3B82F6]'; }
        else if (pctVal >= 80) { col = 'text-[#FACC15]'; bar = 'bg-[#FACC15]'; bor = 'border-[#FACC15]'; }
        else if (pctVal >= 75) { col = 'text-[#F97316]'; bar = 'bg-[#F97316]'; bor = 'border-[#F97316]'; }
        else { col = 'text-[#EF4444]'; bar = 'bg-[#EF4444]'; bor = 'border-[#EF4444]'; }

        let stat, safe = Math.floor((4 * sub.att - 3 * sub.tot) / 3), need = Math.ceil(3 * sub.tot - 4 * sub.att);
        if (sub.pct >= 75) stat = safe > 0 ? `<div class="flex items-center gap-1.5 text-emerald-400 bg-emerald-500/10 px-3 py-1.5 rounded-xl border border-emerald-500/20"><i class="fas fa-shield-alt text-[10px]"></i><span class="text-[9px] font-black uppercase tracking-wider">Safe to bunk ${safe}</span></div>` : `<div class="flex items-center gap-1.5 text-amber-400 bg-amber-500/10 px-3 py-1.5 rounded-xl border border-amber-500/20"><i class="fas fa-exclamation-triangle text-[10px]"></i><span class="text-[9px] font-black uppercase tracking-wider">Danger Zone</span></div>`;
        else stat = need > 0 ? `<div class="flex items-center gap-1.5 text-rose-400 bg-rose-500/10 px-3 py-1.5 rounded-xl border border-rose-500/20"><i class="fas fa-arrow-trend-up text-[10px]"></i><span class="text-[9px] font-black uppercase tracking-wider">Need ${need} classes</span></div>` : `<div class="flex items-center gap-1.5 text-rose-400 bg-rose-500/10 px-3 py-1.5 rounded-xl border border-rose-500/20"><i class="fas fa-exclamation-circle text-[10px]"></i><span class="text-[9px] font-black uppercase tracking-wider">Critical</span></div>`;

        const d = document.createElement('div');
        d.className = `bg-white/[0.03] border border-white/5 backdrop-blur-xl shadow-xl rounded-[28px] overflow-hidden transition-all duration-300 mb-4 cursor-pointer active:scale-[0.98] border-l-4 ${bor}`;
        d.onclick = (e) => { if (!e.target.closest('button')) openSim(sub.code) };
        
        d.innerHTML = `
            <div class="p-5 relative overflow-hidden">
                <div class="absolute -right-4 -top-4 opacity-[0.03] pointer-events-none text-8xl text-white">
                    <i class="fas fa-book-open"></i>
                </div>
                <div class="flex justify-between items-start mb-4">
                    <div class="flex items-center gap-3 z-10 flex-1 pr-2 min-w-0">
                        <div class="min-w-0 flex-1">
                            <h4 class="font-bold text-white text-base leading-snug mb-1 drop-shadow-md tracking-wide truncate w-full block">${sub.name}</h4>
                            <div class="flex items-center gap-2 opacity-80 mt-1">
                                <span class="text-[10px] text-gray-400 font-bold tracking-widest uppercase">Attended: <span class="text-gray-200">${sub.att}/${sub.tot}</span></span>
                            </div>
                        </div>
                    </div>
                    <div class="flex flex-col items-end z-10 shrink-0 pl-2">
                        <span class="text-3xl font-black ${col} drop-shadow-[0_0_15px_rgba(255,255,255,0.1)] tracking-tighter">${pct}%</span>
                    </div>
                </div>
                <div class="w-full bg-black/40 h-2.5 rounded-full overflow-hidden mb-5 border border-white/5 shadow-inner">
                    <div class="h-full ${bar} rounded-full transition-all duration-1000 ease-out shadow-[0_0_10px_currentColor] opacity-90" style="width:${pct}%"></div>
                </div>
                <div class="flex justify-between items-center z-10 relative">
                    ${stat}
                    <button class="w-10 h-10 rounded-[14px] bg-indigo-500/10 border border-indigo-500/20 flex items-center justify-center text-indigo-400 hover:bg-indigo-500/20 transition-all active:scale-90 shadow-[0_0_15px_rgba(99,102,241,0.15)] group">
                        <i class="fas fa-magic text-sm group-hover:rotate-12 transition-transform duration-300"></i>
                    </button>
                </div>
            </div>`;
        c.appendChild(d);
    });
}
function renderWidgets() {
    const today = getToday(); today.setHours(0, 0, 0, 0);

    // Exam Widget Logic
    // Exam Widget Logic
    // For PSG IAS, show placeholder
    if (!state.hasCalendar) {
        document.getElementById('next-exam-name').innerText = "Exams";
        document.getElementById('next-exam-days-big').innerText = "--";
        if (document.getElementById('next-exam-date-sub')) document.getElementById('next-exam-date-sub').innerText = "Schedule pending";
    } else {
        const nEx = ACADEMIC_DATA.fullCalendar.sort((a, b) => new Date(a.date) - new Date(b.date)).find(e => e.type === 'Exam' && new Date(e.date) >= today);
        const exNameEl = document.getElementById('next-exam-name');
        const exDaysEl = document.getElementById('next-exam-days-big');
        const exDateSubEl = document.getElementById('next-exam-date-sub');
        if (nEx) {
            const diff = Math.ceil((new Date(nEx.date) - today) / (1000 * 60 * 60 * 24));
            exNameEl.innerText = nEx.name;
            exDaysEl.innerText = diff;
            if (exDateSubEl) exDateSubEl.innerText = new Date(nEx.date).toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        } else {
            exNameEl.innerText = "No Exams"; exDaysEl.innerText = "--"; if (exDateSubEl) exDateSubEl.innerText = "Relaxing";
        }
    }

    // Holiday Widget Logic (Dynamic Theme)
    const holContainer = document.getElementById('holiday-widget-container');

    if (!state.hasCalendar) {
        holContainer.className = `glass-panel rounded-[32px] p-5 h-44 relative overflow-hidden group active:scale-[0.98] transition-all theme-default`;
        holContainer.innerHTML = `
            <div class="absolute -right-4 -bottom-4 text-8xl opacity-10 transform rotate-12"><i class="fas fa-calendar-check"></i></div>
            <div class="relative z-10 flex flex-col h-full justify-between">
                <div class="flex justify-between items-start">
                    <div class="w-9 h-9 rounded-full flex items-center justify-center text-sm bg-black/20 text-white shadow-sm border border-white/10"><i class="fas fa-calendar-check"></i></div>
                </div>
                <div class="flex flex-col items-center justify-center flex-1 my-2">
                    <span class="text-4xl font-black text-white leading-none tracking-tighter">--</span>
                </div>
                <div class="text-center">
                    <h3 class="text-xs font-bold text-white truncate leading-tight">No Holidays</h3>
                </div>
            </div>
        `;
        return; // Stop holiday processing
    }

    const nHol = ACADEMIC_DATA.fullCalendar.sort((a, b) => new Date(a.date) - new Date(b.date)).find(e => e.type === 'Holiday' && new Date(e.date) >= today);

    if (nHol) {
        const d = new Date(nHol.date);
        const diff = Math.ceil((d - today) / (1000 * 60 * 60 * 24));

        let theme = 'theme-default';
        let icon = 'fa-umbrella-beach';
        let badgeClass = 'badge-default';
        let decoration = '<div class="float-item">✨</div>';

        const nameLower = nHol.name.toLowerCase();

        // PREMIUM HOLIDAY DECORATIONS (Floating & Smooth)
        // Default fallback
        let decors = ['✨', '🌟'];

        if (nameLower.includes('new year') && !nameLower.includes('tamil') && !nameLower.includes('telugu')) {
            theme = 'theme-newyear'; icon = 'fa-glass-cheers'; badgeClass = 'badge-newyear';
            decors = ['🎆', '🥂', '🎉'];
        }
        else if (nameLower.includes('pongal') || nameLower.includes('thiruvalluvar') || nameLower.includes('uzhavar') || nameLower.includes('tamil new year')) {
            theme = 'theme-pongal'; icon = 'fa-leaf'; badgeClass = 'badge-pongal';
            decors = ['🌾', '🏺', '☀️'];
        }
        else if (nameLower.includes('ugadi') || nameLower.includes('telugu')) {
            theme = 'theme-ugadi'; icon = 'fa-leaf'; badgeClass = 'badge-ugadi';
            decors = ['🥭', '🌿', '🍯'];
        }
        else if (nameLower.includes('onam')) {
            theme = 'theme-onam'; icon = 'fa-sun'; badgeClass = 'badge-onam';
            decors = ['🌼', '🛶', '🥥'];
        }
        else if (nameLower.includes('diwali') || nameLower.includes('deepavali')) {
            theme = 'theme-diwali'; icon = 'fa-fire'; badgeClass = 'badge-diwali';
            decors = ['🪔', '💥', '✨'];
        }
        else if (nameLower.includes('christmas')) {
            theme = 'theme-christmas'; icon = 'fa-tree'; badgeClass = 'badge-christmas';
            decors = ['🎅', '❄️', '🎁'];
        }
        else if (nameLower.includes('eid') || nameLower.includes('ramzan') || nameLower.includes('bakrid') || nameLower.includes('muharram') || nameLower.includes('milad')) {
            theme = 'theme-eid'; icon = 'fa-moon'; badgeClass = 'badge-eid';
            decors = ['🌙', '🕌', '✨'];
        }
        else if (nameLower.includes('republic') || nameLower.includes('independence') || nameLower.includes('gandhi')) {
            theme = 'theme-national'; icon = 'fa-flag'; badgeClass = 'badge-national';
            decors = ['🇮🇳', '🪁', '🦚'];
        }
        else if (nameLower.includes('ambedkar')) {
            theme = 'theme-ambedkar'; icon = 'fa-balance-scale'; badgeClass = 'badge-ambedkar';
            decors = ['⚖️', '📘', '🌸'];
        }
        else if (nameLower.includes('krishna') || nameLower.includes('gokulashtami')) {
            theme = 'theme-krishna'; icon = 'fa-om'; badgeClass = 'badge-krishna';
            decors = ['🪈', '🧈', '🦚'];
        }
        else if (nameLower.includes('ganesh') || nameLower.includes('vinayakar')) {
            theme = 'theme-ganesh'; icon = 'fa-om'; badgeClass = 'badge-ganesh';
            decors = ['🐘', '🥟', '🌸'];
        }
        else if (nameLower.includes('pooja') || nameLower.includes('navami') || nameLower.includes('dasami') || nameLower.includes('thaipoosam')) {
            theme = 'theme-pooja'; icon = 'fa-star'; badgeClass = 'badge-pooja';
            decors = ['🔱', '🌺', '🪔'];
        }
        else if (nameLower.includes('mahavir')) {
            theme = 'theme-mahavir'; icon = 'fa-hand-holding-heart'; badgeClass = 'badge-mahavir';
            decors = ['🕊️', '🧘', '✨'];
        }
        else if (nameLower.includes('good friday')) {
            theme = 'theme-goodfriday'; icon = 'fa-cross'; badgeClass = 'badge-goodfriday';
            decors = ['✝️', '🕯️', '🍇'];
        }
        else if (nameLower.includes('labour') || nameLower.includes('may day')) {
            theme = 'theme-labour'; icon = 'fa-hammer'; badgeClass = 'badge-labour';
            decors = ['🛠️', '⚙️', '👷'];
        }
        else if (nameLower.includes('holi')) {
            theme = 'theme-holi'; icon = 'fa-palette'; badgeClass = 'badge-holi';
            decors = ['🎈', '🎨', '💧'];
        }
        else if (nameLower.includes('raksha') || nameLower.includes('rakhi')) {
            theme = 'theme-rakhi'; icon = 'fa-hand-holding-heart'; badgeClass = 'badge-rakhi';
            decors = ['🧵', '🎁', '🍫'];
        }
        else if (nameLower.includes('guru') || nameLower.includes('nanak')) {
            theme = 'theme-guru'; icon = 'fa-om'; badgeClass = 'badge-guru';
            decors = ['👳', '🕯️', '✨'];
        }
        else if (nameLower.includes('exam')) {
            theme = 'theme-exam'; icon = 'fa-book'; badgeClass = 'badge-exam';
            decors = ['📝', '📚', '⏰'];
        }

        // Construct Floating HTML
        decoration = `
                    <div class="float-item delay-1" style="top:10%; right:10%">${decors[0]}</div>
                    <div class="float-item reverse" style="bottom:15%; left:10%">${decors[1]}</div>
                    <div class="float-item delay-2" style="top:40%; left:50%; opacity:0.3; transform:scale(0.8)">${decors[2] || decors[0]}</div>
                `;

        if (nameLower.includes('republic') || nameLower.includes('independence')) {
            decoration += '<div class="flag-wave"></div>'; // Add flag wave back
        }
        if (nameLower.includes('holi')) {
            decoration += '<div class="splash-item" style="top:10%; left:10%; background:#f0f;"></div><div class="splash-item" style="bottom:20%; right:20%; background:#0ff;"></div>';
        }

        holContainer.className = `glass-panel rounded-[32px] p-5 h-44 relative overflow-hidden group active:scale-[0.98] transition-all ${theme}`;

        holContainer.innerHTML = `
                    ${decoration}
                    <div class="relative z-10 flex flex-col h-full justify-between">
                        <div class="flex justify-between items-start">
                            <div class="w-10 h-10 rounded-full flex items-center justify-center text-lg bg-black/40 text-white shadow-sm border border-white/20 scale-105"><i class="fas ${icon}"></i></div>
                            <span class="widget-badge ${badgeClass}">Holiday</span>
                        </div>
                        <div class="flex flex-col items-center justify-center flex-1 my-2">
                            <span class="text-4xl font-black text-white leading-none tracking-tighter drop-shadow-md">${diff}</span>
                            <span class="text-[9px] font-bold text-white/70 uppercase tracking-widest mt-1">Days Left</span>
                        </div>
                        <div class="text-center">
                            <h3 class="text-xs font-bold text-white truncate leading-tight px-1">${nHol.name}</h3>
                        </div>
                    </div>
                `;
    } else {
        holContainer.className = `glass-panel rounded-[32px] p-5 h-44 relative overflow-hidden group active:scale-[0.98] transition-all theme-default`;
        holContainer.innerHTML = `
                    <div class="absolute -right-4 -bottom-4 text-8xl opacity-10 transform rotate-12"><i class="fas fa-calendar-check"></i></div>
                    <div class="relative z-10 flex flex-col h-full justify-between">
                        <div class="flex justify-between items-start">
                            <div class="w-9 h-9 rounded-full flex items-center justify-center text-sm bg-black/20 text-white shadow-sm border border-white/10"><i class="fas fa-calendar-check"></i></div>
                        </div>
                        <div class="flex flex-col items-center justify-center flex-1 my-2">
                            <span class="text-4xl font-black text-white leading-none tracking-tighter">--</span>
                        </div>
                        <div class="text-center">
                            <h3 class="text-xs font-bold text-white truncate leading-tight">No Holidays</h3>
                        </div>
                    </div>
                `;
    }
}
function initAcademicCalendar() {
    const l = document.getElementById('academic-list'); l.innerHTML = '';

    // Check if calendar is available
    if (!state.hasCalendar) {
        l.innerHTML = `
            <div class="text-center py-10">
                <div class="w-16 h-16 rounded-full bg-white/5 flex items-center justify-center mx-auto mb-4">
                    <i class="fas fa-calendar-times text-2xl text-gray-500"></i>
                </div>
                <h3 class="text-white font-bold mb-2">Calendar Unavailable</h3>
                <p class="text-gray-500 text-xs px-10">Academic calendar data is not available for PSG IAS.</p>
            </div>
        `;
        if (document.getElementById('cal-remaining-days')) document.getElementById('cal-remaining-days').innerText = "-- Days";
        return;
    }

    const today = getToday(); today.setHours(0, 0, 0, 0);
    const evts = ACADEMIC_DATA.fullCalendar.filter(e => new Date(e.date) >= today).sort((a, b) => new Date(a.date) - new Date(b.date));
    const endD = new Date(ACADEMIC_DATA.lastDate);
    let rem = Math.ceil((endD - today) / (1000 * 60 * 60 * 24)); if (rem < 0) rem = 0;
    if (document.getElementById('cal-remaining-days')) document.getElementById('cal-remaining-days').innerText = rem + ' Days';

    let cm = "";
    if (evts.length === 0) { l.innerHTML = '<div class="text-center text-gray-500 text-sm py-10">No upcoming events</div>'; return; }
    evts.forEach((e, i) => {
        const d = new Date(e.date), m = d.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
        if (m !== cm) { cm = m; l.innerHTML += `<div class="sticky top-0 z-30 bg-[#000000] py-2 mb-4 bg-opacity-95"><span class="text-[10px] font-black text-indigo-400 uppercase tracking-widest pl-4 border-l-2 border-indigo-500 ml-5">${m}</span></div>`; }
        const diff = Math.ceil((d - today) / (1000 * 60 * 60 * 24));
        const txt = diff === 0 ? "Today" : (diff === 1 ? "Tomorrow" : `${diff} days left`);
        const cls = diff <= 1 ? "text-indigo-300" : "text-gray-500";
        l.innerHTML += `<div class="relative pl-10 mb-6 group transition-all duration-300"><div class="absolute left-[19px] top-3 w-3 h-3 rounded-full bg-[#000000] border-2 border-indigo-500 z-10 transform -translate-x-1/2"></div><div class="glass-card p-5 rounded-[20px] flex items-center justify-between border-b border-white/5 active:scale-[0.98]"><div class="flex items-center gap-4"><div class="flex flex-col items-center justify-center min-w-[40px] text-center"><span class="text-[10px] font-bold uppercase text-gray-500">${d.toLocaleDateString('en-US', { weekday: 'short' })}</span><span class="text-2xl font-black text-white leading-none">${d.getDate()}</span></div><div><h4 class="font-bold text-sm text-white leading-tight">${e.name}</h4></div></div><div class="text-[10px] font-bold uppercase ${cls} whitespace-nowrap">${txt}</div></div></div>`;
    });
}
function initPlanner() {
    const t = document.getElementById('planner-days'), c = document.getElementById('planner-classes');
    const hasTimetable = state.timetable && Object.keys(state.timetable).length > 0 &&
        Object.values(state.timetable).some(d => d && d.length > 0 && d.some(x => x !== 'Free'));

    if (t) {
        if (!hasTimetable) {
            t.innerHTML = '';
            t.parentNode.style.display = 'none';
        } else {
            t.parentNode.style.display = 'flex';
            t.innerHTML = '';
            DAYS.forEach(d => {
                t.innerHTML += `<button onclick="state.activePlannerDay='${d}';state.selectedCards={};initPlanner()" class="flex-1 py-3 px-2 rounded-xl text-[10px] font-black uppercase tracking-widest transition-all ${d === state.activePlannerDay ? 'bg-indigo-600 text-white shadow-lg shadow-indigo-500/20' : 'bg-white/5 text-gray-400 border border-white/5'}">${d}</button>`;
            });
        }
    }

    if (c) {
        c.innerHTML = '';
        if (!hasTimetable) {
            c.innerHTML = `<div class="text-center py-10 opacity-50"><div class="text-4xl mb-4">📅</div><p class="text-xs font-bold uppercase tracking-widest text-gray-400">Timetable Not Found</p></div>`;
            return;
        }

        const cl = state.timetable[state.activePlannerDay] || [];
        if (!cl.length || cl.every(x => x === 'Free')) {
            c.innerHTML = '<div class="text-center py-10 text-gray-600 text-[10px] font-black uppercase tracking-widest">No classes scheduled</div>';
            updateSmartTrackerImpact();
            return;
        }

        cl.forEach((code, i) => {
            if (code === 'Free') return;
            const s = state.subjects.find(s => s.code === code) || { name: state.courseMapping[code] || code };

            const todayStr = new Date().toLocaleDateString();
            const todayEntries = state.manual.filter(m => m.code === code && new Date(m.timestamp || m.time).toLocaleDateString() === todayStr);
            const isDone = todayEntries.length > 0;
            const statusIcon = todayEntries.some(m => m.status === 'Present') ? 'fa-check-circle text-emerald-400' : (isDone ? 'fa-times-circle text-rose-400' : '');

            c.innerHTML += `
                <div class="glass-panel p-5 rounded-[28px] border-2 border-white/5 transition-all duration-300 relative overflow-hidden group
                    ${isDone ? 'opacity-90' : ''}">
                    
                    <div class="flex items-center justify-between">
                        <div class="flex-1 min-w-0 pr-4">
                            <div class="flex items-center gap-2 mb-2">
                                <span class="px-2 py-0.5 rounded-lg bg-indigo-500/10 text-indigo-400 text-[8px] font-black uppercase tracking-widest">Period ${i + 1}</span>
                                ${isDone ? `<span class="text-[10px]"><i class="fas ${statusIcon}"></i></span>` : ''}
                            </div>
                            <p class="text-[14px] font-bold text-white truncate">${s.name}</p>
                            <p class="text-[9px] text-gray-500 font-bold uppercase tracking-wider mt-1">${code}</p>
                        </div>
                        <div class="flex gap-2 relative z-10">
                            <button onclick="markTimetableAttendance('${code}', 'Present')" 
                                class="w-10 h-10 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center hover:bg-emerald-500/20 active:scale-95 transition">
                                <i class="fas fa-check text-xs"></i>
                            </button>
                            <button onclick="markTimetableAttendance('${code}', 'Absent')" 
                                class="w-10 h-10 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center hover:bg-rose-500/20 active:scale-95 transition">
                                <i class="fas fa-times text-xs"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;
        });

        updateSmartTrackerImpact();
    }
}

function toggleSmartTrackerPanel(btn) {
    const panel = document.getElementById('smart-tracker-panel');
    if (!panel) return;
    const isHidden = panel.classList.toggle('hidden');
    btn.innerHTML = isHidden
        ? '<i class="fas fa-chart-bar text-[8px]"></i> Show Stats'
        : '<i class="fas fa-chart-bar text-[8px]"></i> Hide Stats';
    if (!isHidden) updateSmartTrackerImpact();
}

function toggleSelectAllCards() {
    const cl = state.timetable[state.activePlannerDay] || [];
    const validCodes = [];
    cl.forEach((code) => {
        if (code !== 'Free') validCodes.push(code);
    });

    if (validCodes.length === 0) return;

    validCodes.forEach(code => {
        const s = state.subjects.find(x => x.code === code);
        const name = s ? s.name : (state.courseMapping[code] || code);
        state.manual.unshift({
            id: Date.now() + Math.random(),
            code, name,
            status: 'Present',
            time: new Date().toLocaleString(),
            timestamp: new Date().toISOString()
        });
    });

    state.selectedCards = {};
    saveState();
    renderSemesterHero(); renderWidgets(); renderSubjects(); initPlanner(); initManual();
    showToast(`✅ Marked entire day Attended (${validCodes.length} classes)!`, 'success');
}

function toggleCardSelection(id, code) {
    // Immediately mark as Attended on tap — no confirmation needed
    markTimetableAttendance(code, 'Present');
}


function markTimetableAttendance(code, status) {
    const s = state.subjects.find(x => x.code === code);
    const name = s ? s.name : (state.courseMapping[code] || code);

    state.manual.unshift({
        id: Date.now() + Math.random(),
        code: code,
        name: name,
        status: status,
        time: new Date().toLocaleString(),
        timestamp: new Date().toISOString()
    });

    // Deselect specifically for this subject if selected
    if (state.selectedCards) {
        Object.keys(state.selectedCards).forEach(id => {
            if (state.selectedCards[id] === code) delete state.selectedCards[id];
        });
    }

    saveState();
    renderSemesterHero(); renderWidgets(); renderSubjects(); initPlanner(); initManual();
    showToast(`✅ Marked ${status === 'Present' ? 'Attended' : 'Bunked'}: ${code}`, 'success');
}


function updateSmartTrackerImpact() {
    const l = document.getElementById('planner-impact-list');
    if (!l) return;

    const todayStr = new Date().toLocaleDateString();
    const todayManual = state.manual.filter(m => new Date(m.timestamp || m.time).toLocaleDateString() === todayStr);
    const todayManualCodes = [...new Set(todayManual.map(m => m.code))];

    if (todayManualCodes.length === 0) {
        l.innerHTML = '<div class="text-center py-2 text-gray-500 text-[10px] italic font-medium">Mark classes to see today\'s tracker stats</div>';
        return;
    }

    let html = '';
    todayManualCodes.forEach(code => {
        const s = getSubjectStats(code);
        if (!s) return;

        const histCount = todayManual.filter(m => m.code === code && m.status === 'Present').length;
        const histAbsent = todayManual.filter(m => m.code === code && m.status === 'Absent').length;

        const adjAtt = s.att + histCount;
        const adjTot = s.tot + histCount + histAbsent;
        const adjPct = adjTot === 0 ? 0 : (adjAtt / adjTot * 100);

        const diff = adjPct - s.pct;
        const diffStr = diff >= 0 ? `+${diff.toFixed(1)}%` : `${diff.toFixed(1)}%`;
        const diffCol = diff > 0.05 ? 'text-emerald-400' : diff < -0.05 ? 'text-rose-400' : 'text-gray-500';

        html += `
            <div class="flex justify-between items-center bg-white/5 p-4 rounded-2xl border border-white/5">
                <div class="flex-1 min-w-0 pr-3">
                    <p class="text-[11px] font-bold text-white truncate">${s.name}</p>
                    <span class="text-[9px] font-black text-emerald-400/70">${histCount} P / ${histAbsent} A Today</span>
                </div>
                <div class="text-right">
                    <p class="text-[13px] font-black text-indigo-300">${adjPct.toFixed(1)}%</p>
                    <p class="text-[9px] font-bold ${diffCol}">${diffStr}</p>
                </div>
            </div>
        `;
    });

    l.innerHTML = html;
}

function initManual() {
    const h = document.getElementById('manual-history');

    // Render subject comparison panel
    renderManualComparison();

    if (h) {
        h.innerHTML = state.manual.length ? '' : '<div class="text-center text-xs text-gray-700 italic py-4">No manual entries yet</div>';
        state.manual.slice(0, 3).forEach(m => {
            h.innerHTML += `<div class="flex justify-between items-center p-3 rounded-xl bg-white/5 border border-white/5 mb-2">
                <div class="flex items-center gap-3">
                    <div class="w-2 h-8 rounded-full ${m.status === 'Present' ? 'bg-emerald-500' : 'bg-rose-500'}"></div>
                    <div>
                        <p class="text-xs font-bold text-white">${m.name}</p>
                        <p class="text-[9px] text-gray-500 font-bold uppercase">${m.time.split(',')[0]}</p>
                    </div>
                </div>
                <button onclick="deleteManual(${m.id})" class="w-8 h-8 flex items-center justify-center rounded-full text-gray-600 hover:bg-white/10 hover:text-white transition"><i class="fas fa-trash"></i></button>
            </div>`;
        });
    }
}

function toggleManualView(el) {
    state.viewManualAdjusted = el.checked;
    localStorage.setItem(`bunker_view_manual_${state.rollNumber}`, state.viewManualAdjusted);
    renderManualComparison();
    showToast(state.viewManualAdjusted ? 'Showing manual-adjusted view' : 'Showing original attendance');
}

function renderManualComparison() {
    const container = document.getElementById('manual-comparison-container');
    if (!container) return;

    if (state.subjects.length === 0) {
        container.innerHTML = '';
        return;
    }

    // Helper: compute base stats honoring the current attendance mode (no manual)
    function getBaseStats(sub) {
        let baseAtt = sub.attended;
        let baseTot = sub.total;
        if (state.college === 'PSGTECH') {
            if (state.attendanceMode === 'exemp') {
                baseTot = Math.max(sub.total - (sub.exemption || 0), sub.attended);
            } else if (state.attendanceMode === 'medical') {
                const pctMed = sub.pct_medical || 0;
                baseTot = pctMed > 0 ? Math.round(sub.attended / (pctMed / 100)) : sub.total;
            }
        }
        return { baseAtt, baseTot };
    }

    const modeLabel = { normal: 'Official', exemp: '+Exemption', medical: '+Medical' };
    const officialLabel = modeLabel[state.attendanceMode] || 'Official';

    // ALWAYS show manual-adjusted side-by-side comparison
    const hasManual = state.manual.length > 0;
    let html = `<div class="mb-2">
        <p class="text-[9px] font-bold text-gray-600 uppercase tracking-widest mb-3 ml-1">Attendance Comparison <span class="text-violet-400 ml-1">(${officialLabel} vs Manual)</span></p>`;

    if (!hasManual) {
        html += `<div class="text-center text-xs text-gray-700 italic py-4">Add manual entries to see comparison</div>`;
    } else {
        state.subjects.forEach(sub => {
            const { baseAtt, baseTot } = getBaseStats(sub);
            const origPct = baseTot === 0 ? 0 : (baseAtt / baseTot * 100);

            // Apply manual adjustments on top of mode-aware base
            const manualEntries = state.manual.filter(x => x.code === sub.code);
            const manualPresent = manualEntries.filter(x => x.status === 'Present').length;
            const manualAbsent = manualEntries.filter(x => x.status === 'Absent').length;
            const adjAtt = baseAtt + manualPresent;
            const adjTot = baseTot + manualPresent + manualAbsent;
            const adjPct = adjTot === 0 ? 0 : (adjAtt / adjTot * 100);

            const origStr = origPct.toFixed(1);
            const adjStr = adjPct.toFixed(1);
            const diff = adjPct - origPct;
            const diffStr = diff >= 0 ? `+${diff.toFixed(1)}%` : `${diff.toFixed(1)}%`;
            const diffCol = diff > 0.05 ? 'text-emerald-400' : diff < -0.05 ? 'text-rose-400' : 'text-gray-500';
            const origCol = origPct >= 75 ? 'text-gray-400' : 'text-rose-400/70';
            const adjCol = adjPct >= 75 ? 'text-violet-400' : 'text-rose-400';

            html += `<div class="p-3 rounded-xl bg-white/5 border border-white/5 mb-2">
                <p class="text-xs font-bold text-white truncate mb-2">${sub.name}</p>
                <div class="flex items-center justify-between">
                    <div class="text-center">
                        <p class="text-[9px] text-gray-500 uppercase tracking-wider mb-0.5">${officialLabel}</p>
                        <p class="text-sm font-black ${origCol}">${origStr}%</p>
                        <p class="text-[9px] text-gray-600">${baseAtt}/${baseTot}</p>
                    </div>
                    <div class="flex flex-col items-center">
                        <i class="fas fa-arrow-right text-gray-700 text-xs mb-1"></i>
                        <span class="text-[10px] font-black ${diffCol}">${diffStr}</span>
                    </div>
                    <div class="text-center">
                        <p class="text-[9px] text-violet-400 uppercase tracking-wider mb-0.5">With Manual</p>
                        <p class="text-sm font-black ${adjCol}">${adjStr}%</p>
                        <p class="text-[9px] text-gray-600">${adjAtt}/${adjTot}</p>
                    </div>
                </div>
            </div>`;
        });
    }
    html += '</div>';
    container.innerHTML = html;
}


function toggleManualImpact(el) {
    if (el) state.includeManual = el.checked;
    else state.includeManual = !state.includeManual;

    saveState();

    // Update all UI components to reflect changes
    renderSemesterHero();
    renderWidgets();
    renderSubjects();
    initPlanner(); // Planner might show impact stats if we add that later

    // Feedback
    if (state.includeManual) {
        showToast('Manual entries included in attendance');
    } else {
        showToast('Manual entries excluded from attendance');
    }
}

function cleanupManualEntries() {
    // Logic: Remove local manual entries if their date is <= official last update
    const lastUpdateStr = localStorage.getItem('bunker_last_update');
    if (!lastUpdateStr || lastUpdateStr === 'No data') return;

    // Try parsing various formats
    let lastUpdateDate = new Date(lastUpdateStr);
    if (isNaN(lastUpdateDate.getTime())) {
        // If standard parse fails, try "DD-MM-YYYY" or "DD/MM/YYYY" common in India
        const parts = lastUpdateStr.split(/[-/]/);
        if (parts.length === 3) {
            // Assume DD-MM-YYYY
            lastUpdateDate = new Date(`${parts[2]}-${parts[1]}-${parts[0]}`);
        }
    }

    if (isNaN(lastUpdateDate.getTime())) return; // Failed to parse

    // Set to start of the day so that manual entries tracked TODAY are successfully kept
    // and aren't aggressively deleted immediately upon page reload.
    lastUpdateDate.setHours(0, 0, 0, 0);

    const initialCount = state.manual.length;

    // Filter: Keep entries NEWER than last update
    state.manual = state.manual.filter(m => {
        let entryDate;
        if (m.timestamp) {
            entryDate = new Date(m.timestamp);
        } else {
            // Backwards compatibility for old entries (try parsing locale string)
            entryDate = new Date(m.time);
            if (isNaN(entryDate.getTime())) return true; // Keep safely if unknown
        }
        return entryDate > lastUpdateDate;
    });

    if (state.manual.length < initialCount) {
        // Cleanup completed silently
        saveState();
        initManual(); // Refresh UI if checking
    }
}

function deleteManual(id) {
    state.manual = state.manual.filter(x => x.id !== id);
    saveState();
    // Update UI components without switching tab
    renderSemesterHero(); renderWidgets(); renderSubjects(); initPlanner(); initManual();
}

function switchTab(id, index) {
    // Get current active tab
    const currentTab = document.querySelector('.tab-content.active');
    const newTab = document.getElementById(`tab-${id}`);

    // If switching to the same tab, do nothing
    if (currentTab === newTab) return;

    // Smooth transition: fade out current, then fade in new
    if (currentTab) {
        currentTab.style.opacity = '0';
        currentTab.style.transform = 'translateY(10px)';

        setTimeout(() => {
            currentTab.classList.remove('active');
            newTab.classList.add('active');

            // Reset and animate new tab
            requestAnimationFrame(() => {
                newTab.style.opacity = '0';
                newTab.style.transform = 'translateY(10px)';

                requestAnimationFrame(() => {
                    newTab.style.opacity = '1';
                    newTab.style.transform = 'translateY(0)';
                });
            });
        }, 200); // Wait for fade out
    } else {
        // First load
        newTab.classList.add('active');
        newTab.style.opacity = '1';
        newTab.style.transform = 'translateY(0)';
    }

    // New Nav Logic
    const navItems = document.querySelectorAll('.nav-item');
    navItems.forEach(e => e.classList.remove('active'));
    document.getElementById(`nav-${id}`).classList.add('active');

    let t = "Dashboard";
    if (id === 'home') { const td = new Date(); const ev = ACADEMIC_DATA.fullCalendar.find(e => new Date(e.date).toDateString() === td.toDateString()); if (ev) t = ev.type === 'Holiday' ? "Holiday! 🌴" : ev.type === 'Exam' ? "Exam Day! 🍀" : "Busy Day! 📚"; else if (td.getDay() === 0 || td.getDay() === 6) t = "Weekend Vibes 🎉"; }
    else if (id === 'calendar') t = "Timeline"; else if (id === 'planner') t = "Smart Tracker";
    else if (id === 'academics') {
        t = "Academics";
        if (state.academics && !state.academics.loaded) {
            setTimeout(() => loadAcademics(), 150);
        }
    }
    document.getElementById('greeting-text').innerText = t;
}
function togglePassword() { const i = document.getElementById('password'); i.type = i.type === 'password' ? 'text' : 'password'; }

function toggleSettings() {
    const m = document.getElementById('settings-modal'), p = document.getElementById('settings-panel'), b = document.getElementById('settings-backdrop');
    if (m.classList.contains('hidden')) {
        m.classList.remove('hidden');
        requestAnimationFrame(() => {
            b.classList.remove('opacity-0');
            p.classList.remove('translate-y-full');
        });
        // Sync attendance mode button states
        const attModeContainer = document.getElementById('att-mode-container');
        if (attModeContainer) {
            // Hide for PSG IAS (they don't have exemption types)
            attModeContainer.style.display = state.college === 'PSGIAS' ? 'none' : '';
        }
        ['normal', 'exemp', 'medical'].forEach(m => {
            const btn = document.getElementById(`att-mode-${m}`);
            if (!btn) return;
            btn.className = m === state.attendanceMode
                ? 'flex-1 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider transition bg-indigo-600 text-white shadow'
                : 'flex-1 py-2 rounded-xl text-[10px] font-bold uppercase tracking-wider transition bg-white/5 text-gray-400 border border-white/5';
        });

        // Sync include manual toggle
        const incToggle = document.getElementById('settings-include-manual');
        if (incToggle) incToggle.checked = state.includeManual;
    } else {
        p.classList.add('translate-y-full');
        b.classList.add('opacity-0');
        setTimeout(() => m.classList.add('hidden'), 300);
    }
}
function setAttendanceMode(mode) {
    state.attendanceMode = mode;
    saveState();
    // Update button styles
    ['normal', 'exemp', 'medical'].forEach(m => {
        const btn = document.getElementById(`att-mode-${m}`);
        if (btn) {
            btn.className = m === mode
                ? 'flex-1 py-2 rounded-xl text-[10px] font-black uppercase tracking-wider transition bg-indigo-600 text-white shadow'
                : 'flex-1 py-2 rounded-xl text-[10px] font-bold uppercase tracking-wider transition bg-white/5 text-gray-400 border border-white/5';
        }
    });
    // Re-render subjects with new mode — including the manual comparison panel
    renderSemesterHero(); renderWidgets(); renderSubjects(); initPlanner();
    renderManualComparison(); // Sync manual comparison to new mode
    const labels = { normal: 'Official Attendance', exemp: 'With Exemption', medical: 'With Medical' };
    showToast(`Mode: ${labels[mode]}`);
}

function saveState() {
    localStorage.setItem('bunker_subjects', JSON.stringify(state.subjects));
    localStorage.setItem('bunker_timetable', JSON.stringify(state.timetable));
    if (state.rollNumber) {
        localStorage.setItem(`bunker_manual_${state.rollNumber}`, JSON.stringify(state.manual));
        localStorage.setItem(`bunker_include_manual_${state.rollNumber}`, state.includeManual);
        localStorage.setItem(`bunker_view_manual_${state.rollNumber}`, state.viewManualAdjusted);
        localStorage.setItem(`bunker_att_mode_${state.rollNumber}`, state.attendanceMode);
    }
    localStorage.setItem('bunker_roll', state.rollNumber);
}
function logout() {
    // Smart Logout: Clear session but keep manual entries and preferences
    const allKeys = Object.keys(localStorage);
    allKeys.forEach(key => {
        // Keep roll-specific cached subjects
        if (key.startsWith('bunker_subjects_')) return;
        // Keep manual tracking entries
        if (key.startsWith('bunker_manual_')) return;
        // Keep per-user preferences
        if (key.startsWith('bunker_include_manual_')) return;
        if (key.startsWith('bunker_view_manual_')) return;
        if (key.startsWith('bunker_att_mode_')) return;
        // CLEAR credentials → forces login screen on next open
        // (all the above keys allow user to quickly log back in and restore state)
        localStorage.removeItem(key);
    });
    location.reload();
}
function showToast(msg, t = 'info') { const e = document.createElement('div'), c = t === 'error' ? 'bg-rose-500' : 'bg-white text-black'; e.className = `px-5 py-3 rounded-2xl text-xs font-bold shadow-2xl flex items-center gap-3 transform translate-y-[-20px] opacity-0 transition-all duration-300 ${c}`; e.innerHTML = `<i class="fas fa-${t === 'error' ? 'exclamation-circle' : 'check-circle'}"></i> ${msg}`; document.getElementById('toast-container').appendChild(e); requestAnimationFrame(() => e.classList.remove('translate-y-[-20px]', 'opacity-0')); setTimeout(() => { e.classList.add('opacity-0', 'translate-y-[-10px]'); setTimeout(() => e.remove(), 300); }, 2500); }

// SIMULATOR FUNCTIONS
let simSubject = null;
let simAddAttend = 0;
let simAddBunk = 0;

function openSim(code) {
    simSubject = state.subjects.find(s => s.code === code);
    if (!simSubject) return;

    simAddAttend = 0;
    simAddBunk = 0;

    document.getElementById('sim-subject').innerText = simSubject.name;
    document.getElementById('val-attend').innerText = "0";
    document.getElementById('val-bunk').innerText = "0";

    updateSimUI();

    const m = document.getElementById('sim-modal');
    const p = document.getElementById('sim-panel');
    const b = document.getElementById('sim-backdrop');

    m.classList.remove('hidden');
    requestAnimationFrame(() => {
        b.classList.remove('opacity-0');
        p.classList.remove('opacity-0', 'scale-95');
        p.classList.add('scale-100');
    });
}

function closeSim() {
    const m = document.getElementById('sim-modal');
    const p = document.getElementById('sim-panel');
    const b = document.getElementById('sim-backdrop');

    b.classList.add('opacity-0');
    p.classList.add('opacity-0', 'scale-95');
    p.classList.remove('scale-100');

    setTimeout(() => {
        m.classList.add('hidden');
    }, 300);
}

function updateSim(type, change) {
    if (type === 'attend') {
        simAddAttend += change;
        if (simAddAttend < 0) simAddAttend = 0;
        document.getElementById('val-attend').innerText = simAddAttend;
    } else {
        simAddBunk += change;
        if (simAddBunk < 0) simAddBunk = 0;
        document.getElementById('val-bunk').innerText = simAddBunk;
    }
    updateSimUI();
}

function updateSimUI() {
    if (!simSubject) return;
    const stats = getSubjectStats(simSubject.code);
    const newAtt = stats.att + simAddAttend;
    const newTot = stats.tot + simAddAttend + simAddBunk;
    const pct = newTot === 0 ? 0 : (newAtt / newTot) * 100;

    const ring = document.getElementById('sim-ring');
    const pctText = document.getElementById('sim-pct');
    const diffText = document.getElementById('sim-diff');

    // Reduced font size to fit 100% inside ring
    pctText.innerText = pct.toFixed(1) + '%';
    if (pct >= 100) {
        pctText.classList.remove('text-6xl');
        pctText.classList.add('text-5xl');
    } else {
        pctText.classList.remove('text-5xl');
        pctText.classList.add('text-6xl');
    }

    // C = 2 * PI * 90 = 565.48
    const offset = 565 - (565 * pct / 100);
    ring.style.strokeDashoffset = offset;

    // Color Logic
    const pVal = parseFloat(pct.toFixed(1));
    let color;
    if (pVal === 100) color = '#22C55E';
    else if (pVal >= 95) color = '#6366F1';
    else if (pVal >= 85) color = '#3B82F6';
    else if (pVal >= 80) color = '#FACC15';
    else if (pVal >= 75) color = '#F97316';
    else color = '#EF4444';

    ring.style.stroke = color;
    // Add dynamic glow to ring
    ring.style.filter = `drop-shadow(0 0 8px ${color})`;

    pctText.style.color = color;

    const diff = pct - stats.pct;
    if (Math.abs(diff) < 0.1) {
        diffText.innerText = "Current";
        diffText.className = "text-[10px] font-bold px-3 py-1 rounded-full bg-white/5 mt-2 uppercase tracking-wide border border-white/5";
        diffText.style.color = "#9CA3AF";
    } else if (diff > 0) {
        diffText.innerText = `+${diff.toFixed(1)}%`;
        diffText.className = "text-[10px] font-bold px-3 py-1 rounded-full bg-emerald-500/10 mt-2 uppercase tracking-wide border border-emerald-500/20";
        diffText.style.color = "#34D399";
    } else {
        diffText.innerText = `${diff.toFixed(1)}%`;
        diffText.className = "text-[10px] font-bold px-3 py-1 rounded-full bg-rose-500/10 mt-2 uppercase tracking-wide border border-rose-500/20";
        diffText.style.color = "#FB7185";
    }
}

// BULK ATTENDANCE & HISTORY


function showFullHistory() {
    const m = document.getElementById('history-modal'), p = document.getElementById('history-panel'),
        b = document.getElementById('history-backdrop'), c = document.getElementById('full-history-content'),
        count = document.getElementById('history-count');

    if (!m || !c) return;

    // Group by date
    const groups = {};
    state.manual.forEach(entry => {
        const date = new Date(entry.timestamp || entry.time).toLocaleDateString(undefined, {
            weekday: 'long', year: 'numeric', month: 'long', day: 'numeric'
        });
        if (!groups[date]) groups[date] = [];
        groups[date].push(entry);
    });

    let html = '';
    const sortedDates = Object.keys(groups).sort((a, b) => new Date(b) - new Date(a));

    if (sortedDates.length === 0) {
        html = '<div class="text-center py-20 opacity-50"><div class="text-4xl mb-4">📜</div><p class="text-xs font-bold uppercase tracking-widest text-gray-500">No History Yet</p></div>';
    } else {
        sortedDates.forEach(date => {
            html += `<div class="mb-8">
                <div class="flex items-center gap-3 mb-4">
                    <div class="h-px flex-1 bg-white/5"></div>
                    <p class="text-[9px] font-black text-gray-600 uppercase tracking-[0.2em] whitespace-nowrap">${date}</p>
                    <div class="h-px flex-1 bg-white/5"></div>
                </div>
                <div class="space-y-3">`;
            groups[date].forEach(m => {
                const timeStr = new Date(m.timestamp || m.time).toLocaleTimeString(undefined, {
                    hour: '2-digit', minute: '2-digit'
                });
                html += `<div class="p-4 rounded-[24px] bg-white/[0.03] border border-white/5 flex justify-between items-center group hover:bg-white/[0.06] transition-colors">
                    <div class="flex items-center gap-4">
                        <div class="w-10 h-10 rounded-2xl ${m.status === 'Present' ? 'bg-emerald-500/10 text-emerald-500' : 'bg-rose-500/10 text-rose-500'} flex items-center justify-center text-sm">
                            <i class="fas fa-${m.status === 'Present' ? 'check' : 'times'}"></i>
                        </div>
                        <div class="max-w-[180px]">
                            <p class="text-xs font-bold text-white truncate">${m.name}</p>
                            <div class="flex items-center gap-2 mt-0.5">
                                <span class="text-[9px] text-gray-500 uppercase font-black">${m.code}</span>
                                <span class="w-0.5 h-0.5 rounded-full bg-gray-700"></span>
                                <span class="text-[9px] text-gray-500 font-bold">${timeStr}</span>
                            </div>
                        </div>
                    </div>
                    <button onclick="deleteManual(${m.id}); showFullHistory();" 
                        class="w-10 h-10 flex items-center justify-center rounded-xl text-gray-600 hover:bg-rose-500/10 hover:text-rose-500 transition-all opacity-0 group-hover:opacity-100">
                        <i class="fas fa-trash-alt text-xs"></i>
                    </button>
                </div>`;
            });
            html += `</div></div>`;
        });
    }

    count.innerText = `${state.manual.length} Total Entries`;
    c.innerHTML = html;

    m.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    requestAnimationFrame(() => {
        b.classList.remove('opacity-0');
        p.classList.remove('translate-y-full');
    });
}

function closeHistory() {
    const m = document.getElementById('history-modal'), p = document.getElementById('history-panel'),
        b = document.getElementById('history-backdrop');
    if (!p) return;
    p.classList.add('translate-y-full');
    b.classList.add('opacity-0');
    document.body.style.overflow = '';
    setTimeout(() => m.classList.add('hidden'), 300);
}

// ================================================================
// ACADEMICS PAGE
// ================================================================

let acadActiveTab = 'internals';


function getAuthToken() {
    // 'bunker_credentials' is stored at login as {roll, password}
    const creds = localStorage.getItem('bunker_credentials');
    return creds || null;
}

function switchAcadTab(tab) {
    acadActiveTab = tab;
    const tabs = ['internals', 'results'];
    tabs.forEach(t => {
        const btn = document.getElementById(`acad-tab-${t}`);
        const panel = document.getElementById(`acad-panel-${t}`);
        if (!btn || !panel) return;
        if (t === tab) {
            btn.className = 'flex-1 py-2.5 rounded-[18px] text-[10px] font-black uppercase tracking-widest transition-all bg-indigo-600 text-white shadow-lg';
            panel.classList.remove('hidden');
        } else {
            btn.className = 'flex-1 py-2.5 rounded-[18px] text-[10px] font-black uppercase tracking-widest transition-all bg-white/5 text-gray-400 border border-white/5';
            panel.classList.add('hidden');
        }
    });
}

async function loadAcademics(force = false) {
    if (state.academics.loaded && !force) return;

    // PSG IAS doesn't have CA Marks / GPA pages on eCampus
    if (state.college === 'PSGIAS') {
        document.getElementById('acad-loading')?.classList.add('hidden');
        showAcadError('Academic data (Internals / GPA / CGPA) is only available for PSG Tech students.');
        return;
    }

    // Show loading
    const panels = ['internals', 'results'];
    panels.forEach(p => document.getElementById(`acad-panel-${p}`)?.classList.add('hidden'));
    document.getElementById('acad-error')?.classList.add('hidden');
    document.getElementById('acad-loading')?.classList.remove('hidden');

    const authToken = getAuthToken();
    if (!authToken) {
        showAcadError('Please log in with valid credentials to view academic data.');
        return;
    }

    try {
        const [internalsRes, gpaRes, cgpaRes] = await Promise.all([
            fetch('/api/internals', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ auth_token: authToken }) }),
            fetch('/api/gpa', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ auth_token: authToken }) }),
            fetch('/api/cgpa', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ auth_token: authToken }) })
        ]);

        const internals = await internalsRes.json();
        const gpa = await gpaRes.json();
        const cgpa = await cgpaRes.json();

        if (internals.error || gpa.error || cgpa.error) {
            showAcadError(internals.error || gpa.error || cgpa.error || 'Failed to load academic data.');
            return;
        }

        state.academics = { internals, gpa, cgpa, loaded: true };

        document.getElementById('acad-loading')?.classList.add('hidden');

        renderInternals(internals);
        renderGPA(gpa);
        renderCGPA(cgpa);

        switchAcadTab(acadActiveTab);

    } catch (err) {
        showAcadError('Network error. Make sure you are connected.');
    }
}

function showAcadError(msg) {
    document.getElementById('acad-loading')?.classList.add('hidden');
    const errEl = document.getElementById('acad-error');
    const msgEl = document.getElementById('acad-error-msg');
    if (errEl) errEl.classList.remove('hidden');
    if (msgEl) msgEl.textContent = msg;
}

// ---- INTERNALS ----
function renderInternals(internals) {
    const list = document.getElementById('internals-list');
    const statusEl = document.getElementById('internals-status');
    if (!list) return;

    // Filter out subjects without relevant data (labs with no marks yet, etc.)
    const mainSubjects = internals.filter(s => s.total !== '' || s.row_data.some(v => v && v !== '*' && v !== ''));

    // Count updated subjects
    const withTotals = mainSubjects.filter(s => {
        const t = parseFloat(s.total);
        return !isNaN(t);
    });
    if (withTotals.length > 0) {
        if (statusEl) statusEl.textContent = `${withTotals.length} of ${mainSubjects.length} subjects updated`;
    } else {
        if (statusEl) statusEl.textContent = 'Marks not yet entered';
    }

    if (mainSubjects.length === 0) {
        list.innerHTML = `<div class="text-center py-10 opacity-50"><div class="text-4xl mb-4">📝</div><p class="text-xs font-bold uppercase tracking-widest text-gray-500">No Marks Available Yet</p></div>`;
        return;
    }

    list.innerHTML = '';

    // Initialize global METADATA for simulation
    if (typeof window.METADATA === 'undefined') {
        window.METADATA = {
            t1: { label: 'Test 1 (CA1)', max: 50, weight: 15, color: 'text-blue-400', accent: 'bg-blue-500' },
            t2: { label: 'Test 2 (CA2)', max: 50, weight: 15, color: 'text-indigo-400', accent: 'bg-indigo-500' },
            ap: { label: 'Assignment', max: 10, weight: 10, color: 'text-purple-400', accent: 'bg-purple-500' },
            ap1: { label: 'Assign 1', max: 5, weight: 5, color: 'text-purple-400', accent: 'bg-purple-500' },
            ap2: { label: 'Assign 2', max: 5, weight: 5, color: 'text-purple-400', accent: 'bg-purple-500' },
            mq1: { label: 'Quiz 1 (MQ1)', max: 10, weight: 5, color: 'text-pink-400', accent: 'bg-pink-500' },
            mq2: { label: 'Quiz 2 (MQ2)', max: 10, weight: 5, color: 'text-pink-400', accent: 'bg-pink-500' },
            ir1: { label: 'Record 1', max: 25, weight: 25, color: 'text-emerald-400', accent: 'bg-emerald-500' },
            ir2: { label: 'Record 2', max: 25, weight: 25, color: 'text-emerald-400', accent: 'bg-emerald-500' },
            plro1: { label: 'Pre-Lab 1', max: 10, weight: 10, color: 'text-teal-400', accent: 'bg-teal-500' },
            plro2: { label: 'Pre-Lab 2', max: 10, weight: 10, color: 'text-teal-400', accent: 'bg-teal-500' },
            // Fallbacks
            c1: { label: 'Comp 1', max: 50, weight: 10, color: 'text-gray-400', accent: 'bg-gray-500' },
            c2: { label: 'Comp 2', max: 50, weight: 10, color: 'text-gray-400', accent: 'bg-gray-500' },
            c3: { label: 'Comp 3', max: 50, weight: 10, color: 'text-gray-400', accent: 'bg-gray-500' },
            c4: { label: 'Comp 4', max: 50, weight: 10, color: 'text-gray-400', accent: 'bg-gray-500' },
            c5: { label: 'Comp 5', max: 50, weight: 10, color: 'text-gray-400', accent: 'bg-gray-500' },
            c6: { label: 'Comp 6', max: 50, weight: 10, color: 'text-gray-400', accent: 'bg-gray-500' }
        };
        window.simState = {};
    }

    let listHTML = '';

    mainSubjects.forEach((sub, idx) => {
        const rowData = sub.row_data;
        const numCols = rowData.length;
        let expectedKeys = [];
        if (sub.is_lab) {
            if (numCols === 5) expectedKeys = ['ir1', 'ir2', 'plro1', 'plro2', 'total'];
            else expectedKeys = rowData.map((_, i) => `c${i+1}`);
        } else {
            if (numCols === 8) expectedKeys = ['t1', 't2', 'best2t', 'ap', 'mq1', 'mq2', 'bestmcq', 'total'];
            else if (numCols === 9) expectedKeys = ['t1', 't2', 'best2t', 'ap1', 'ap2', 'mq1', 'mq2', 'bestmcq', 'total'];
            else expectedKeys = rowData.map((_, i) => `c${i+1}`);
        }

        const d = {};
        expectedKeys.forEach((k, i) => {
            const val = rowData[i];
            d[k] = (!val || val === '*' || val.trim() === '') ? null : parseFloat(val);
        });

        // Simulator keys exclude derived totals
        const simKeys = expectedKeys.filter(k => k !== 'best2t' && k !== 'bestmcq' && k !== 'total');
        const missingKeys = simKeys.filter(k => d[k] === null);

        // Use the API's pre-converted total for card display (most accurate)
        // API computes: theory → total*0.8 (/40), lab → total*1.2 (/60)
        const portalTotalConverted = parseFloat(sub.total_converted);
        const portalTotalRaw = parseFloat(sub.total); // raw from portal (/50 for theory)
        const hasPortalTotal = !isNaN(portalTotalConverted);

        // Fallback to component calc only when portal total not available
        const currentTotal = hasPortalTotal ? portalTotalRaw : calcCATotal(sub.is_lab, simKeys, d);
        const currentOutOf40 = hasPortalTotal
            ? portalTotalConverted
            : (sub.is_lab ? Math.min(60, currentTotal * 1.2) : Math.min(40, (currentTotal / 50) * 40));
        const displayMax = sub.is_lab ? 60 : 40;

        const isTheory = !sub.is_lab;
        const iconName = isTheory ? 'fa-book-open' : 'fa-flask';
        const typeColor = isTheory ? 'indigo' : 'teal';

        listHTML += `
        <div id="card-${sub.course_code}" class="bg-white/[0.03] border border-white/5 backdrop-blur-xl shadow-xl rounded-[28px] overflow-hidden transition-all duration-300 mb-4">
            <div class="p-5 relative overflow-hidden cursor-pointer active:scale-[0.98] transition-all" onclick="toggleInternalCard('${sub.course_code}')">
                <div class="absolute -right-4 -top-4 opacity-[0.03] pointer-events-none text-8xl text-white">
                    <i class="fas ${iconName}"></i>
                </div>
                <div class="flex justify-between items-start">
                    <div class="flex-1 pr-4 z-10">
                        <div class="flex flex-wrap items-center gap-2 mb-1.5">
                            <span class="text-[10px] font-bold uppercase tracking-widest px-2 py-0.5 rounded-md border bg-${typeColor}-500/10 text-${typeColor}-400 border-${typeColor}-500/20">${sub.course_code}</span>
                            <span class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">${isTheory ? 'Theory' : 'Laboratory'}</span>
                        </div>
                        <h3 class="font-bold text-white text-[13px] leading-snug">${sub.course_name}</h3>
                    </div>
                    <div class="flex flex-col items-end z-10 ml-2">
                        <div class="flex items-baseline gap-1">
                            <span class="text-2xl font-black text-transparent bg-clip-text ${missingKeys.length > 0 ? 'bg-gradient-to-r from-gray-300 to-gray-500' : 'bg-gradient-to-r from-indigo-300 to-purple-400'}">
                                ${currentOutOf40.toFixed(1)}
                            </span>
                            <span class="text-[10px] font-bold text-gray-500 uppercase tracking-widest">/ ${displayMax}</span>
                        </div>
                        <div class="mt-0.5 mb-1.5 opacity-80">
                            <span class="text-[9px] font-bold text-gray-400">${hasPortalTotal ? `Portal Raw Score: ${portalTotalRaw} / 50` : `Estimated from Pending`}</span>
                        </div>
                        <div class="mt-0 flex items-center">
                            ${missingKeys.length > 0 
                                ? `<span class="flex items-center gap-1 text-[9px] text-amber-400 font-bold bg-amber-400/10 px-1.5 py-0.5 rounded border border-amber-400/20 whitespace-nowrap"><i class="fas fa-exclamation-circle text-[8px]"></i> ${missingKeys.length} Pend</span>`
                                : `<span class="flex items-center gap-1 text-[9px] text-emerald-400 font-bold bg-emerald-400/10 px-1.5 py-0.5 rounded border border-emerald-400/20 whitespace-nowrap"><i class="fas fa-check-circle text-[8px]"></i> Final</span>`
                            }
                        </div>
                    </div>
                </div>
                <div class="mt-4 h-1 w-full bg-black/50 rounded-full overflow-hidden" id="bar-${sub.course_code}">
                     <div class="h-full bg-${typeColor}-500" style="width: ${Math.min(100,(currentOutOf40/displayMax)*100).toFixed(1)}%"></div>
                </div>
            </div>

            <div class="expandable-content" id="content-${sub.course_code}">
                <div class="expandable-inner cursor-default">
                    <div class="px-5 pb-5">
                        <div class="w-full h-px bg-gradient-to-r from-transparent via-white/10 to-transparent mb-5 mt-2"></div>
                        ${renderFullSimulator(sub, d, simKeys)}
                    </div>
                </div>
            </div>
        </div>`;
    });

    list.innerHTML = listHTML;

    // Initial calculation run for all simulators
    mainSubjects.forEach(sub => {
        if(window.simState[sub.course_code]) calculateSimOutputs(sub.course_code, sub);
    });
}

function renderFullSimulator(subject, d, expectedKeys) {
    const courseCode = subject.course_code;
    window.simState[courseCode] = { sem: 75 };
    expectedKeys.forEach(k => { 
        const actual = d[k];
        const meta = window.METADATA[k] || window.METADATA['c1'];
        window.simState[courseCode][k] = actual !== null ? actual : Math.round(meta.max * 0.7); 
    });

    let actualMarksHTML = '';
    let slidersHTML = '';

    expectedKeys.forEach(key => {
        const meta = window.METADATA[key] || window.METADATA['c1'];
        const isMissing = d[key] === null;

        if (!isMissing) {
            actualMarksHTML += `
            <div class="bg-white/5 p-3 rounded-xl border border-white/10 flex justify-between items-center">
                <span class="text-[11px] font-bold ${meta.color}">${meta.label}</span>
                <span class="text-sm font-black text-white bg-black/40 px-2.5 py-1 rounded">
                    ${d[key]} <span class="text-[9px] text-gray-500 font-medium">/ ${meta.max}</span>
                </span>
            </div>`;
        } else {
            slidersHTML += `
            <div class="bg-white/5 p-3.5 rounded-2xl border border-amber-500/20 shadow-[inset_0_0_15px_rgba(245,158,11,0.05)]">
                <div class="flex justify-between items-center mb-3">
                    <div class="flex flex-col">
                        <span class="text-xs font-bold ${meta.color}">${meta.label}</span>
                        <div class="mt-1"><span class="text-[9px] bg-amber-500/20 text-amber-400 px-1.5 py-0.5 rounded border border-amber-500/20">Pending</span></div>
                    </div>
                    <span class="text-sm font-black text-white bg-black/40 px-2.5 py-1 rounded">
                        <span id="val-${courseCode}-${key}">${window.simState[courseCode][key]}</span> 
                        <span class="text-[10px] text-gray-500 font-medium">/ ${meta.max}</span>
                    </span>
                </div>
                <input type="range" min="0" max="${meta.max}" step="1" value="${window.simState[courseCode][key]}" 
                    oninput="updateSim('${courseCode}', '${key}', this.value)"
                    class="w-full bg-black/50 rounded-lg appearance-none cursor-pointer accent-indigo-500 acad-slider" style="height: 8px;" />
            </div>`;
        }
    });

    let internalsSimSection = '';
    if (actualMarksHTML !== '') internalsSimSection += `<div class="mb-4"><p class="text-[9px] text-gray-400 mb-2 uppercase tracking-widest font-bold">Entered Marks</p><div class="grid grid-cols-2 gap-2">${actualMarksHTML}</div></div>`;
    if (slidersHTML !== '') internalsSimSection += `<div class="mb-6"><p class="text-[9px] text-gray-400 mb-2 uppercase tracking-widest font-bold">Pending Marks (Simulate)</p><div class="grid grid-cols-1 gap-3">${slidersHTML}</div></div>`;
    else internalsSimSection += `<div class="mb-6 bg-emerald-500/10 border border-emerald-500/20 rounded-xl p-3 text-center"><span class="text-xs font-bold text-emerald-400">All internal marks finalized!</span></div>`;

    return `
    <div class="bg-gradient-to-br from-black/60 to-indigo-950/30 p-5 rounded-3xl border border-indigo-500/20 mt-4 relative shadow-inner" onclick="event.stopPropagation()">
        <div class="flex items-center justify-between mb-5 border-b border-white/5 pb-3">
            <div class="flex items-center gap-2">
                <i class="fas fa-calculator text-indigo-400 text-xs"></i>
                <h4 class="text-xs font-bold text-indigo-300 uppercase tracking-widest">Master Simulator</h4>
            </div>
            <button onclick="resetSim('${courseCode}')" class="text-[10px] bg-white/10 hover:bg-white/20 text-gray-300 px-3 py-1.5 rounded-lg font-bold transition-colors active:scale-95">Reset</button>
        </div>

        ${internalsSimSection}

        <p class="text-[10px] text-gray-400 mb-3 uppercase tracking-widest font-bold">Simulate Final Exam</p>
        <div class="mb-5 bg-gradient-to-r from-purple-900/20 to-indigo-900/20 p-5 rounded-2xl border border-purple-500/20">
            <div class="flex justify-between items-end mb-4">
                <div class="flex items-center gap-2">
                    <i class="fas fa-graduation-cap text-purple-400 text-sm"></i>
                    <span class="text-xs font-bold text-gray-200">Final Sem Exam</span>
                </div>
                <div class="flex items-baseline gap-1">
                    <span class="text-2xl font-black text-purple-300" id="val-${courseCode}-sem">75</span>
                    <span class="text-[10px] font-bold text-gray-500">/ 100</span>
                </div>
            </div>
            <input type="range" min="0" max="100" value="75" id="slider-${courseCode}-sem"
                oninput="updateSim('${courseCode}', 'sem', this.value)"
                class="w-full bg-black/50 rounded-lg appearance-none cursor-pointer accent-purple-500 acad-slider" style="height: 8px;" />
        </div>

        <div class="flex items-stretch justify-between bg-black/40 p-2 rounded-2xl border border-white/5 mb-5 relative">
            <div class="flex-1 flex flex-col items-center justify-center p-2">
                <span class="text-[9px] text-gray-500 font-bold uppercase tracking-widest mb-1">CA Weight</span>
                <span class="text-xl font-black text-indigo-300" id="out-${courseCode}-ca">--</span>
                <span class="text-[8px] text-gray-600 mt-1" id="out-${courseCode}-ca-raw">--</span>
            </div>
            <div class="w-px bg-white/5 my-2"></div>
            <div class="flex-1 flex flex-col items-center justify-center p-2">
                <span class="text-[9px] text-gray-500 font-bold uppercase tracking-widest mb-1">Sem Weight</span>
                <span class="text-xl font-black text-purple-300" id="out-${courseCode}-sem">--</span>
                <span class="text-[8px] text-gray-600 mt-1" id="out-${courseCode}-sem-raw">--</span>
            </div>
            <div class="w-px bg-white/5 my-2"></div>
            <div id="out-${courseCode}-box" class="flex-[1.2] flex flex-col items-center justify-center p-3 rounded-xl border">
                <span class="text-[9px] text-gray-400 font-bold uppercase tracking-widest mb-1">Final Total</span>
                <span class="text-3xl font-black" id="out-${courseCode}-total">--%</span>
                <span id="out-${courseCode}-grade" class="text-[10px] font-bold mt-1.5 px-2 py-0.5 rounded bg-black/20 text-center leading-tight"></span>
            </div>
        </div>

        <div>
            <span class="text-[10px] font-bold text-gray-400 uppercase tracking-widest block mb-3">Smart Target — Marks needed in final exam</span>
            <div class="grid grid-cols-2 gap-3">
                <button onclick="targetGrade('${courseCode}', 90)" class="active:scale-95 py-3 rounded-xl bg-amber-500/10 border border-amber-500/20 text-xs font-bold text-amber-400">Aim Grade O (90)</button>
                <button onclick="targetGrade('${courseCode}', 80)" class="active:scale-95 py-3 rounded-xl bg-purple-500/10 border border-purple-500/20 text-xs font-bold text-purple-400">Aim A+ (80)</button>
                <button onclick="targetGrade('${courseCode}', 70)" class="active:scale-95 py-3 rounded-xl bg-indigo-500/10 border border-indigo-500/20 text-xs font-bold text-indigo-400">Aim A (70)</button>
                <button onclick="targetGrade('${courseCode}', 50)" class="active:scale-95 py-3 rounded-xl bg-rose-500/10 border border-rose-500/20 text-xs font-bold text-rose-400">Just Pass (50%)</button>
            </div>
        </div>
    </div>`;
}

function getGradeInfo(total) {
    if (total >= 90) return { grade: 'O', color: 'text-amber-400', bg: 'bg-amber-400/10', border: 'border-amber-400/30' };
    if (total >= 80) return { grade: 'A+', color: 'text-purple-400', bg: 'bg-purple-400/10', border: 'border-purple-400/30' };
    if (total >= 70) return { grade: 'A', color: 'text-indigo-400', bg: 'bg-indigo-400/10', border: 'border-indigo-400/30' };
    if (total >= 60) return { grade: 'B+', color: 'text-emerald-400', bg: 'bg-emerald-400/10', border: 'border-emerald-400/30' };
    if (total >= 50) return { grade: 'B', color: 'text-teal-400', bg: 'bg-teal-400/10', border: 'border-teal-400/30' };
    return { grade: 'U', color: 'text-rose-400', bg: 'bg-rose-400/10', border: 'border-rose-400/30' };
}

function toggleInternalCard(code) {
    const expand = document.getElementById(`content-${code}`);
    const card = document.getElementById(`card-${code}`);
    const bar = document.getElementById(`bar-${code}`);
    if (!expand) return;
    
    expand.classList.toggle('expanded');
    if(expand.classList.contains('expanded')) {
        card.classList.add('border-indigo-500/30', 'ring-1', 'ring-indigo-500/20');
        if(bar) bar.style.display = 'none';
    } else {
        card.classList.remove('border-indigo-500/30', 'ring-1', 'ring-indigo-500/20');
        if(bar) bar.style.display = 'block';
    }
}

function updateSim(courseCode, key, val) {
    window.simState[courseCode][key] = Number(val);
    document.getElementById(`val-${courseCode}-${key}`).innerText = val;
    if(key === 'sem') document.getElementById(`slider-${courseCode}-sem`).value = val;
    calculateSimOutputs(courseCode);
}

function resetSim(courseCode) {
    const subject = state.academics.internals.find(s => s.course_code === courseCode);
    const rowData = subject.row_data;
    const numCols = rowData.length;
    let expectedKeys = [];
    if (subject.is_lab) {
        if (numCols === 5) expectedKeys = ['ir1', 'ir2', 'plro1', 'plro2', 'total'];
        else expectedKeys = rowData.map((_, i) => `c${i+1}`);
    } else {
        if (numCols === 8) expectedKeys = ['t1', 't2', 'best2t', 'ap', 'mq1', 'mq2', 'bestmcq', 'total'];
        else if (numCols === 9) expectedKeys = ['t1', 't2', 'best2t', 'ap1', 'ap2', 'mq1', 'mq2', 'bestmcq', 'total'];
        else expectedKeys = rowData.map((_, i) => `c${i+1}`);
    }
    const simKeys = expectedKeys.filter(k => k !== 'best2t' && k !== 'bestmcq' && k !== 'total');
    
    const d = {};
    expectedKeys.forEach((k, i) => {
        const val = rowData[i];
        d[k] = (!val || val === '*' || val.trim() === '') ? null : parseFloat(val);
    });

    window.simState[courseCode] = { sem: 75 };
    simKeys.forEach(k => { 
        const actual = d[k];
        const meta = window.METADATA[k] || window.METADATA['c1'];
        window.simState[courseCode][k] = actual !== null ? actual : Math.round(meta.max * 0.7); 
        
        const slider = document.querySelector(`input[oninput="updateSim('${courseCode}', '${k}', this.value)"]`);
        if(slider) slider.value = window.simState[courseCode][k];
        const textVal = document.getElementById(`val-${courseCode}-${k}`);
        if(textVal) textVal.innerText = window.simState[courseCode][k];
    });

    document.getElementById(`slider-${courseCode}-sem`).value = 75;
    document.getElementById(`val-${courseCode}-sem`).innerText = 75;

    calculateSimOutputs(courseCode, subject);
}

/**
 * Core CA calculation using correct PSG formula:
 * Theory: Best2T = (T1+T2)/2, BestMCQ = (MQ1+MQ2)/2
 *         Total/50 = Best2T + AP + BestMCQ  (T raw = displayed/0.6)
 * Lab:    Total/50 = IR1 + IR2 + PLRO1 + PLRO2  → ×1.2 for /60
 */
function calcCATotal(isLab, simKeys, values) {
    if (isLab) {
        // Sum all lab components directly (out of 50)
        const labKeys = ['ir1', 'ir2', 'plro1', 'plro2'];
        return labKeys.reduce((sum, k) => sum + (simKeys.includes(k) ? (values[k] || 0) : 0), 0);
    }
    // Theory
    const t1Raw = (values['t1'] || 0) / 0.6;   // revert scale-down
    const t2Raw = (values['t2'] || 0) / 0.6;
    const best2T = (t1Raw + t2Raw) / 2;          // average of both tests
    const ap = (values['ap'] || 0) + (values['ap1'] || 0) + (values['ap2'] || 0);
    const mq1 = values['mq1'] || 0;
    const mq2 = values['mq2'] || 0;
    const bestMCQ = (mq1 + mq2) / 2;             // average of both quizzes
    return best2T + ap + bestMCQ;                 // raw total out of 50
}

function calculateSimOutputs(courseCode, subjectObj) {
    const subject = subjectObj || state.academics.internals.find(s => s.course_code === courseCode);
    if(!subject) return;
    
    const numCols = subject.row_data.length;
    let expectedKeys = [];
    if (subject.is_lab) {
        if (numCols === 5) expectedKeys = ['ir1', 'ir2', 'plro1', 'plro2', 'total'];
        else expectedKeys = subject.row_data.map((_, i) => `c${i+1}`);
    } else {
        if (numCols === 8) expectedKeys = ['t1', 't2', 'best2t', 'ap', 'mq1', 'mq2', 'bestmcq', 'total'];
        else if (numCols === 9) expectedKeys = ['t1', 't2', 'best2t', 'ap1', 'ap2', 'mq1', 'mq2', 'bestmcq', 'total'];
        else expectedKeys = subject.row_data.map((_, i) => `c${i+1}`);
    }
    const simKeys = expectedKeys.filter(k => k !== 'best2t' && k !== 'bestmcq' && k !== 'total');

    const totalCA = calcCATotal(subject.is_lab, simKeys, window.simState[courseCode]);
    // Lab: internal max is 60 (×1.2 scaling); Theory: max is 40 (×0.8 scaling)
    const ca40 = subject.is_lab ? Math.min(60, totalCA * 1.2) : Math.min(40, (totalCA / 50) * 40);
    const sem60 = (window.simState[courseCode].sem / 100) * 60;
    const grandTotal = ca40 + sem60;
    const info = getGradeInfo(grandTotal);

    const caEl = document.getElementById(`out-${courseCode}-ca`);
    if(caEl) {
        caEl.innerText = ca40.toFixed(1);
        document.getElementById(`out-${courseCode}-ca-raw`).innerText = subject.is_lab ? `Lab: ${totalCA.toFixed(1)}→×1.2` : `Theory: ${totalCA.toFixed(1)}/50`;
        document.getElementById(`out-${courseCode}-sem`).innerText = sem60.toFixed(1);
        document.getElementById(`out-${courseCode}-sem-raw`).innerText = `Exam ${window.simState[courseCode].sem}/100 × 60%`;
        
        document.getElementById(`out-${courseCode}-total`).innerText = grandTotal.toFixed(1) + '%';
        document.getElementById(`out-${courseCode}-total`).className = `text-3xl font-black ${info.color}`;
        
        const box = document.getElementById(`out-${courseCode}-box`);
        box.className = `flex-[1.2] flex flex-col items-center justify-center p-3 rounded-xl border ${info.bg} ${info.border}`;
        
        const gradeBadge = document.getElementById(`out-${courseCode}-grade`);
        gradeBadge.className = `text-[10px] font-bold mt-1.5 px-2 py-0.5 rounded ${info.color} bg-black/20 text-center leading-tight`;
        gradeBadge.innerHTML = `Grade: ${info.grade}`;
    }
}

function targetGrade(courseCode, targetTotal) {
    const subject = state.academics.internals.find(s => s.course_code === courseCode);
    const numCols = subject.row_data.length;
    let expectedKeys = [];
    if (subject.is_lab) {
        if (numCols === 5) expectedKeys = ['ir1', 'ir2', 'plro1', 'plro2', 'total'];
        else expectedKeys = subject.row_data.map((_, i) => `c${i+1}`);
    } else {
        if (numCols === 8) expectedKeys = ['t1', 't2', 'best2t', 'ap', 'mq1', 'mq2', 'bestmcq', 'total'];
        else if (numCols === 9) expectedKeys = ['t1', 't2', 'best2t', 'ap1', 'ap2', 'mq1', 'mq2', 'bestmcq', 'total'];
        else expectedKeys = subject.row_data.map((_, i) => `c${i+1}`);
    }
    const simKeys = expectedKeys.filter(k => k !== 'best2t' && k !== 'bestmcq' && k !== 'total');

    // Use corrected CA formula
    const totalCA = calcCATotal(subject.is_lab, simKeys, window.simState[courseCode]);
    const ca40 = subject.is_lab ? Math.min(60, totalCA * 1.2) : Math.min(40, (totalCA / 50) * 40);

    // Required exam %: (target - ca_weight) / 0.6
    // Per spec: Since final exam counts 60%, required exam marks = (target - ca40) / 0.6
    const requiredExamPct = (targetTotal - ca40) / 0.6;

    if (requiredExamPct > 100) {
        const maxPossible = (ca40 + 60).toFixed(1);
        showToast(`Max possible: ${maxPossible}% total — cannot reach ${targetTotal}%. Need higher CA marks.`);
    } else if (requiredExamPct <= 0) {
        showToast(`Already achieved ${targetTotal}% total with current CA alone!`);
        updateSim(courseCode, 'sem', 0);
    } else {
        const req = Math.ceil(requiredExamPct);
        showToast(`Need ${req} / 100 in Final Exam to score ${targetTotal}% overall`);
        updateSim(courseCode, 'sem', req);
    }
}


// ---- GPA ----
function renderGPA(gpaData) {
    const valEl = document.getElementById('gpa-value');
    const tableEl = document.getElementById('gpa-table');
    if (!valEl || !tableEl) return;

    const gpa = gpaData.gpa;
    valEl.textContent = gpa === 'RA' ? 'RA' : (gpa || '--');
    valEl.style.color = gpa === 'RA' ? '#EF4444' : gpa >= 8.5 ? '#10B981' : gpa >= 7 ? '#6366f1' : gpa >= 5 ? '#F59E0B' : '#EF4444';

    const courses = gpaData.table || [];
    if (courses.length === 0) {
        tableEl.innerHTML = '<div class="text-center py-10 text-gray-600 text-xs">No semester data found</div>';
        return;
    }

    // Group by sem
    const sems = {};
    courses.forEach(c => {
        if (!sems[c.sem]) sems[c.sem] = [];
        sems[c.sem].push(c);
    });

    let html = '';
    Object.keys(sems).sort((a, b) => b - a).forEach(sem => {
        html += `<div class="mb-4"><p class="text-[9px] font-black text-indigo-400 uppercase tracking-widest px-1 mb-2">Semester ${sem}</p><div class="bg-black/20 rounded-3xl p-2 border border-white/5 space-y-1">`;
        sems[sem].forEach(c => {
            const gradeStr = c.grade || '--';
            const isPass = c.result === 'Pass';
            html += `
            <div class="flex flex-col sm:flex-row justify-between items-start sm:items-center p-3 rounded-2xl hover:bg-white/5 transition-colors gap-2">
                <div class="flex-1 pr-2">
                    <p class="text-[11px] sm:text-xs font-bold text-white mb-0.5 leading-snug">${c.title}</p>
                    <p class="text-[9px] text-gray-500 font-bold uppercase tracking-wider">${c.course} • ${c.credits || 0} CR</p>
                </div>
                <div class="flex items-center gap-2 w-full sm:w-auto justify-between sm:justify-end mt-1 sm:mt-0 pt-2 sm:pt-0 border-t border-white/5 sm:border-t-0">
                    <div class="bg-white/5 px-3 py-1.5 rounded-lg border border-white/10 min-w-[70px] text-center">
                        <span class="text-xs font-black text-indigo-300">${gradeStr}</span>
                    </div>
                    ${c.result ? `
                    <div class="${isPass ? 'bg-emerald-500/10 border-emerald-500/20' : 'bg-rose-500/10 border-rose-500/20'} px-3 py-1.5 rounded-lg border">
                        <span class="text-[10px] font-bold ${isPass ? 'text-emerald-400' : 'text-rose-400'} uppercase tracking-wider">${c.result}</span>
                    </div>` : ''}
                </div>
            </div>`;
        });
        html += '</div></div>';
    });

    tableEl.innerHTML = html;
}

// ---- CGPA ----
function renderCGPA(cgpaData) {
    const valEl = document.getElementById('internals-cgpa-value');
    const credEl = document.getElementById('cgpa-credits');
    const chartEl = document.getElementById('cgpa-chart');
    const semList = document.getElementById('cgpa-semlist');
    if (!valEl) return;

    const cgpa = cgpaData.cgpa;
    valEl.textContent = cgpa === 'RA' ? 'RA' : (cgpa || '--');
    valEl.style.color = cgpa === 'RA' ? '#EF4444' : cgpa >= 8.5 ? '#10B981' : cgpa >= 7 ? '#6366f1' : cgpa >= 5 ? '#F59E0B' : '#EF4444';

    if (credEl) credEl.textContent = `${cgpaData.total_credits || 0} total credits earned`;

    const semData = cgpaData.semwise_data || [];

    // SVG Line Chart
    if (chartEl && semData.length > 0) {
        const W = 300, H = 120, padX = 30, padY = 15;
        const innerW = W - padX * 2;
        const innerH = H - padY * 2;
        const minGPA = 5, maxGPA = 10;

        const toX = (i) => padX + (i / Math.max(semData.length - 1, 1)) * innerW;
        const toY = (g) => padY + (1 - (Math.max(g, minGPA) - minGPA) / (maxGPA - minGPA)) * innerH;

        // Build paths
        const sgpaPoints = semData.map((d, i) => `${toX(i)},${toY(d.sgpa)}`).join(' ');
        const cgpaPoints = semData.map((d, i) => `${toX(i)},${toY(d.cgpa)}`).join(' ');

        // Grid lines at 6, 7, 8, 9, 10
        const gridLines = [6, 7, 8, 9, 10].map(g => {
            const y = toY(g);
            return `<line x1="${padX}" y1="${y}" x2="${W - padX}" y2="${y}" stroke="rgba(255,255,255,0.05)" stroke-width="1"/>
                    <text x="${padX - 4}" y="${y + 4}" font-size="7" fill="rgba(255,255,255,0.2)" text-anchor="end">${g}</text>`;
        }).join('');

        // Dots
        const sgpaDots = semData.map((d, i) => `<circle cx="${toX(i)}" cy="${toY(d.sgpa)}" r="3.5" fill="#6366f1"/>`).join('');
        const cgpaDots = semData.map((d, i) => `<circle cx="${toX(i)}" cy="${toY(d.cgpa)}" r="3.5" fill="#10B981"/>`).join('');

        // Sem labels
        const semLabels = semData.map((d, i) => `<text x="${toX(i)}" y="${H - 2}" font-size="7" fill="rgba(255,255,255,0.25)" text-anchor="middle">S${d.sem}</text>`).join('');

        chartEl.innerHTML = `
        <svg viewBox="0 0 ${W} ${H}" class="cgpa-chart-svg">
            ${gridLines}
            <!-- CGPA Line -->
            <polyline points="${cgpaPoints}" fill="none" stroke="#10B981" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"/>
            <!-- SGPA Line -->
            <polyline points="${sgpaPoints}" fill="none" stroke="#6366f1" stroke-width="1.5" stroke-dasharray="4 3" stroke-linejoin="round" stroke-linecap="round"/>
            ${cgpaDots}
            ${sgpaDots}
            ${semLabels}
        </svg>
        <div class="flex gap-4 mt-2 justify-center">
            <div class="flex items-center gap-1.5"><div class="w-4 h-[2px] bg-emerald-500 rounded-full"></div><span class="text-[9px] font-bold text-gray-500">CGPA</span></div>
            <div class="flex items-center gap-1.5"><div class="w-4 h-[2px] bg-indigo-500 rounded-full opacity-70" style="background: repeating-linear-gradient(90deg, #6366f1 0px, #6366f1 4px, transparent 4px, transparent 7px);"></div><span class="text-[9px] font-bold text-gray-500">SGPA</span></div>
        </div>`;
    }

    // Sem-by-Sem breakdown
    if (semList && semData.length > 0) {
        semList.innerHTML = '';
        semData.forEach(d => {
            const gpaColor = d.cgpa >= 8.5 ? 'text-emerald-400' : d.cgpa >= 7 ? 'text-indigo-400' : d.cgpa >= 5 ? 'text-amber-400' : 'text-rose-400';
            semList.innerHTML += `
            <div class="glass-panel rounded-[24px] p-5 flex items-center justify-between">
                <div>
                    <p class="text-[9px] font-black text-gray-600 uppercase tracking-widest mb-1">Semester ${d.sem}</p>
                    <div class="flex gap-4">
                        <div>
                            <span class="text-[8px] font-bold text-indigo-400/60 block uppercase">SGPA</span>
                            <span class="text-lg font-black text-indigo-300">${d.sgpa}</span>
                        </div>
                        <div class="w-px bg-white/5"></div>
                        <div>
                            <span class="text-[8px] font-bold text-emerald-400/60 block uppercase">CGPA</span>
                            <span class="text-lg font-black ${gpaColor}">${d.cgpa}</span>
                        </div>
                    </div>
                </div>
                <div class="w-10 h-10 rounded-2xl bg-white/5 flex items-center justify-center text-gray-500 text-sm font-black">S${d.sem}</div>
            </div>`;
        });
    } else if (semList) {
        semList.innerHTML = '<div class="text-center py-8 text-gray-600 text-xs">No semester data yet</div>';
    }
}

// Hook into switchTab to auto-load academics
// (Academics auto-load is handled in the existing switchTab function body above)
// Call this to refresh academics data manually
function refreshAcademics() {
    state.academics = { internals: null, gpa: null, cgpa: null, loaded: false };
    loadAcademics();
}


