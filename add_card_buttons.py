import re

path = 'static/app.js'
with open(path, 'r') as f:
    content = f.read()

# 1. Update card rendering in initPlanner to include buttons
# We need to change the div structure slightly to accommodate the buttons
new_card_html = """            c.innerHTML += `
                <div onclick="toggleCardSelection('${id}', '${code}')" 
                    class="glass-panel p-5 rounded-[28px] border-2 transition-all duration-300 relative overflow-hidden group active:scale-[0.97] cursor-pointer
                    ${isSelected ? 'border-emerald-500 bg-emerald-500/10 shadow-lg shadow-emerald-500/10' : 'border-white/5 hover:border-white/20'} 
                    ${isDone ? 'opacity-90' : ''}">
                    
                    ${isSelected ? '<div class="absolute -right-4 -top-4 w-12 h-12 bg-emerald-500 rotate-45 flex items-end justify-center pb-1 shadow-lg"><i class="fas fa-check text-[10px] text-white -rotate-45"></i></div>' : ''}
                    
                    <div class="flex items-center justify-between">
                        <div class="flex-1 min-w-0 pr-4">
                            <div class="flex items-center gap-2 mb-2">
                                <span class="px-2 py-0.5 rounded-lg bg-indigo-500/10 text-indigo-400 text-[8px] font-black uppercase tracking-widest">Period ${i + 1}</span>
                                ${isDone ? `<span class="text-[10px] animate-pulse"><i class="fas ${statusIcon}"></i></span>` : ''}
                            </div>
                            <p class="text-[14px] font-bold text-white truncate group-hover:text-indigo-200 transition-colors">${s.name}</p>
                            <p class="text-[9px] text-gray-500 font-bold uppercase tracking-wider mt-1">${code}</p>
                        </div>
                        <div class="flex gap-2 relative z-10">
                            <button onclick="event.stopPropagation(); markTimetableAttendance('${code}', 'Present')" 
                                class="w-10 h-10 rounded-2xl bg-emerald-500/10 border border-emerald-500/20 text-emerald-400 flex items-center justify-center hover:bg-emerald-500/20 active:scale-90 transition">
                                <i class="fas fa-check text-xs"></i>
                            </button>
                            <button onclick="event.stopPropagation(); markTimetableAttendance('${code}', 'Absent')" 
                                class="w-10 h-10 rounded-2xl bg-rose-500/10 border border-rose-500/20 text-rose-400 flex items-center justify-center hover:bg-rose-500/20 active:scale-90 transition">
                                <i class="fas fa-times text-xs"></i>
                            </button>
                        </div>
                    </div>
                </div>
            `;"""

# Replace the old card rendering
pattern_card = re.compile(r'c\.innerHTML \+= `\s+<div onclick="toggleCardSelection.*?<\/div>\s+<\/div>\s+<\/div>\s+`;', re.DOTALL)
new_content = pattern_card.sub(new_card_html, content)

# 2. Add markTimetableAttendance function before applySelectedAttendance
mark_func = """function markTimetableAttendance(code, status) {
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
    
    // Deselect all cards for this subject to avoid confusion
    if (state.selectedCards) {
        Object.keys(state.selectedCards).forEach(id => {
            if (state.selectedCards[id] === code) delete state.selectedCards[id];
        });
    }

    saveState();
    renderSemesterHero(); renderWidgets(); renderSubjects(); initPlanner(); initManual();
    showToast(`✅ Marked ${status === 'Present' ? 'Attended' : 'Bunked'}: ${code}`, 'success');
}

function applySelectedAttendance()"""

if 'function markTimetableAttendance' not in new_content:
    new_content = new_content.replace('function applySelectedAttendance()', mark_func)

if new_content != content:
    with open(path, 'w') as f:
        f.write(new_content)
    print("SUCCESS")
else:
    print("FAILURE")
