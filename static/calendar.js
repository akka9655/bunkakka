/**
 * BUNKER ACADEMIC CALENDAR & EVENT PLANNER
 * Mobile-First, Single Calendar Mode, Dynamic Color-Changing Event Mode, Touch Swipe Month Switching.
 */

(function () {
    'use strict';

    // Adaptive performance mode for 60fps / 120fps on any mobile phone
    const savedPerf = localStorage.getItem('bunker_perf_mode');
    if (savedPerf) {
        document.documentElement.setAttribute('data-perf', savedPerf);
    } else {
        const ram = navigator.deviceMemory;
        const cores = navigator.hardwareConcurrency;
        const saveData = navigator.connection && navigator.connection.saveData;
        const reducedMotion = window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
        if (reducedMotion || saveData || (ram && ram <= 4) || (cores && cores <= 4)) {
            document.documentElement.setAttribute('data-perf', 'low');
        } else {
            document.documentElement.setAttribute('data-perf', 'high');
        }
    }

    // --- Department Definitions ---
    const DEPARTMENTS = [
        { id: 'be_3_4', name: '3rd & 4th Year BE / B.Tech', shortName: '3rd & 4th BE', plannerOdd: 32, plannerEven: 40, color: '#6366f1' },
        { id: 'be_2', name: '2nd Year BE / B.Tech', shortName: '2nd Year BE', plannerOdd: 33, plannerEven: 41, color: '#a855f7' },
        { id: 'be_1', name: '1st Year BE / B.Tech', shortName: '1st Year BE', plannerOdd: 39, plannerEven: 42, color: '#ec4899' },
        { id: 'bsc_msc', name: 'B.Sc & M.Sc (All Years)', shortName: 'B.Sc / M.Sc', plannerOdd: 32, plannerEven: 40, color: '#06b6d4' },
        { id: 'pg', name: 'ME / M.Tech', shortName: 'ME / M.Tech', plannerOdd: 32, plannerEven: 40, color: '#f59e0b' },
        { id: 'mca', name: 'MCA (1st & 2nd Year)', shortName: 'MCA', plannerOdd: 34, plannerEven: 43, color: '#14b8a6' },
        { id: 'sandwich', name: 'BE Sandwich (SW)', shortName: 'BE Sandwich', plannerOdd: 35, plannerEven: 44, color: '#10b981' },
        { id: 'all', name: 'All Departments (Combined)', shortName: 'All Combined', plannerOdd: null, plannerEven: null, color: '#8b5cf6' }
    ];

    // --- Application State ---
    const STATE = {
        allPlanners: {},
        userRoll: '',
        userDeptId: null,
        userDeptName: '',

        // Single Calendar Mode vs All
        selectedDept: 'be_3_4',

        // Event Mode (Colors calendar based on test/exam clashes)
        isEventMode: false,
        plannerAudience: 'all', // 'all', 'ug', 'pg', 'current'

        searchQuery: '',
        currentView: 'month', // 'month' or 'agenda'
        currentMonth: new Date(2026, 8, 1), // Default to September 2026
        selectedDate: null
    };

    // --- Roll Number Parser & Auto Dept Detection ---
    function parseRoll(roll) {
        if (!roll || roll.length < 2) return null;
        roll = roll.trim().toUpperCase();
        try {
            const admissionYear = int2DigitYear(roll.substring(0, 2));
            const now = new Date();
            const currYear = now.getFullYear();
            const currMonth = now.getMonth() + 1;
            const acadYear = (currMonth >= 1 && currMonth <= 5) ? currYear - 1 : currYear;
            const yearOfStudy = Math.max(1, Math.min(5, acadYear - admissionYear + 1));

            const letters = roll.substring(2);
            let deptId = 'be_3_4';
            let deptName = '3rd & 4th Year BE / B.Tech';

            const singleLetter = letters.charAt(0);
            const doubleLetter = letters.substring(0, 2);

            if (['S', 'X'].includes(singleLetter) || ['SA', 'FD', 'XW', 'XT', 'XD', 'XC'].includes(doubleLetter)) {
                deptId = 'bsc_msc';
                deptName = 'B.Sc & M.Sc (All Years)';
            } else if (['MX'].includes(doubleLetter)) {
                deptId = 'mca';
                deptName = 'MCA';
            } else if (['AE', 'NB', 'ZC', 'UC', 'EE', 'MD', 'MN', 'PP', 'ED', 'CS', 'LV', 'BT', 'LN', 'TT', 'SE', 'CE', 'EC', 'IT'].includes(doubleLetter)) {
                deptId = 'pg';
                deptName = 'ME / M.Tech';
            } else {
                if (yearOfStudy === 1) {
                    deptId = 'be_1';
                    deptName = '1st Year BE / B.Tech';
                } else if (yearOfStudy === 2) {
                    deptId = 'be_2';
                    deptName = '2nd Year BE / B.Tech';
                } else if (yearOfStudy >= 5) {
                    deptId = 'sandwich';
                    deptName = 'BE Sandwich (SW)';
                } else {
                    deptId = 'be_3_4';
                    deptName = '3rd & 4th Year BE / B.Tech';
                }
            }

            return { roll, deptId, deptName, yearOfStudy };
        } catch (e) {
            return null;
        }
    }

    function int2DigitYear(str) {
        const val = parseInt(str, 10);
        return isNaN(val) ? 2024 : 2000 + val;
    }

    // --- Categorize Academic Activities ---
    function categorizeActivity(name, isHoliday) {
        if (isHoliday) {
            return { type: 'holiday', label: 'Holiday', badgeClass: 'badge-holiday', icon: 'fa-tree' };
        }
        const n = (name || '').toLowerCase();
        if (n.includes('assessment tutorial') || n.includes('tutorial')) {
            return { type: 'at', label: 'Tutorial', badgeClass: 'badge-at', icon: 'fa-book-open' };
        }
        if (n.includes('ca test') || n.includes('ca 1') || n.includes('ca 2') || n.includes('ca 3') || n.includes('practice test')) {
            return { type: 'ca', label: 'CA Test', badgeClass: 'badge-ca', icon: 'fa-pen-to-square' };
        }
        if (n.includes('semester exam') || n.includes('end semester exam')) {
            return { type: 'sem', label: 'Semester Exam', badgeClass: 'badge-sem', icon: 'fa-graduation-cap' };
        }
        if (n.includes('laboratory exam') || n.includes('lab exam')) {
            return { type: 'lab', label: 'Lab Exam', badgeClass: 'badge-lab', icon: 'fa-flask' };
        }
        return { type: 'milestone', label: 'Milestone', badgeClass: 'badge-milestone', icon: 'fa-calendar-check' };
    }

    function getEventColor(cat) {
        switch (cat) {
            case 'ca': return '#8b5cf6';
            case 'at': return '#f59e0b';
            case 'sem': return '#ef4444';
            case 'lab': return '#06b6d4';
            case 'holiday': return '#10b981';
            default: return '#94a3b8';
        }
    }

    function toDateKey(d) {
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        return `${year}-${month}-${day}`;
    }

    // --- Fetch Academic Data ---
    async function loadCalendarData() {
        showLoading(true);
        let data = null;

        try {
            const res = await fetch('/api/all-calendars');
            if (res.ok) {
                const json = await res.json();
                if (json.success && json.planners && Object.keys(json.planners).length > 0) {
                    data = json.planners;
                }
            }
        } catch (e) {
            console.warn('Network fetch /api/all-calendars failed, falling back to static cache:', e);
        }

        if (!data) {
            try {
                const res = await fetch('/static/all_calendars_cache.json');
                if (res.ok) {
                    data = await res.json();
                }
            } catch (e) {
                console.error('Static all_calendars_cache.json fetch failed:', e);
            }
        }

        if (data) {
            STATE.allPlanners = data;
            try { localStorage.setItem('bunker_all_calendars_cache', JSON.stringify(data)); } catch (err) {}
        } else {
            const cached = localStorage.getItem('bunker_all_calendars_cache');
            if (cached) {
                try { STATE.allPlanners = JSON.parse(cached); } catch (e) {}
            }
        }

        showLoading(false);
        initApp();
    }

    function showLoading(show) {
        const loader = document.getElementById('cal-global-loader');
        if (loader) loader.style.display = show ? 'flex' : 'none';
    }

    // --- Extract Active Events (Single Calendar or All) ---
    function getActiveEvents() {
        const events = [];
        const seen = new Set();

        const deptsToInclude = (STATE.selectedDept === 'all')
            ? DEPARTMENTS.filter(d => d.id !== 'all')
            : DEPARTMENTS.filter(d => d.id === STATE.selectedDept);

        deptsToInclude.forEach(dept => {
            [dept.plannerOdd, dept.plannerEven].forEach(pid => {
                if (!pid) return;
                const p = STATE.allPlanners[String(pid)];
                if (!p) return;

                // Activities
                if (p.activities && Array.isArray(p.activities)) {
                    p.activities.forEach(a => {
                        if (!a.date || !a.name) return;
                        const cat = categorizeActivity(a.name, false);

                        if (STATE.searchQuery) {
                            const q = STATE.searchQuery.toLowerCase();
                            if (!a.name.toLowerCase().includes(q) && !dept.name.toLowerCase().includes(q)) return;
                        }

                        const key = `${a.name}_${a.date}_${dept.id}`;
                        if (!seen.has(key)) {
                            seen.add(key);
                            events.push({
                                id: a.id || key,
                                name: a.name,
                                date: new Date(a.date),
                                rawDate: a.date,
                                deptId: dept.id,
                                deptName: dept.name,
                                deptShortName: dept.shortName,
                                deptColor: dept.color,
                                category: cat.type,
                                catLabel: cat.label,
                                badgeClass: cat.badgeClass,
                                icon: cat.icon,
                                isHoliday: false
                            });
                        }
                    });
                }

                // Holidays
                if (p.calendar && p.calendar.holidays && Array.isArray(p.calendar.holidays)) {
                    p.calendar.holidays.forEach(h => {
                        if (!h.date || !h.name) return;
                        const cat = categorizeActivity(h.name, true);

                        if (STATE.searchQuery) {
                            const q = STATE.searchQuery.toLowerCase();
                            if (!h.name.toLowerCase().includes(q)) return;
                        }

                        const key = `holiday_${h.name}_${h.date}`;
                        if (!seen.has(key)) {
                            seen.add(key);
                            events.push({
                                id: key,
                                name: h.name,
                                date: new Date(h.date),
                                rawDate: h.date,
                                deptId: 'all',
                                deptName: 'PSG Tech',
                                deptShortName: 'Holiday',
                                deptColor: '#10b981',
                                category: 'holiday',
                                catLabel: 'College Holiday',
                                badgeClass: 'badge-holiday',
                                icon: 'fa-tree',
                                isHoliday: true
                            });
                        }
                    });
                }
            });
        });

        events.sort((a, b) => a.date - b.date);
        return events;
    }

    // --- Clash Evaluation for Event Mode ---
    function evaluateMonthClashes(year, month) {
        let targetDeptIds = [];
        if (STATE.plannerAudience === 'all') {
            targetDeptIds = DEPARTMENTS.filter(d => d.id !== 'all').map(d => d.id);
        } else if (STATE.plannerAudience === 'ug') {
            targetDeptIds = ['be_3_4', 'be_2', 'be_1', 'sandwich'];
        } else if (STATE.plannerAudience === 'pg') {
            targetDeptIds = ['pg', 'mca', 'bsc_msc'];
        } else {
            targetDeptIds = (STATE.selectedDept === 'all') ? ['be_3_4', 'be_2', 'be_1'] : [STATE.selectedDept];
        }

        // Collect all blocker exams across target depts
        const blockers = [];
        DEPARTMENTS.forEach(dept => {
            if (targetDeptIds.includes(dept.id)) {
                [dept.plannerOdd, dept.plannerEven].forEach(pid => {
                    const p = STATE.allPlanners[String(pid)];
                    if (p && p.activities) {
                        p.activities.forEach(a => {
                            if (!a.date || !a.name) return;
                            const cat = categorizeActivity(a.name, false);
                            if (['ca', 'at', 'sem', 'lab'].includes(cat.type)) {
                                blockers.push({
                                    date: new Date(a.date),
                                    name: a.name,
                                    deptShort: dept.shortName,
                                    type: cat.type
                                });
                            }
                        });
                    }
                });
            }
        });

        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const evaluations = {};

        for (let dayNum = 1; dayNum <= daysInMonth; dayNum++) {
            const currentDay = new Date(year, month, dayNum);
            const dateKey = toDateKey(currentDay);

            let clashes = [];
            let minDistanceToExam = 999;
            let nearestExamInfo = '';

            blockers.forEach(b => {
                const diffDays = Math.round((b.date - currentDay) / (1000 * 60 * 60 * 24));
                const absDiff = Math.abs(diffDays);

                if (absDiff === 0) {
                    clashes.push(`${b.deptShort}: ${b.name}`);
                }
                if (absDiff < minDistanceToExam) {
                    minDistanceToExam = absDiff;
                    nearestExamInfo = `${b.name} (${b.deptShort})`;
                }
            });

            let status = 'best';
            let summary = '';

            if (clashes.length > 0) {
                status = 'clash';
                summary = `Exam Clash: ${clashes.join('; ')}`;
            } else if (minDistanceToExam <= 2) {
                status = 'caution';
                summary = `Near exam window (${minDistanceToExam} day${minDistanceToExam === 1 ? '' : 's'} from ${nearestExamInfo})`;
            } else {
                status = 'best';
                summary = 'Ideal Date: Clash-free with zero scheduled tests or exams';
            }

            evaluations[dateKey] = {
                status,
                summary,
                clashes,
                minDistanceToExam
            };
        }

        return evaluations;
    }

    // --- Google Calendar Month View Renderer ---
    function renderMonthView() {
        const gridContainer = document.getElementById('month-grid-cells');
        const monthTitle = document.getElementById('cal-month-title');
        if (!gridContainer) return;

        gridContainer.innerHTML = '';
        const cur = STATE.currentMonth;
        const year = cur.getFullYear();
        const month = cur.getMonth();

        const monthName = cur.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
        if (monthTitle) monthTitle.textContent = monthName;

        // Active events
        const events = getActiveEvents();
        const eventsByDate = {};
        events.forEach(e => {
            const k = toDateKey(e.date);
            if (!eventsByDate[k]) eventsByDate[k] = [];
            eventsByDate[k].push(e);
        });

        // Clash evaluations if Event Mode is ON
        const clashEvaluations = STATE.isEventMode ? evaluateMonthClashes(year, month) : {};

        // Month days alignment (Monday = 0)
        const firstDayOfMonth = new Date(year, month, 1);
        let startDay = firstDayOfMonth.getDay();
        startDay = (startDay === 0) ? 6 : startDay - 1;

        const daysInMonth = new Date(year, month + 1, 0).getDate();
        const daysInPrevMonth = new Date(year, month, 0).getDate();

        const todayKey = toDateKey(new Date());

        // Previous month filler days
        for (let i = startDay - 1; i >= 0; i--) {
            const dayNum = daysInPrevMonth - i;
            const d = new Date(year, month - 1, dayNum);
            const cell = createDayCell(d, dayNum, true, eventsByDate, todayKey, clashEvaluations);
            gridContainer.appendChild(cell);
        }

        // Current month days
        for (let dayNum = 1; dayNum <= daysInMonth; dayNum++) {
            const d = new Date(year, month, dayNum);
            const cell = createDayCell(d, dayNum, false, eventsByDate, todayKey, clashEvaluations);
            gridContainer.appendChild(cell);
        }

        // Next month filler days to complete grid
        const totalCells = startDay + daysInMonth;
        const nextFiller = (totalCells % 7 === 0) ? 0 : 7 - (totalCells % 7);
        for (let dayNum = 1; dayNum <= nextFiller; dayNum++) {
            const d = new Date(year, month + 1, dayNum);
            const cell = createDayCell(d, dayNum, true, eventsByDate, todayKey, clashEvaluations);
            gridContainer.appendChild(cell);
        }
    }

    function createDayCell(dateObj, dayNum, isOtherMonth, eventsByDate, todayKey, clashEvaluations) {
        const cell = document.createElement('div');
        const dateKey = toDateKey(dateObj);
        const dayEvents = eventsByDate[dateKey] || [];
        const isToday = (dateKey === todayKey);
        const clashInfo = clashEvaluations[dateKey];

        let baseClasses = `day-cell ${isOtherMonth ? 'other-month' : ''} ${isToday ? 'today' : ''}`;

        // Color cell ONLY if Event Mode is ON
        if (STATE.isEventMode && clashInfo && !isOtherMonth) {
            if (clashInfo.status === 'best') baseClasses += ' plan-green';
            else if (clashInfo.status === 'caution') baseClasses += ' plan-yellow';
            else if (clashInfo.status === 'clash') baseClasses += ' plan-red';
        }

        cell.className = baseClasses;
        cell.dataset.date = dateKey;

        // Top Header: Day Number + Status / Badge
        const header = document.createElement('div');
        header.className = 'flex items-center justify-between w-full';

        const numSpan = document.createElement('span');
        numSpan.className = 'day-number font-black text-xs text-white';
        numSpan.textContent = dayNum;
        header.appendChild(numSpan);

        if (STATE.isEventMode && clashInfo && !isOtherMonth) {
            const statusBadge = document.createElement('span');
            let badgeClass = '';
            let symbol = '';
            if (clashInfo.status === 'best') {
                badgeClass = 'bg-emerald-500/20 text-emerald-300 border border-emerald-500/30';
                symbol = '✓';
            } else if (clashInfo.status === 'caution') {
                badgeClass = 'bg-amber-500/20 text-amber-300 border border-amber-500/30';
                symbol = '!';
            } else {
                badgeClass = 'bg-rose-500/20 text-rose-300 border border-rose-500/30';
                symbol = '✕';
            }
            statusBadge.className = `event-status-pill ${badgeClass}`;
            statusBadge.textContent = symbol;
            header.appendChild(statusBadge);
        } else if (dayEvents.length > 0 && !isOtherMonth) {
            const countBadge = document.createElement('span');
            countBadge.className = 'text-[9px] font-black px-1.5 py-0.5 rounded-full bg-indigo-500/20 text-indigo-300 sm:hidden leading-none';
            countBadge.textContent = dayEvents.length;
            header.appendChild(countBadge);
        }

        cell.appendChild(header);

        // Desktop Event Chips (Single Calendar Mode)
        if (!isOtherMonth) {
            const chipContainer = document.createElement('div');
            chipContainer.className = 'hidden sm:flex flex-col gap-1 mt-1 overflow-hidden w-full';

            dayEvents.slice(0, 2).forEach(evt => {
                const chip = document.createElement('div');
                chip.className = `day-event-chip ${evt.badgeClass} truncate`;
                chip.title = `${evt.name} (${evt.deptShortName})`;
                chip.innerHTML = escapeHtml(evt.name);
                chipContainer.appendChild(chip);
            });

            if (dayEvents.length > 2) {
                const more = document.createElement('div');
                more.className = 'text-[9px] font-bold text-gray-400 pl-0.5';
                more.textContent = `+${dayEvents.length - 2} more`;
                chipContainer.appendChild(more);
            }
            cell.appendChild(chipContainer);

            // Mobile Event Indicator Dots
            if (dayEvents.length > 0) {
                const dotsContainer = document.createElement('div');
                dotsContainer.className = 'day-dots-container sm:hidden';
                dayEvents.slice(0, 3).forEach(evt => {
                    const dot = document.createElement('span');
                    dot.className = 'event-dot';
                    dot.style.backgroundColor = getEventColor(evt.category);
                    dot.style.color = getEventColor(evt.category);
                    dotsContainer.appendChild(dot);
                });
                cell.appendChild(dotsContainer);
            }
        }

        // Tap cell to open Day Detail
        cell.onclick = () => openDayDetail(dateObj, dayEvents, clashInfo);

        return cell;
    }

    // --- Agenda / Schedule List View ---
    function renderAgendaView() {
        const container = document.getElementById('agenda-list-container');
        if (!container) return;

        const events = getActiveEvents();
        if (events.length === 0) {
            container.innerHTML = `
                <div class="text-center py-16 px-4 cal-glass rounded-3xl">
                    <div class="w-14 h-14 rounded-2xl bg-white/5 flex items-center justify-center mx-auto mb-3 text-2xl text-gray-500">
                        <i class="fas fa-calendar-times"></i>
                    </div>
                    <h3 class="text-white font-bold text-base mb-1">No Events Found</h3>
                    <p class="text-gray-400 text-xs max-w-sm mx-auto">No tests, tutorials, or exams scheduled for the chosen calendar or search filter.</p>
                </div>
            `;
            return;
        }

        const grouped = {};
        events.forEach(e => {
            const key = toDateKey(e.date);
            if (!grouped[key]) grouped[key] = { date: e.date, list: [] };
            grouped[key].list.push(e);
        });

        const today = new Date();
        today.setHours(0, 0, 0, 0);

        let html = '';
        Object.keys(grouped).forEach(dateKey => {
            const group = grouped[dateKey];
            const d = group.date;
            const fullDateStr = d.toLocaleDateString('en-US', {
                weekday: 'long', month: 'short', day: 'numeric', year: 'numeric'
            });
            const weekdayShort = d.toLocaleDateString('en-US', { weekday: 'short' });
            const dayNum = d.getDate();
            const diffDays = Math.ceil((d - today) / (1000 * 60 * 60 * 24));

            let timeBadge = '';
            if (diffDays === 0) {
                timeBadge = '<span class="px-2 py-0.5 rounded-full text-[9px] font-black bg-indigo-500 text-white shadow-md shadow-indigo-500/40">TODAY</span>';
            } else if (diffDays === 1) {
                timeBadge = '<span class="px-2 py-0.5 rounded-full text-[9px] font-bold bg-indigo-500/20 text-indigo-300 border border-indigo-500/30">TOMORROW</span>';
            } else if (diffDays > 1) {
                timeBadge = `<span class="text-[10px] font-semibold text-gray-400">in ${diffDays} days</span>`;
            } else {
                timeBadge = '<span class="text-[9px] font-semibold text-gray-500">Completed</span>';
            }

            html += `
                <div class="mb-4">
                    <div class="sticky top-12 z-20 py-2 px-3 bg-[#05040a]/90 backdrop-blur-md flex items-center justify-between border-b border-white/5 mb-2 rounded-xl">
                        <div class="flex items-center gap-2">
                            <i class="fas fa-calendar-day text-indigo-400 text-xs"></i>
                            <h3 class="text-xs sm:text-sm font-extrabold text-white">${fullDateStr}</h3>
                        </div>
                        <div>${timeBadge}</div>
                    </div>
                    <div class="space-y-2 pl-1 sm:pl-2">
            `;

            group.list.forEach(evt => {
                const gCalUrl = generateGoogleCalendarUrl(evt);
                html += `
                    <div class="cal-glass p-3 sm:p-3.5 rounded-2xl flex items-center justify-between gap-2.5 border border-white/5">
                        <div class="flex items-center gap-2.5 sm:gap-3.5 min-w-0">
                            <div class="w-10 h-10 rounded-xl bg-white/5 border border-white/10 flex flex-col items-center justify-center flex-shrink-0 text-center">
                                <span class="text-[8px] font-black text-indigo-300 uppercase leading-none">${weekdayShort}</span>
                                <span class="text-sm font-black text-white leading-tight mt-0.5">${dayNum}</span>
                            </div>
                            <div class="min-w-0">
                                <div class="flex items-center gap-1.5 flex-wrap mb-1">
                                    <span class="badge-dept" style="background:${evt.deptColor}22; color:${evt.deptColor}; border:1px solid ${evt.deptColor}44;">
                                        ${escapeHtml(evt.deptShortName)}
                                    </span>
                                    <span class="badge-dept ${evt.badgeClass}">
                                        <i class="fas ${evt.icon} text-[8px]"></i> ${evt.catLabel}
                                    </span>
                                </div>
                                <h4 class="text-xs sm:text-sm font-bold text-white leading-snug truncate sm:whitespace-normal">
                                    ${escapeHtml(evt.name)}
                                </h4>
                            </div>
                        </div>
                        <a href="${gCalUrl}" target="_blank" rel="noopener" title="Add to Google Calendar"
                           class="p-2 rounded-xl bg-white/5 hover:bg-indigo-600/30 border border-white/10 text-gray-300 hover:text-white transition active:scale-95 text-xs flex-shrink-0">
                            <i class="fab fa-google text-[11px] text-indigo-400"></i>
                        </a>
                    </div>
                `;
            });

            html += `</div></div>`;
        });

        container.innerHTML = html;
    }

    // --- Day Detail Bottom Sheet / Drawer ---
    function openDayDetail(dateObj, dayEvents, clashInfo) {
        STATE.selectedDate = dateObj;
        const drawer = document.getElementById('day-detail-drawer');
        const titleEl = document.getElementById('drawer-date-title');
        const listEl = document.getElementById('drawer-events-list');
        const conflictBanner = document.getElementById('drawer-conflict-banner');
        if (!drawer || !titleEl || !listEl) return;

        const fullDateStr = dateObj.toLocaleDateString('en-US', {
            weekday: 'long', month: 'long', day: 'numeric', year: 'numeric'
        });
        titleEl.textContent = fullDateStr;

        // Event Mode Conflict Summary Banner
        if (STATE.isEventMode && clashInfo) {
            conflictBanner.classList.remove('hidden');
            if (clashInfo.status === 'best') {
                conflictBanner.className = 'mb-3 p-3 rounded-xl border border-emerald-500/30 bg-emerald-950/30 text-emerald-300 text-xs flex items-center gap-2.5';
                conflictBanner.innerHTML = `
                    <div class="w-6 h-6 rounded-full bg-emerald-500/20 flex items-center justify-center flex-shrink-0 text-emerald-400">
                        <i class="fas fa-check text-[10px]"></i>
                    </div>
                    <div>
                        <p class="font-extrabold text-white">Ideal Date &bull; Zero Clashes</p>
                        <p class="text-[11px] opacity-90">${clashInfo.summary}</p>
                    </div>
                `;
            } else if (clashInfo.status === 'caution') {
                conflictBanner.className = 'mb-3 p-3 rounded-xl border border-amber-500/30 bg-amber-950/30 text-amber-300 text-xs flex items-center gap-2.5';
                conflictBanner.innerHTML = `
                    <div class="w-6 h-6 rounded-full bg-amber-500/20 flex items-center justify-center flex-shrink-0 text-amber-400">
                        <i class="fas fa-exclamation text-[10px]"></i>
                    </div>
                    <div>
                        <p class="font-extrabold text-white">Caution &bull; Near Exam Window</p>
                        <p class="text-[11px] opacity-90">${clashInfo.summary}</p>
                    </div>
                `;
            } else {
                conflictBanner.className = 'mb-3 p-3 rounded-xl border border-rose-500/30 bg-rose-950/30 text-rose-300 text-xs flex items-center gap-2.5';
                conflictBanner.innerHTML = `
                    <div class="w-6 h-6 rounded-full bg-rose-500/20 flex items-center justify-center flex-shrink-0 text-rose-400">
                        <i class="fas fa-times text-[10px]"></i>
                    </div>
                    <div>
                        <p class="font-extrabold text-white">Exam Conflict on Date</p>
                        <p class="text-[11px] opacity-90">${clashInfo.summary}</p>
                    </div>
                `;
            }
        } else {
            conflictBanner.classList.add('hidden');
        }

        // List of Events
        if (!dayEvents || dayEvents.length === 0) {
            listEl.innerHTML = `
                <div class="text-center py-6 text-gray-400 text-xs">
                    <i class="fas fa-mug-hot text-2xl mb-2 text-gray-500"></i>
                    <p class="font-bold text-white">No scheduled tests or exams on this day</p>
                    <p class="text-[11px] text-gray-500 mt-1">Regular class schedule or free day for ${getCurrentDeptName()}.</p>
                </div>
            `;
        } else {
            let html = '';
            dayEvents.forEach(evt => {
                const gCalUrl = generateGoogleCalendarUrl(evt);
                html += `
                    <div class="p-3.5 rounded-2xl bg-white/5 border border-white/10">
                        <div class="flex items-center gap-1.5 flex-wrap mb-1">
                            <span class="badge-dept" style="background:${evt.deptColor}22; color:${evt.deptColor}; border:1px solid ${evt.deptColor}44;">
                                ${escapeHtml(evt.deptShortName)}
                            </span>
                            <span class="badge-dept ${evt.badgeClass}">
                                <i class="fas ${evt.icon} text-[8px]"></i> ${evt.catLabel}
                            </span>
                        </div>
                        <h4 class="text-xs sm:text-sm font-bold text-white mb-2 leading-snug">${escapeHtml(evt.name)}</h4>
                        <div class="flex items-center justify-between pt-1 border-t border-white/5">
                            <span class="text-[10px] text-gray-400 font-semibold">${evt.isHoliday ? 'Campus Holiday' : 'PSG College of Technology'}</span>
                            <a href="${gCalUrl}" target="_blank" rel="noopener"
                               class="text-[11px] font-bold text-indigo-400 hover:text-indigo-300 flex items-center gap-1 active:scale-95 transition">
                                <i class="fab fa-google text-[10px]"></i> Add to Calendar
                            </a>
                        </div>
                    </div>
                `;
            });
            listEl.innerHTML = html;
        }

        drawer.style.display = 'flex';
        drawer.classList.remove('hidden');
        requestAnimationFrame(() => {
            drawer.classList.add('open');
        });
    }

    function closeDayDetail() {
        const drawer = document.getElementById('day-detail-drawer');
        if (!drawer) return;
        drawer.classList.remove('open');
        setTimeout(() => {
            if (!drawer.classList.contains('open')) {
                drawer.classList.add('hidden');
                drawer.style.display = 'none';
            }
        }, 250);
    }

    // --- Google Calendar URL Builder ---
    function generateGoogleCalendarUrl(evt) {
        const d = evt.date;
        const year = d.getFullYear();
        const month = String(d.getMonth() + 1).padStart(2, '0');
        const day = String(d.getDate()).padStart(2, '0');
        const dateStr = `${year}${month}${day}`;

        const nextD = new Date(d);
        nextD.setDate(nextD.getDate() + 1);
        const nextYear = nextD.getFullYear();
        const nextMonth = String(nextD.getMonth() + 1).padStart(2, '0');
        const nextDay = String(nextD.getDate()).padStart(2, '0');
        const nextDateStr = `${nextYear}${nextMonth}${nextDay}`;

        const title = encodeURIComponent(`${evt.name} - ${evt.deptShortName} [PSG Tech]`);
        const details = encodeURIComponent(`Academic Schedule: ${evt.name}\nDepartment: ${evt.deptName}\nCategory: ${evt.catLabel}\nSynced from Smart Bunker.`);
        const location = encodeURIComponent('PSG College of Technology, Coimbatore');

        return `https://calendar.google.com/calendar/render?action=TEMPLATE&text=${title}&dates=${dateStr}/${nextDateStr}&details=${details}&location=${location}`;
    }

    // --- Department Switcher (Single Calendar Mode) ---
    function changeDepartment(deptId) {
        STATE.selectedDept = deptId;
        renderCurrentView();
    }

    function getCurrentDeptName() {
        const d = DEPARTMENTS.find(dept => dept.id === STATE.selectedDept);
        return d ? d.shortName : 'Selected Department';
    }

    // --- Event Mode Toggle (Dynamic Color Changing Engine) ---
    function toggleEventMode(forceState) {
        STATE.isEventMode = (typeof forceState === 'boolean') ? forceState : !STATE.isEventMode;

        const btn = document.getElementById('btn-toggle-event-mode');
        const panel = document.getElementById('event-mode-panel');

        if (btn) {
            btn.classList.toggle('btn-event-mode-active', STATE.isEventMode);
            const btnText = btn.querySelector('.event-mode-btn-text');
            if (btnText) {
                btnText.textContent = STATE.isEventMode ? 'Event Mode ON' : 'Event Mode';
            }
        }

        if (panel) {
            panel.classList.toggle('hidden', !STATE.isEventMode);
        }

        renderCurrentView();
    }

    function changeAudience(aud) {
        STATE.plannerAudience = aud;
        if (STATE.isEventMode) {
            renderCurrentView();
        }
    }

    // --- Month Navigation & Month Switching ---
    function changeMonth(delta) {
        const cur = STATE.currentMonth;
        STATE.currentMonth = new Date(cur.getFullYear(), cur.getMonth() + delta, 1);
        renderCurrentView();
    }

    function jumpToMonth(year, month) {
        STATE.currentMonth = new Date(year, month, 1);
        renderCurrentView();
    }

    function jumpToToday() {
        const now = new Date();
        STATE.currentMonth = new Date(now.getFullYear(), now.getMonth(), 1);
        renderCurrentView();
    }

    function openMonthPicker() {
        const picker = document.getElementById('cal-month-picker');
        if (!picker) return;
        const y = STATE.currentMonth.getFullYear();
        const m = String(STATE.currentMonth.getMonth() + 1).padStart(2, '0');
        picker.value = `${y}-${m}`;
        if (typeof picker.showPicker === 'function') {
            try {
                picker.showPicker();
            } catch (err) {
                picker.click();
            }
        } else {
            picker.click();
        }
    }

    function onMonthPickerChange(val) {
        if (!val) return;
        const parts = val.split('-');
        const y = parseInt(parts[0], 10);
        const m = parseInt(parts[1], 10) - 1;
        if (!isNaN(y) && !isNaN(m)) {
            jumpToMonth(y, m);
        }
    }

    // --- Mobile Touch Swipe Gesture Handler ---
    function setupSwipeGestures() {
        const gridCard = document.getElementById('calendar-grid-card');
        if (!gridCard) return;

        let startX = 0;
        let startY = 0;
        let endX = 0;
        let endY = 0;

        gridCard.addEventListener('touchstart', (e) => {
            if (!e.changedTouches || e.changedTouches.length === 0) return;
            startX = e.changedTouches[0].screenX;
            startY = e.changedTouches[0].screenY;
        }, { passive: true });

        gridCard.addEventListener('touchend', (e) => {
            if (!e.changedTouches || e.changedTouches.length === 0) return;
            endX = e.changedTouches[0].screenX;
            endY = e.changedTouches[0].screenY;

            const diffX = endX - startX;
            const diffY = endY - startY;

            // Only trigger if horizontal movement is dominant and > 45px
            if (Math.abs(diffX) > 45 && Math.abs(diffX) > Math.abs(diffY) * 1.5) {
                if (diffX < 0) {
                    // Swipe Left -> Next Month
                    changeMonth(1);
                } else {
                    // Swipe Right -> Previous Month
                    changeMonth(-1);
                }
            }
        }, { passive: true });

        // Drawer Swipe Down to dismiss
        const drawerPanel = document.getElementById('drawer-panel');
        if (drawerPanel) {
            let drawerStartY = 0;
            drawerPanel.addEventListener('touchstart', (e) => {
                drawerStartY = e.changedTouches[0].screenY;
            }, { passive: true });

            drawerPanel.addEventListener('touchend', (e) => {
                const diffY = e.changedTouches[0].screenY - drawerStartY;
                const listEl = document.getElementById('drawer-events-list');
                const isScrolled = listEl ? listEl.scrollTop > 5 : false;
                if (diffY > 60 && !isScrolled) {
                    closeDayDetail();
                }
            }, { passive: true });
        }
    }

    // --- Switch View (Month vs Schedule) ---
    function setView(view) {
        STATE.currentView = view;
        document.querySelectorAll('.view-tab-btn').forEach(b => {
            const isActive = (b.dataset.view === view);
            b.classList.toggle('active', isActive);
            if (isActive) {
                b.classList.add('bg-indigo-600', 'text-white');
                b.classList.remove('bg-transparent', 'text-gray-400');
            } else {
                b.classList.remove('bg-indigo-600', 'text-white');
                b.classList.add('bg-transparent', 'text-gray-400');
            }
        });

        const vMonth = document.getElementById('view-month');
        const vAgenda = document.getElementById('view-agenda');

        if (vMonth) vMonth.classList.toggle('hidden', view !== 'month');
        if (vAgenda) vAgenda.classList.toggle('hidden', view !== 'agenda');

        renderCurrentView();
    }

    function renderCurrentView() {
        if (STATE.currentView === 'month') {
            renderMonthView();
        } else {
            renderAgendaView();
        }
    }

    // --- Initialize UI & App State ---
    function initApp() {
        // Read URL parameters or stored roll
        const urlParams = new URLSearchParams(window.location.search);
        const rollParam = urlParams.get('roll') || localStorage.getItem('bunker_roll') || '';

        if (rollParam) {
            const parsed = parseRoll(rollParam);
            if (parsed) {
                STATE.userRoll = parsed.roll;
                STATE.userDeptId = parsed.deptId;
                STATE.userDeptName = parsed.deptName;
                STATE.selectedDept = parsed.deptId;

                const badge = document.getElementById('user-dept-badge');
                if (badge) {
                    badge.textContent = `${parsed.roll} (${parsed.deptName.split(' ')[0]})`;
                    badge.classList.remove('hidden');
                }
            }
        }

        // Populate Single Calendar Department Select dropdown
        const deptSelect = document.getElementById('cal-dept-select');
        if (deptSelect) {
            deptSelect.innerHTML = '';
            DEPARTMENTS.forEach(dept => {
                const opt = document.createElement('option');
                opt.value = dept.id;
                opt.className = 'bg-gray-900 text-white';
                let label = dept.name;
                if (dept.id === STATE.userDeptId) label += ' ★ (My Dept)';
                opt.textContent = label;
                if (dept.id === STATE.selectedDept) opt.selected = true;
                deptSelect.appendChild(opt);
            });
        }

        // Search Input Listener
        const searchInput = document.getElementById('cal-search-input');
        if (searchInput) {
            let timeout = null;
            searchInput.addEventListener('input', (e) => {
                clearTimeout(timeout);
                timeout = setTimeout(() => {
                    STATE.searchQuery = e.target.value.trim();
                    renderCurrentView();
                }, 180);
            });
        }

        setupSwipeGestures();
        renderCurrentView();
    }

    function escapeHtml(str) {
        if (!str) return '';
        return String(str).replace(/[&<>"']/g, m => ({
            '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
        }[m]));
    }

    // Expose public API
    window.calendarApp = {
        changeDepartment,
        toggleEventMode,
        changeAudience,
        changeMonth,
        jumpToMonth,
        jumpToToday,
        openMonthPicker,
        onMonthPickerChange,
        setView,
        closeDayDetail,
        openDayDetail
    };

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', loadCalendarData);
    } else {
        loadCalendarData();
    }
})();
