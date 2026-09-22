/**
 * BUNKER ACADEMIC CALENDAR & PLANNER
 * Automated Dynamic Roll Number Calendar Resolver
 * Zero manual tokens or hardcoded semester IDs.
 */

(function () {
    'use strict';

    // --- Branch metadata for client-side resolution & display ---
    const PSGTECH_BRANCHES = {
        'A': { degree: 'B.E.', name: 'Automobile Engineering', sandwich: false },
        'D': { degree: 'B.E.', name: 'Civil Engineering', sandwich: false },
        'C': { degree: 'B.E.', name: 'Computer Science & Engineering', sandwich: false },
        'CS': { degree: 'B.E.', name: 'Computer Science & Engineering', sandwich: false },
        'Z': { degree: 'B.E.', name: 'Electronics & Communication Engineering', sandwich: false },
        'N': { degree: 'B.E.', name: 'Electrical & Electronics Engineering', sandwich: false },
        'E': { degree: 'B.E.', name: 'Electronics & Instrumentation Engineering', sandwich: false },
        'L': { degree: 'B.E.', name: 'Mechanical Engineering', sandwich: false },
        'M': { degree: 'B.E.', name: 'Metallurgical Engineering', sandwich: false },
        'Y': { degree: 'B.E.', name: 'Production Engineering', sandwich: false },
        'P': { degree: 'B.E. (Sandwich)', name: 'Production Engineering (Sandwich)', sandwich: true },
        'K': { degree: 'B.E. (Sandwich)', name: 'Mechanical Engineering (Sandwich)', sandwich: true },
        'ES': { degree: 'B.E. (Sandwich)', name: 'Electrical & Electronics (Sandwich)', sandwich: true },
        'SW': { degree: 'B.E. (Sandwich)', name: 'Sandwich Engineering Program', sandwich: true },
        'R': { degree: 'B.E.', name: 'Robotics & Automation', sandwich: false },
        'U': { degree: 'B.E.', name: 'Biomedical Engineering', sandwich: false },
        'B': { degree: 'B.Tech', name: 'Biotechnology', sandwich: false },
        'H': { degree: 'B.Tech', name: 'Fashion Technology', sandwich: false },
        'I': { degree: 'B.Tech', name: 'Information Technology', sandwich: false },
        'T': { degree: 'B.Tech', name: 'Textile Technology', sandwich: false },
        'S': { degree: 'B.Sc', name: 'Applied Science / Computer Systems', sandwich: false },
        'X': { degree: 'B.Sc', name: 'Mathematics & Computing', sandwich: false },
        'SA': { degree: 'M.Sc (Integrated)', name: 'Software Systems', sandwich: false },
        'FD': { degree: 'M.Sc (Integrated)', name: 'Data Science', sandwich: false },
        'XW': { degree: 'M.Sc (Integrated)', name: 'Cyber Security', sandwich: false },
        'XT': { degree: 'M.Sc (Integrated)', name: 'Theoretical Computer Science', sandwich: false },
        'XD': { degree: 'M.Sc (Integrated)', name: 'Decision & Computing Sciences', sandwich: false },
        'XC': { degree: 'M.Sc (Integrated)', name: 'Theoretical Computer Science', sandwich: false },
        'MX': { degree: 'M.C.A.', name: 'Master of Computer Applications', sandwich: false },
        'AE': { degree: 'M.E.', name: 'Automotive Engineering', sandwich: false },
        'NB': { degree: 'M.E.', name: 'Energy Engineering', sandwich: false },
        'ZC': { degree: 'M.E.', name: 'Communication Systems', sandwich: false },
        'UC': { degree: 'M.E.', name: 'Embedded & Real-Time Systems', sandwich: false },
        'EE': { degree: 'M.E.', name: 'Power Electronics & Drives', sandwich: false },
        'MD': { degree: 'M.E.', name: 'Manufacturing Engineering', sandwich: false },
        'MN': { degree: 'M.E.', name: 'Engineering Design', sandwich: false },
        'PP': { degree: 'M.E.', name: 'Computer Science & Engineering', sandwich: false },
        'ED': { degree: 'M.E.', name: 'Industrial Engineering', sandwich: false },
        'CS': { degree: 'M.E.', name: 'Computer Science & Engineering', sandwich: false },
        'LV': { degree: 'M.E.', name: 'VLSI Design', sandwich: false },
        'BT': { degree: 'M.Tech', name: 'Biotechnology', sandwich: false },
        'LN': { degree: 'M.Tech', name: 'Nano Science & Technology', sandwich: false },
        'TT': { degree: 'M.Tech', name: 'Textile Technology', sandwich: false },
        'SE': { degree: 'M.E.', name: 'Structural Engineering', sandwich: false },
        'CE': { degree: 'M.Tech', name: 'Chemical Engineering', sandwich: false },
        'EC': { degree: 'M.Tech', name: 'Electronics & Communication', sandwich: false },
        'IT': { degree: 'M.Tech', name: 'Information Technology', sandwich: false },
        'GM': { degree: 'M.B.A.', name: 'Master of Business Administration', sandwich: false },
        'GW': { degree: 'M.B.A.', name: 'Master of Business Administration', sandwich: false }
    };

    // --- State ---
    const STATE = {
        currentRoll: '',
        currentSemester: (new Date().getMonth() + 1 >= 1 && new Date().getMonth() + 1 <= 5) ? 'even' : 'odd',
        academicYear: 2026,
        student: null,
        plannerData: null,
        availablePlanners: [],
        activeCategoryFilter: 'all',
        searchQuery: '',
        currentView: 'agenda', // 'agenda' | 'month' | 'holidays'
        calendarMonthDate: new Date(),
        allYearsIndex: null
    };

    // --- Helper: Clean Roll (Repairs Excel / Google Sheets scientific notation & diploma prefixes) ---
    function cleanRollNumber(raw) {
        if (!raw) return '';
        let roll = String(raw).trim().toUpperCase();
        // Handle exponential formatting e.g. 2.50E+119 or 250E+201
        const m = roll.match(/^(\d+)\.?(\d*)E\+(\d+)$/i);
        if (m) {
            const digits = m[1] + m[2];
            const year = digits.substring(0, 2);
            const suffix = m[3];
            return `${year}E${suffix}`;
        }
        // Handle optional leading 'D' for diploma / lateral entry notations (e.g. D26U233 -> 26U233)
        roll = roll.replace(/^D(\d{2}[A-Z])/i, '$1');
        return roll;
    }

    // --- Helper: Validate PSG Tech Roll Number ---
    function checkNonPsgCollege(roll) {
        if (!roll) return null;
        if (!/^\d{2}[A-Z]/i.test(roll) || roll.length < 6 || roll.length > 7) {
            return {
                college: 'OTHER',
                message: `Roll number <strong>${escapeHtml(roll)}</strong> is not a valid PSG College of Technology roll number.<br><span class="opacity-80">This academic calendar portal is exclusively available for <strong>PSG College of Technology</strong> students.</span>`
            };
        }
        return null;
    }

    // --- Helper: Detect eCampus active semester from local storage ---
    function detectEcampusSemClient(roll) {
        try {
            roll = cleanRollNumber(roll);
            const subjectsRaw = localStorage.getItem(`bunker_subjects_${roll}`) || localStorage.getItem('bunker_subjects');
            if (subjectsRaw) {
                const subs = JSON.parse(subjectsRaw);
                if (Array.isArray(subs) && subs.length > 0) {
                    const codes = subs.map(s => s.code || s.course).filter(Boolean);
                    const semCounts = {};
                    for (const c of codes) {
                        const m = String(c).trim().toUpperCase().match(/^[0-9]{2}[A-Z]+([1-9])\d{1,2}/);
                        if (m) {
                            const sem = parseInt(m[1], 10);
                            semCounts[sem] = (semCounts[sem] || 0) + 1;
                        }
                    }
                    let bestSem = null, maxCount = 0;
                    for (const [s, cnt] of Object.entries(semCounts)) {
                        if (cnt > maxCount) {
                            maxCount = cnt;
                            bestSem = parseInt(s, 10);
                        }
                    }
                    if (bestSem) {
                        return {
                            semesterNo: bestSem,
                            yearOfStudy: Math.floor((bestSem + 1) / 2),
                            semesterType: (bestSem % 2 === 1) ? 'odd' : 'even',
                            source: 'ecampus_localstorage'
                        };
                    }
                }
            }
        } catch (e) {}
        return null;
    }

    // --- Parse Roll Number into Student Metadata ---
    function parseStudentRoll(roll, acadYear, explicitSem) {
        roll = cleanRollNumber(roll);
        if (!roll || roll.length < 4) return null;
        acadYear = acadYear || STATE.academicYear || 2026;

        const mYear = roll.match(/^(\d{2})/);
        if (!mYear) return null;
        const admYear = 2000 + parseInt(mYear[1], 10);

        const mLetters = roll.substring(2).match(/[A-Z]+/);
        const branchLetters = mLetters ? mLetters[0] : '';
        let branchCode = null;
        if (branchLetters.length >= 2) {
            const code2 = branchLetters.substring(0, 2);
            if (PSGTECH_BRANCHES[code2]) {
                branchCode = code2;
            } else if (code2 === 'PT') {
                branchCode = 'P';
            } else {
                return null;
            }
        } else if (branchLetters.length === 1 && PSGTECH_BRANCHES[branchLetters.charAt(0)]) {
            branchCode = branchLetters.charAt(0);
        } else {
            // Not a valid PSG Tech branch code
            return null;
        }

        const meta = PSGTECH_BRANCHES[branchCode];

        // Serial number in roll (e.g. 25U402 -> 402, 25U201 -> 201, 22E613 -> 613)
        const mNum = roll.match(/(\d+)$/);
        const serialNum = mNum ? parseInt(mNum[1], 10) : 0;

        // Distinguish Sandwich sections (500-series and 600-series for E, M, P, N, L)
        const isSandwichSeries = (serialNum >= 500 && serialNum <= 699 && ['E', 'M', 'P', 'N', 'L'].includes(branchCode));

        // Detect Lateral Entry (400-series or L/LE/D prefix)
        const isLateral = (serialNum >= 400 && serialNum <= 499 && ['B.E.', 'B.Tech'].includes(meta.degree)) || /^L|LE|D/i.test(roll);

        // Nominal year of study: lateral entry enters directly into Year 2 (skips Year 1)
        let nominalYear = isLateral ? (acadYear - admYear + 2) : (acadYear - admYear + 1);

        const ecampusSem = detectEcampusSemClient(roll);
        let semesterNo = null;
        let yearOfStudy = nominalYear;
        let semesterType = STATE.currentSemester || 'odd';

        if (explicitSem && String(explicitSem).match(/^\d+$/)) {
            semesterNo = parseInt(explicitSem, 10);
            yearOfStudy = Math.floor((semesterNo + 1) / 2);
            semesterType = (semesterNo % 2 === 1) ? 'odd' : 'even';
        } else if (ecampusSem) {
            semesterNo = ecampusSem.semesterNo;
            yearOfStudy = ecampusSem.yearOfStudy;
            semesterType = ecampusSem.semesterType;
        } else {
            if (explicitSem && ['odd', 'even'].includes(String(explicitSem).toLowerCase())) {
                semesterType = String(explicitSem).toLowerCase();
            }
            semesterNo = (semesterType === 'even') ? (yearOfStudy * 2) : (yearOfStudy * 2 - 1);
        }

        const isSandwich = meta.sandwich || isSandwichSeries || (yearOfStudy === 5 && !['SA', 'FD', 'XW', 'XT', 'XD', 'XC'].includes(branchCode));
        const maxYears = isSandwich || ['SA', 'FD', 'XW', 'XT', 'XD', 'XC'].includes(branchCode) ? 5 : (meta.degree === 'M.E.' || meta.degree === 'M.C.A.' ? 2 : (meta.degree === 'B.Sc' ? 3 : 4));
        yearOfStudy = Math.max(1, Math.min(maxYears, yearOfStudy));
        semesterNo = Math.max(1, Math.min(maxYears * 2, semesterNo));

        const isMCA = (branchCode === 'MX');
        const isMSc = ['SA', 'FD', 'XW', 'XT', 'XD', 'XC'].includes(branchCode);
        const isBSc = ['S', 'X'].includes(branchCode);
        const isPG = ['M.E.', 'M.Tech', 'M.B.A.'].includes(meta.degree);

        let courseType = 'BE';
        const degClean = (meta.degree || '').replace(/\./g, '').toUpperCase();
        if (degClean.includes('BTECH')) courseType = 'BTech';
        else if (degClean.includes('BSC')) courseType = 'BSc';
        else if (degClean.includes('MSC')) courseType = 'MSc';
        else if (degClean.includes('ME') || degClean.includes('MTECH') || degClean.includes('MBA')) courseType = 'ME';
        else if (degClean.includes('MCA')) courseType = 'MCA';

        return {
            roll: roll,
            admissionYear: admYear,
            academicYear: acadYear,
            yearOfStudy: yearOfStudy,
            semesterNo: semesterNo,
            semesterType: semesterType,
            isLateralEntry: isLateral,
            entryType: isLateral ? 'Lateral Entry (Direct 2nd Year)' : 'Regular Entry',
            branchCode: branchCode,
            degree: meta.degree,
            branchName: meta.name,
            course: courseType,
            isSandwich: isSandwich,
            isMCA: isMCA,
            isMSc: isMSc,
            isBSc: isBSc,
            isPG: isPG,
            ecampusSynced: Boolean(ecampusSem)
        };
    }

    // --- Client-side Planner Matching Logic ---
    function splitClauses(title) {
        let clean = (title || '').toLowerCase();
        clean = clean.replace(/reg(ular)?\.?\s*&\s*sw/g, 'reg_and_sw');
        clean = clean.replace(/regular\s+and\s+sw/g, 'reg_and_sw');
        clean = clean.replace(/b\.?e\.?\s*\/\s*b\.?tech/g, 'be');
        clean = clean.replace(/be\/btech/g, 'be');
        clean = clean.replace(/all\s+bsc\s+(and|&)\s+all\s+msc/g, 'all_bsc_msc');
        return clean.split(/[,;]|\band\b/).map(s => s.trim()).filter(Boolean);
    }

    function scoreClause(clause, s) {
        const c = clause.toLowerCase();
        const y = s.yearOfStudy;
        const courseNorm = (s.course || 'BE').replace(/\./g, '').toUpperCase();

        if (s.isSandwich) {
            if (!c.includes('sw') && !c.includes('sandwich')) return 0;
            if (y === 5 && (c.includes('fifth') || c.includes('5th') || c.includes('v year') || c.includes('final'))) return 100;
            if (y === 4 && (c.includes('fourth') || c.includes('4th') || c.includes('iv year'))) return 100;
            if (y === 3 && (c.includes('third') || c.includes('3rd') || c.includes('iii'))) return 90;
            if (y === 2 && (c.includes('second') || c.includes('2nd') || c.includes('ii'))) return 90;
            if (y === 1 && (c.includes('first') || c.includes('1st') || c.includes('i '))) return 90;
            return 70;
        }

        if (c.includes('fourth year be sw') || c.includes('fifth year be sw') || c.includes('final year be sandwich')) {
            return 0;
        }

        if (s.isBSc || s.isMSc) {
            return (c.includes('bsc') || c.includes('msc') || c.includes('all_bsc_msc')) ? 100 : 0;
        }

        if (s.isMCA) {
            if (!c.includes('mca')) return 0;
            if (y === 1 && (c.includes('first') || c.includes('1st') || c.includes('i year') || c.includes('i '))) return 100;
            if (y >= 2 && (c.includes('second') || c.includes('2nd') || c.includes('ii year') || c.includes('ii '))) return 100;
            return 80;
        }

        if (s.isPG) {
            if (!c.includes('me') && !c.includes('mtech') && !c.includes('pg')) return 0;
            if (y === 1 && (c.includes('first') || c.includes('1st') || c.includes('i year') || c.includes('i '))) return 100;
            if (y >= 2 && (c.includes('second') || c.includes('2nd') || c.includes('ii year') || c.includes('ii '))) return 100;
            return 80;
        }

        if (courseNorm === 'BE' || courseNorm === 'BTECH') {
            if ((c.includes('mca') && !c.includes('be') && !c.includes('btech')) || (c.includes('all_bsc_msc') && !c.includes('be') && !c.includes('btech'))) {
                return 0;
            }
            if (y === 1 && (c.includes('first year') || c.includes('1st year') || c.includes('i year') || c.includes('first  year'))) return 100;
            if (y === 2 && (c.includes('second year') || c.includes('2nd year') || c.includes('ii year'))) return 100;
            if ((y === 3 || y === 4) && (c.includes('3rd') || c.includes('4th') || c.includes('third') || c.includes('fourth') || c.includes('iii') || c.includes('iv'))) return 100;
        }

        return 0;
    }

    function matchPlannerClient(planners, student, semester) {
        if (!planners || !planners.length) return null;
        semester = (semester || 'odd').toLowerCase();
        const active = planners.filter(p => {
            const nl = (p.name || '').toLowerCase();
            if (semester === 'odd') {
                return p.isPublished || (nl.includes('odd') && !nl.includes('even'));
            } else {
                return !p.isPublished || nl.includes('even');
            }
        });

        const list = active.length ? active : planners;
        let best = null;
        let bestScore = -1;

        list.forEach(p => {
            const clauses = splitClauses(p.name);
            const maxScore = Math.max(0, ...clauses.map(cl => scoreClause(cl, student)));
            if (maxScore > bestScore) {
                bestScore = maxScore;
                best = p;
            }
        });

        return best || list[0];
    }

    // --- Categorize Activity ---
    function categorize(name, isHoliday) {
        if (isHoliday) {
            return { type: 'holiday', label: 'Holiday', badgeClass: 'badge-holiday', icon: 'fa-umbrella-beach' };
        }
        const n = (name || '').toLowerCase();
        if (n.includes('assessment tutorial') || n.includes('tutorial')) {
            return { type: 'tutorial', label: 'Tutorial', badgeClass: 'badge-at', icon: 'fa-book-open' };
        }
        if (n.includes('ca test') || n.includes('ca 1') || n.includes('ca 2') || n.includes('ca 3') || n.includes('practice test')) {
            return { type: 'catest', label: 'CA Test', badgeClass: 'badge-ca', icon: 'fa-pen-to-square' };
        }
        if (n.includes('semester exam') || n.includes('end semester exam')) {
            return { type: 'exam', label: 'Semester Exam', badgeClass: 'badge-sem', icon: 'fa-graduation-cap' };
        }
        if (n.includes('laboratory exam') || n.includes('lab exam')) {
            return { type: 'exam', label: 'Lab Exam', badgeClass: 'badge-lab', icon: 'fa-flask' };
        }
        if (n.includes('feedback') || n.includes('attendance review') || n.includes('mark entry')) {
            return { type: 'review', label: 'Review & Feedback', badgeClass: 'badge-blue', icon: 'fa-clipboard-check' };
        }
        return { type: 'milestone', label: 'Academic Milestone', badgeClass: 'badge-milestone', icon: 'fa-calendar-day' };
    }

    function formatDate(dateStr) {
        if (!dateStr) return 'TBA';
        try {
            const d = new Date(dateStr);
            if (isNaN(d.getTime())) return dateStr;
            return d.toLocaleDateString('en-IN', {
                weekday: 'short',
                day: 'numeric',
                month: 'short',
                year: 'numeric'
            });
        } catch (e) {
            return dateStr;
        }
    }

    function getDaysDiff(targetDateStr) {
        if (!targetDateStr) return null;
        try {
            const target = new Date(targetDateStr);
            const now = new Date();
            target.setHours(0, 0, 0, 0);
            now.setHours(0, 0, 0, 0);
            const diffTime = target.getTime() - now.getTime();
            return Math.round(diffTime / (1000 * 60 * 60 * 24));
        } catch (e) {
            return null;
        }
    }

    // --- Fetch / Load Calendar for Roll ---
    async function loadCalendar(roll, semester, forceDirectApi = false) {
        roll = cleanRollNumber(roll || STATE.currentRoll);
        if (!roll) return;

        const isNewRoll = (roll !== STATE.currentRoll);
        STATE.currentRoll = roll;

        if (semester !== undefined && semester !== null) {
            if (String(semester).match(/^\d+$/)) {
                STATE.currentSemesterNo = parseInt(semester, 10);
                STATE.currentSemester = (STATE.currentSemesterNo % 2 === 1) ? 'odd' : 'even';
            } else {
                STATE.currentSemester = String(semester).toLowerCase();
                STATE.currentSemesterNo = null;
            }
        } else if (isNewRoll) {
            // Reset semester state so new roll automatically detects its appropriate semester
            STATE.currentSemesterNo = null;
            STATE.currentSemester = null;
        }

        try { localStorage.setItem('bunker_calendar_roll', roll); } catch (e) {}

        // Immediate validation: Reject non-PSG Tech roll numbers
        const nonPsg = checkNonPsgCollege(roll);
        if (nonPsg) {
            showLoading(false);
            showError(nonPsg.message);
            return;
        }

        showLoading(true);
        showError(null);

        let data = null;

        // Strategy 1: Try our automated backend endpoint
        if (!forceDirectApi) {
            try {
                const querySem = (semester !== undefined && semester !== null) ? semester : (STATE.currentSemesterNo || STATE.currentSemester || '');
                const semParam = querySem ? `?sem=${encodeURIComponent(querySem)}` : '';
                const res = await fetch(`/api/calendar/${encodeURIComponent(roll)}${semParam}`);
                if (res.ok) {
                    data = await res.json();
                } else {
                    const errData = await res.json().catch(() => null);
                    if (errData && errData.error) {
                        showLoading(false);
                        showError(errData.error);
                        return;
                    }
                }
            } catch (err) {
                console.warn('Backend proxy fetch failed, trying direct API:', err);
            }
        }

        // Strategy 2: Direct query to official PSG Tech API if backend is unavailable or client-side only
        if (!data || !data.activities) {
            try {
                let allCalendars = STATE.allYearsIndex;
                if (!allCalendars) {
                    const idxRes = await fetch('https://academicschedule.psgtech.ac.in/api/calendar');
                    if (idxRes.ok) {
                        allCalendars = await idxRes.json();
                        STATE.allYearsIndex = allCalendars;
                    }
                }

                if (allCalendars && allCalendars.length) {
                    const latestYear = allCalendars[0].year || 2026;
                    STATE.academicYear = latestYear;
                    const student = parseStudentRoll(roll, latestYear, semester);
                    if (!student) {
                        showLoading(false);
                        showError(`Roll number "<strong>${escapeHtml(roll)}</strong>" was not recognized as a valid PSG College of Technology roll number. Please check your roll number.`);
                        return;
                    }
                    STATE.student = student;
                    if (student.semesterNo) STATE.currentSemesterNo = student.semesterNo;
                    if (student.semesterType) STATE.currentSemester = student.semesterType;

                    const yearEntry = allCalendars.find(y => y.year === latestYear) || allCalendars[0];
                    const planners = yearEntry.planner || [];
                    STATE.availablePlanners = planners;

                    const matched = matchPlannerClient(planners, student, STATE.currentSemester);
                    if (matched) {
                        const pRes = await fetch(`https://academicschedule.psgtech.ac.in/api/calendar/${latestYear}/planner/${matched.id}`);
                        if (pRes.ok) {
                            data = await pRes.json();
                            data.student = student;
                            data.matchedPlanner = matched;
                            data.semester = STATE.currentSemester;
                            data.semesterNo = STATE.currentSemesterNo;
                            data.academicYear = latestYear;
                            data.availablePlanners = planners;
                        }
                    }
                }
            } catch (err) {
                console.error('Direct API fetch failed:', err);
            }
        }

        // Strategy 3: Fallback to local cached static file
        if (!data || !data.activities) {
            try {
                const cacheRes = await fetch('/static/all_calendars_cache.json');
                if (cacheRes.ok) {
                    const cdata = await cacheRes.json();
                    const student = parseStudentRoll(roll, 2026);
                    STATE.student = student;
                    const plannersList = Object.values(cdata);
                    const matched = matchPlannerClient(plannersList, student, STATE.currentSemester);
                    if (matched && cdata[String(matched.id)]) {
                        data = cdata[String(matched.id)];
                        data.student = student;
                        data.matchedPlanner = matched;
                    }
                }
            } catch (err) {}
        }

        showLoading(false);

        if (data && (data.activities || data.name)) {
            STATE.plannerData = data;
            if (data.student) STATE.student = data.student;
            if (data.semesterNo) STATE.currentSemesterNo = data.semesterNo;
            if (data.semester) STATE.currentSemester = data.semester;
            if (data.availablePlanners) STATE.availablePlanners = data.availablePlanners;
            renderAll();
        } else {
            showError(`Could not find calendar for roll number "${roll}". Please verify your roll number.`);
        }
    }

    // --- Load by Planner ID Directly (e.g. for department dropdown) ---
    async function loadByPlannerId(plannerId, year) {
        year = year || STATE.academicYear || 2026;
        showLoading(true);
        try {
            let data = null;
            try {
                const res = await fetch(`/api/calendar/${plannerId}?year=${year}`);
                if (res.ok) data = await res.json();
            } catch (e) {}

            if (!data) {
                const res2 = await fetch(`https://academicschedule.psgtech.ac.in/api/calendar/${year}/planner/${plannerId}`);
                if (res2.ok) data = await res2.json();
            }

            if (data) {
                STATE.plannerData = data;
                renderAll();
            }
        } catch (e) {
            showError(`Failed to load planner ${plannerId}`);
        } finally {
            showLoading(false);
        }
    }

    // --- UI Rendering ---
    function renderAll() {
        const d = STATE.plannerData;
        if (!d) return;

        // Container visibility
        const resContainer = document.getElementById('calendar-result-container');
        if (resContainer) resContainer.classList.remove('hidden');

        // Render Student Profile Header
        renderStudentHeader();

        // Render Summary Badges & Metrics
        renderSummaryMetrics();

        // Render Activities / Milestones List
        renderActivities();

        // Render Public Holidays
        renderHolidays();

        // Render Monthly Calendar
        renderMonthGrid();

        // Populate Planner Switcher Dropdown
        populatePlannerDropdown();
    }

    function renderStudentHeader() {
        const s = STATE.student;
        const d = STATE.plannerData;
        const banner = document.getElementById('student-profile-banner');
        if (!banner) return;

        const titleEl = document.getElementById('student-degree-title');
        const metaEl = document.getElementById('student-meta-info');
        const plannerNameEl = document.getElementById('student-planner-name');
        const rollBadgeEl = document.getElementById('student-roll-badge');

        if (s) {
            const yearOfStudy = s.yearOfStudy || s.year_of_study || 1;
            const branchName = s.branchName || s.branch_name || 'Engineering';
            const admYear = s.admissionYear || s.admission_year || 2026;
            const acadYear = s.academicYear || s.academic_year || 2026;
            const degree = s.degree || 'B.E.';
            const roll = s.roll || STATE.currentRoll;

            const isLateral = s.isLateralEntry || s.is_lateral_entry;
            const semNo = s.semesterNo || s.semester_no || STATE.currentSemesterNo;
            const ecampusSynced = s.ecampusSynced || s.ecampus_synced;

            if (titleEl) titleEl.textContent = `${yearOfStudy}${getOrdinal(yearOfStudy)} Year ${degree} • ${branchName}`;
            if (metaEl) metaEl.textContent = `Batch of ${admYear} • Academic Year ${acadYear}–${String(acadYear + 1).slice(-2)}`;
            if (rollBadgeEl) {
                rollBadgeEl.textContent = roll;
                rollBadgeEl.classList.remove('hidden');
            }

            const entryBadge = document.getElementById('student-entry-badge');
            if (entryBadge) {
                if (isLateral) {
                    entryBadge.textContent = '⚡ Lateral Entry';
                    entryBadge.title = 'Admitted directly into 2nd Year (Polytechnic/Diploma entry)';
                    entryBadge.classList.remove('hidden');
                } else {
                    entryBadge.textContent = '';
                    entryBadge.classList.add('hidden');
                }
            }

            const semBadge = document.getElementById('student-sem-badge');
            if (semBadge) {
                if (semNo) {
                    semBadge.textContent = `Semester ${semNo}`;
                    semBadge.classList.remove('hidden');
                } else {
                    semBadge.textContent = '';
                    semBadge.classList.add('hidden');
                }
            }

            const ecampusBadge = document.getElementById('student-ecampus-badge');
            if (ecampusBadge) {
                if (ecampusSynced) {
                    ecampusBadge.classList.remove('hidden');
                } else {
                    ecampusBadge.classList.add('hidden');
                }
            }
        } else {
            if (titleEl) titleEl.textContent = d.name || 'PSG Tech Academic Calendar';
            if (metaEl) metaEl.textContent = `Academic Year ${d.calendarYear || 2026}`;
            if (rollBadgeEl) rollBadgeEl.classList.add('hidden');
            const entryBadge = document.getElementById('student-entry-badge');
            if (entryBadge) { entryBadge.textContent = ''; entryBadge.classList.add('hidden'); }
            const semBadge = document.getElementById('student-sem-badge');
            if (semBadge) { semBadge.textContent = ''; semBadge.classList.add('hidden'); }
            const ecampusBadge = document.getElementById('student-ecampus-badge');
            if (ecampusBadge) { ecampusBadge.textContent = ''; ecampusBadge.classList.add('hidden'); }
        }

        if (plannerNameEl) {
            plannerNameEl.textContent = d.name || (d.matchedPlanner ? d.matchedPlanner.name : '');
        }

        // Highlight Active Semester Tab
        const oddTab = document.getElementById('btn-sem-odd');
        const evenTab = document.getElementById('btn-sem-even');
        if (oddTab && evenTab) {
            if (STATE.currentSemester === 'even') {
                evenTab.className = 'px-3 py-1.5 rounded-lg text-xs font-extrabold transition active:scale-95 bg-indigo-600 text-white active-sem-tab';
                oddTab.className = 'px-3 py-1.5 rounded-lg text-xs font-extrabold transition active:scale-95 bg-transparent text-gray-400 hover:text-white';
            } else {
                oddTab.className = 'px-3 py-1.5 rounded-lg text-xs font-extrabold transition active:scale-95 bg-indigo-600 text-white active-sem-tab';
                evenTab.className = 'px-3 py-1.5 rounded-lg text-xs font-extrabold transition active:scale-95 bg-transparent text-gray-400 hover:text-white';
            }
        }

        // Highlight Active Semester Pill
        const activeSemNo = (s && (s.semesterNo || s.semester_no)) || STATE.currentSemesterNo;
        document.querySelectorAll('.sem-pill-btn').forEach(btn => {
            const semVal = parseInt(btn.getAttribute('data-sem'), 10);
            if (semVal === activeSemNo) {
                btn.className = 'sem-pill-btn px-2 py-0.5 rounded-md text-[10px] font-black transition active:scale-95 bg-indigo-600 text-white shadow';
            } else {
                btn.className = 'sem-pill-btn px-2 py-0.5 rounded-md text-[10px] font-bold transition active:scale-95 bg-white/5 hover:bg-white/10 text-gray-400 hover:text-white';
            }
        });
    }

    function renderSummaryMetrics() {
        const d = STATE.plannerData;
        if (!d) return;

        // Reopening date
        const reopenEl = document.getElementById('stat-reopen-date');
        if (reopenEl) reopenEl.textContent = formatDate(d.startDate);

        // Last working day
        const lastEl = document.getElementById('stat-last-date');
        if (lastEl) lastEl.textContent = formatDate(d.lastDate);

        // Working days & progress
        const totalDays = d.totalWorkingDays || 0;
        const remainingDays = (d.remainingDays !== undefined && d.remainingDays !== null) ? d.remainingDays : 0;
        const completedDays = Math.max(0, totalDays - remainingDays);
        const percent = totalDays > 0 ? Math.min(100, Math.round((completedDays / totalDays) * 100)) : 0;

        const workingDaysEl = document.getElementById('stat-working-days');
        if (workingDaysEl) {
            workingDaysEl.textContent = `${remainingDays} Remaining / ${totalDays} Total`;
        }

        const progressBar = document.getElementById('working-days-progress-bar');
        if (progressBar) {
            progressBar.style.width = `${percent}%`;
        }
        const progressLabel = document.getElementById('working-days-percent-label');
        if (progressLabel) {
            progressLabel.textContent = `${percent}% elapsed (${completedDays} days done)`;
        }

        // Next Upcoming Milestone
        renderNextMilestone(d.activities || []);
    }

    function renderNextMilestone(activities) {
        const container = document.getElementById('next-milestone-card');
        if (!container) return;

        const now = new Date();
        now.setHours(0, 0, 0, 0);

        let nextAct = null;
        let minDiff = Infinity;

        activities.forEach(a => {
            if (!a.date) return;
            const diff = getDaysDiff(a.date);
            if (diff !== null && diff >= 0 && diff < minDiff) {
                minDiff = diff;
                nextAct = a;
            }
        });

        if (nextAct) {
            const nameEl = document.getElementById('next-milestone-name');
            const dateEl = document.getElementById('next-milestone-date');
            const countdownEl = document.getElementById('next-milestone-countdown');

            if (nameEl) nameEl.textContent = nextAct.name;
            if (dateEl) dateEl.textContent = formatDate(nextAct.date);
            if (countdownEl) {
                if (minDiff === 0) {
                    countdownEl.textContent = 'TODAY!';
                    countdownEl.className = 'px-2.5 py-1 rounded-full text-xs font-black bg-rose-500 text-white animate-pulse';
                } else if (minDiff === 1) {
                    countdownEl.textContent = 'Tomorrow';
                    countdownEl.className = 'px-2.5 py-1 rounded-full text-xs font-black bg-amber-500 text-white';
                } else {
                    countdownEl.textContent = `In ${minDiff} days`;
                    countdownEl.className = 'px-2.5 py-1 rounded-full text-xs font-black bg-indigo-600 text-white';
                }
            }
            container.classList.remove('hidden');
        } else {
            container.classList.add('hidden');
        }
    }

    function renderActivities() {
        const d = STATE.plannerData;
        const container = document.getElementById('activities-table-body');
        if (!container || !d) return;

        const activities = d.activities || [];
        const filter = STATE.activeCategoryFilter;
        const query = (STATE.searchQuery || '').toLowerCase();

        const filtered = activities.filter(a => {
            const cat = categorize(a.name, false);
            if (filter !== 'all' && cat.type !== filter) return false;
            if (query && !a.name.toLowerCase().includes(query)) return false;
            return true;
        });

        if (!filtered.length) {
            container.innerHTML = `
                <tr>
                    <td colspan="4" class="px-4 py-8 text-center text-gray-400 text-xs">
                        <i class="fas fa-search mb-2 text-base text-gray-600"></i><br>
                        No activities match the current filter or search query.
                    </td>
                </tr>
            `;
            return;
        }

        let html = '';
        filtered.forEach((act, idx) => {
            const cat = categorize(act.name, false);
            const diff = getDaysDiff(act.date);
            const dateFormatted = formatDate(act.date);
            const gcalUrl = makeGoogleCalendarUrl(act.name, act.date);

            let statusBadge = '';
            if (diff === null) {
                statusBadge = '<span class="text-[10px] text-gray-500 font-bold">TBA</span>';
            } else if (diff < 0) {
                statusBadge = '<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-white/5 text-gray-400 border border-white/10"><i class="fas fa-check mr-1 text-[9px] text-emerald-400"></i>Completed</span>';
            } else if (diff === 0) {
                statusBadge = '<span class="px-2.5 py-0.5 rounded-md text-[10px] font-black bg-rose-500/20 text-rose-300 border border-rose-500/40 animate-pulse">TODAY</span>';
            } else if (diff <= 7) {
                statusBadge = `<span class="px-2 py-0.5 rounded-md text-[10px] font-black bg-amber-500/20 text-amber-300 border border-amber-500/30">In ${diff} days</span>`;
            } else {
                statusBadge = `<span class="px-2 py-0.5 rounded-md text-[10px] font-bold bg-indigo-500/15 text-indigo-300 border border-indigo-500/25">${diff} days left</span>`;
            }

            html += `
                <tr class="border-b border-white/5 hover:bg-white/[0.03] transition-colors group">
                    <td class="py-3 px-3 sm:px-4">
                        <div class="flex items-start gap-2.5">
                            <span class="w-6 h-6 rounded-lg ${cat.badgeClass} flex items-center justify-center flex-shrink-0 text-[11px] mt-0.5">
                                <i class="fas ${cat.icon}"></i>
                            </span>
                            <div>
                                <div class="font-bold text-xs sm:text-sm text-white flex items-center gap-1.5 flex-wrap">
                                    <span>${escapeHtml(act.name)}</span>
                                    <span class="text-[9px] uppercase tracking-wider font-extrabold px-1.5 py-0.2 rounded ${cat.badgeClass} opacity-80">${cat.label}</span>
                                </div>
                                <div class="text-[10px] text-gray-400 mt-0.5 flex items-center gap-2">
                                    <span>Working Day ${act.relativeToStart !== undefined ? act.relativeToStart : (idx + 1)}</span>
                                    ${act.relativeDays ? `<span>&bull; +${act.relativeDays} days gap</span>` : ''}
                                </div>
                            </div>
                        </div>
                    </td>
                    <td class="py-3 px-3 sm:px-4 whitespace-nowrap text-xs text-gray-300 font-medium">
                        ${dateFormatted}
                    </td>
                    <td class="py-3 px-3 sm:px-4 whitespace-nowrap text-right sm:text-left">
                        ${statusBadge}
                    </td>
                    <td class="py-3 px-3 sm:px-4 whitespace-nowrap text-right">
                        <a href="${gcalUrl}" target="_blank" rel="noopener noreferrer"
                            class="p-1.5 rounded-lg bg-white/5 hover:bg-white/15 text-gray-400 hover:text-indigo-300 transition text-xs inline-flex items-center gap-1"
                            title="Add to Google Calendar">
                            <i class="fas fa-calendar-plus text-[11px]"></i>
                        </a>
                    </td>
                </tr>
            `;
        });

        container.innerHTML = html;
    }

    function renderHolidays() {
        const d = STATE.plannerData;
        const container = document.getElementById('holidays-list-container');
        if (!container || !d) return;

        const holidays = (d.calendar && d.calendar.holidays) ? d.calendar.holidays : [];
        if (!holidays.length) {
            container.innerHTML = '<p class="text-xs text-gray-500 py-4 text-center">No holidays listed.</p>';
            return;
        }

        let html = '<div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-2.5">';
        holidays.forEach(h => {
            const diff = getDaysDiff(h.date);
            const dateStr = formatDate(h.date);
            let pill = '';
            if (diff !== null) {
                if (diff < 0) pill = '<span class="text-[9px] text-gray-500">Past</span>';
                else if (diff === 0) pill = '<span class="text-[9px] text-emerald-400 font-bold">Today</span>';
                else pill = `<span class="text-[9px] text-emerald-300 font-bold">In ${diff}d</span>`;
            }

            html += `
                <div class="cal-glass p-3 rounded-xl flex items-center justify-between gap-2 border border-emerald-500/20 bg-emerald-950/10">
                    <div class="flex items-center gap-2.5 min-w-0">
                        <span class="w-7 h-7 rounded-lg bg-emerald-500/20 text-emerald-300 flex items-center justify-center text-xs flex-shrink-0">
                            <i class="fas fa-umbrella-beach"></i>
                        </span>
                        <div class="min-w-0">
                            <h4 class="text-xs font-bold text-white truncate">${escapeHtml(h.name)}</h4>
                            <p class="text-[10px] text-gray-400">${dateStr}</p>
                        </div>
                    </div>
                    ${pill}
                </div>
            `;
        });
        html += '</div>';
        container.innerHTML = html;
    }

    function renderMonthGrid() {
        const container = document.getElementById('month-grid-cells');
        const titleEl = document.getElementById('cal-month-title');
        if (!container) return;

        const curr = STATE.calendarMonthDate;
        const year = curr.getFullYear();
        const month = curr.getMonth();

        if (titleEl) {
            titleEl.textContent = curr.toLocaleDateString('en-IN', { month: 'long', year: 'numeric' });
        }

        const firstDayOfMonth = new Date(year, month, 1);
        const lastDayOfMonth = new Date(year, month + 1, 0);

        // In India / Monday start: 0=Sun -> 6, 1=Mon -> 0
        let startOffset = firstDayOfMonth.getDay() - 1;
        if (startOffset === -1) startOffset = 6;

        const totalDays = lastDayOfMonth.getDate();
        const todayStr = toDateKey(new Date());

        // Map events by Date Key 'YYYY-MM-DD'
        const eventMap = {};
        const d = STATE.plannerData;
        if (d) {
            (d.activities || []).forEach(a => {
                if (!a.date) return;
                const k = toDateKey(new Date(a.date));
                if (!eventMap[k]) eventMap[k] = [];
                eventMap[k].push({ name: a.name, ...categorize(a.name, false) });
            });
            if (d.calendar && d.calendar.holidays) {
                d.calendar.holidays.forEach(h => {
                    if (!h.date) return;
                    const k = toDateKey(new Date(h.date));
                    if (!eventMap[k]) eventMap[k] = [];
                    eventMap[k].push({ name: h.name, ...categorize(h.name, true) });
                });
            }
        }

        let html = '';

        // Empty padding cells before first day
        for (let i = 0; i < startOffset; i++) {
            html += '<div class="cal-day-cell empty-cell aspect-square sm:aspect-auto sm:min-h-[70px] rounded-xl bg-white/[0.01] opacity-30"></div>';
        }

        // Days
        for (let day = 1; day <= totalDays; day++) {
            const thisDate = new Date(year, month, day);
            const dateKey = toDateKey(thisDate);
            const isToday = (dateKey === todayStr);
            const dayOfWeek = thisDate.getDay();
            const isWeekend = (dayOfWeek === 0 || dayOfWeek === 6);
            const events = eventMap[dateKey] || [];

            let dotsHtml = '';
            events.slice(0, 3).forEach(ev => {
                let dotColor = '#6366f1';
                if (ev.type === 'catest') dotColor = '#a855f7';
                else if (ev.type === 'tutorial') dotColor = '#f59e0b';
                else if (ev.type === 'exam') dotColor = '#ef4444';
                else if (ev.type === 'holiday') dotColor = '#10b981';
                dotsHtml += `<span class="w-1.5 h-1.5 rounded-full flex-shrink-0" style="background-color: ${dotColor};" title="${escapeHtml(ev.name)}"></span>`;
            });
            if (events.length > 3) {
                dotsHtml += `<span class="text-[8px] font-black text-gray-400">+${events.length - 3}</span>`;
            }

            html += `
                <div onclick="window.calendarApp.openDayModal('${dateKey}')"
                    class="cal-day-cell relative aspect-square sm:aspect-auto sm:min-h-[70px] p-1.5 sm:p-2 rounded-xl sm:rounded-2xl transition border cursor-pointer flex flex-col justify-between
                    ${isToday ? 'border-indigo-500 bg-indigo-950/40 shadow-sm shadow-indigo-500/30 font-black' : 'border-white/5 bg-white/[0.02] hover:bg-white/[0.06] hover:border-white/20'}">
                    <div class="flex items-center justify-between">
                        <span class="text-xs ${isToday ? 'text-indigo-300 font-extrabold' : isWeekend ? 'text-gray-400' : 'text-gray-200 font-semibold'}">${day}</span>
                        ${events.length ? `<span class="text-[9px] font-bold text-indigo-400 hidden sm:inline">${events.length}</span>` : ''}
                    </div>
                    <div class="flex items-center gap-1 flex-wrap mt-1">
                        ${dotsHtml}
                    </div>
                </div>
            `;
        }

        container.innerHTML = html;
    }

    function populatePlannerDropdown() {
        const select = document.getElementById('direct-planner-select');
        if (!select) return;

        const planners = STATE.availablePlanners || [];
        if (!planners.length) return;

        let html = '<option value="">-- Or Choose Any College Calendar --</option>';
        planners.forEach(p => {
            const isSelected = STATE.plannerData && (STATE.plannerData.id === p.id);
            html += `<option value="${p.id}" ${isSelected ? 'selected' : ''}>${escapeHtml(p.name)}</option>`;
        });
        select.innerHTML = html;
    }

    // --- Day Modal / Drawer ---
    function openDayModal(dateKey) {
        const d = STATE.plannerData;
        if (!d) return;

        const modal = document.getElementById('day-detail-drawer');
        const titleEl = document.getElementById('drawer-date-title');
        const listEl = document.getElementById('drawer-events-list');
        if (!modal || !titleEl || !listEl) return;

        const parts = dateKey.split('-');
        const dateObj = new Date(parts[0], parts[1] - 1, parts[2]);
        titleEl.textContent = dateObj.toLocaleDateString('en-IN', {
            weekday: 'long',
            day: 'numeric',
            month: 'long',
            year: 'numeric'
        });

        const dayEvents = [];
        (d.activities || []).forEach(a => {
            if (a.date && toDateKey(new Date(a.date)) === dateKey) {
                dayEvents.push({ name: a.name, ...categorize(a.name, false) });
            }
        });
        if (d.calendar && d.calendar.holidays) {
            d.calendar.holidays.forEach(h => {
                if (h.date && toDateKey(new Date(h.date)) === dateKey) {
                    dayEvents.push({ name: h.name, ...categorize(h.name, true) });
                }
            });
        }

        if (!dayEvents.length) {
            listEl.innerHTML = '<p class="text-xs text-gray-400 py-6 text-center">No special milestones or tests scheduled on this date.</p>';
        } else {
            let html = '';
            dayEvents.forEach(ev => {
                html += `
                    <div class="cal-glass p-3 rounded-xl border border-white/10 flex items-start gap-3">
                        <span class="w-7 h-7 rounded-lg ${ev.badgeClass} flex items-center justify-center text-xs flex-shrink-0 mt-0.5">
                            <i class="fas ${ev.icon}"></i>
                        </span>
                        <div>
                            <span class="text-[9px] uppercase tracking-wider font-black px-1.5 py-0.5 rounded ${ev.badgeClass} opacity-80">${ev.label}</span>
                            <h4 class="text-xs sm:text-sm font-bold text-white mt-1">${escapeHtml(ev.name)}</h4>
                        </div>
                    </div>
                `;
            });
            listEl.innerHTML = html;
        }

        modal.classList.remove('hidden');
        modal.style.display = 'flex';
    }

    function closeDayModal() {
        const modal = document.getElementById('day-detail-drawer');
        if (modal) {
            modal.classList.add('hidden');
            modal.style.display = 'none';
        }
    }

    // --- View Switching ---
    function setView(view) {
        STATE.currentView = view;
        const agendaSec = document.getElementById('view-agenda');
        const monthSec = document.getElementById('view-month');
        const holidaySec = document.getElementById('view-holidays');

        const btnAgenda = document.getElementById('tab-btn-agenda');
        const btnMonth = document.getElementById('tab-btn-month');
        const btnHolidays = document.getElementById('tab-btn-holidays');

        [agendaSec, monthSec, holidaySec].forEach(el => el && el.classList.add('hidden'));
        [btnAgenda, btnMonth, btnHolidays].forEach(btn => btn && btn.classList.remove('active-view-tab'));

        if (view === 'month') {
            if (monthSec) monthSec.classList.remove('hidden');
            if (btnMonth) btnMonth.classList.add('active-view-tab');
            renderMonthGrid();
        } else if (view === 'holidays') {
            if (holidaySec) holidaySec.classList.remove('hidden');
            if (btnHolidays) btnHolidays.classList.add('active-view-tab');
        } else {
            if (agendaSec) agendaSec.classList.remove('hidden');
            if (btnAgenda) btnAgenda.classList.add('active-view-tab');
        }
    }

    function setCategoryFilter(cat) {
        STATE.activeCategoryFilter = cat;
        document.querySelectorAll('.cat-filter-btn').forEach(b => {
            if (b.getAttribute('data-cat') === cat) {
                b.classList.add('active-cat-btn');
            } else {
                b.classList.remove('active-cat-btn');
            }
        });
        renderActivities();
    }

    function changeMonth(delta) {
        const curr = STATE.calendarMonthDate;
        STATE.calendarMonthDate = new Date(curr.getFullYear(), curr.getMonth() + delta, 1);
        renderMonthGrid();
    }

    function jumpToToday() {
        STATE.calendarMonthDate = new Date();
        renderMonthGrid();
    }

    function switchSemester(sem) {
        sem = (sem || 'odd').toLowerCase();
        STATE.currentSemester = sem;
        const s = STATE.student;
        if (s) {
            const y = s.yearOfStudy || s.year_of_study || 1;
            STATE.currentSemesterNo = (sem === 'even') ? (y * 2) : (y * 2 - 1);
            loadCalendar(STATE.currentRoll, STATE.currentSemesterNo);
        } else {
            loadCalendar(STATE.currentRoll, sem);
        }
    }

    function selectSemester(semNo) {
        if (!semNo) return;
        const semInt = parseInt(semNo, 10);
        STATE.currentSemesterNo = semInt;
        STATE.currentSemester = (semInt % 2 === 1) ? 'odd' : 'even';
        loadCalendar(STATE.currentRoll, semInt);
    }

    // --- Utilities ---
    function toDateKey(d) {
        const y = d.getFullYear();
        const m = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${y}-${m}-${day}`;
    }

    function getOrdinal(n) {
        const s = ['th', 'st', 'nd', 'rd'];
        const v = n % 100;
        return s[(v - 20) % 10] || s[v] || s[0];
    }

    function makeGoogleCalendarUrl(title, dateStr) {
        if (!dateStr) return '#';
        try {
            const d = new Date(dateStr);
            const dStr = d.toISOString().replace(/-|:|\.\d+/g, '').substring(0, 8);
            const nextD = new Date(d);
            nextD.setDate(d.getDate() + 1);
            const nextStr = nextD.toISOString().replace(/-|:|\.\d+/g, '').substring(0, 8);
            return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${encodeURIComponent(title)}&dates=${dStr}/${nextStr}&details=PSG+Tech+Academic+Calendar&location=PSG+College+of+Technology`;
        } catch (e) {
            return '#';
        }
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    function showLoading(show) {
        const el = document.getElementById('cal-loader');
        if (el) el.style.display = show ? 'flex' : 'none';
    }

    function showError(msg) {
        const errCard = document.getElementById('cal-error-card');
        const errMsg = document.getElementById('cal-error-msg');
        const resContainer = document.getElementById('calendar-result-container');
        if (!errCard) return;
        if (msg) {
            if (errMsg) errMsg.innerHTML = msg;
            errCard.classList.remove('hidden');
            if (resContainer) resContainer.classList.add('hidden');
        } else {
            errCard.classList.add('hidden');
        }
    }

    // --- Initialization ---
    function init() {
        // Check URL params e.g. ?roll=25L101 or ?sem=odd
        const urlParams = new URLSearchParams(window.location.search);
        let roll = urlParams.get('roll');
        let sem = urlParams.get('sem');

        if (!roll) {
            // Check localStorage
            try {
                roll = localStorage.getItem('bunker_calendar_roll') || localStorage.getItem('bunker_roll_number');
            } catch (e) {}
        }

        // Setup Event Listeners
        const input = document.getElementById('roll-input');
        const form = document.getElementById('roll-search-form');

        if (form) {
            form.addEventListener('submit', function (e) {
                e.preventDefault();
                const val = input ? input.value : '';
                if (val) loadCalendar(val);
            });
        }

        if (input) {
            // Auto uppercase as you type
            input.addEventListener('input', function () {
                this.value = cleanRollNumber(this.value);
                if (this.value.length >= 6 && this.value.length <= 8) {
                    // Fast auto-trigger if complete
                }
            });
            input.addEventListener('keypress', function (e) {
                if (e.key === 'Enter') {
                    e.preventDefault();
                    if (this.value) loadCalendar(this.value);
                }
            });
        }

        const searchFilter = document.getElementById('activity-search-input');
        if (searchFilter) {
            searchFilter.addEventListener('input', function () {
                STATE.searchQuery = this.value;
                renderActivities();
            });
        }

        const directSelect = document.getElementById('direct-planner-select');
        if (directSelect) {
            directSelect.addEventListener('change', function () {
                if (this.value) loadByPlannerId(this.value);
            });
        }

        // Default initial load
        if (roll) {
            if (input) input.value = roll;
            loadCalendar(roll, sem);
        } else {
            // Load 25L101 as default showcase or fetch calendar index
            loadCalendar('25L101', sem || 'odd');
        }
    }

    // Export global controller
    window.calendarApp = {
        loadCalendar: loadCalendar,
        loadByPlannerId: loadByPlannerId,
        switchSemester: switchSemester,
        selectSemester: selectSemester,
        setView: setView,
        setCategoryFilter: setCategoryFilter,
        changeMonth: changeMonth,
        jumpToToday: jumpToToday,
        openDayModal: openDayModal,
        closeDayModal: closeDayModal
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }
})();
