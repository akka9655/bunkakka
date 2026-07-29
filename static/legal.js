const LEGAL_TEXT = `
<div class="space-y-6 text-gray-300">
    <!-- Disclaimer Block -->
    <div class="bg-amber-500/10 border border-amber-500/20 p-4 rounded-2xl">
        <h4 class="text-amber-400 font-bold mb-2 flex items-center gap-2">
            <i class="fas fa-exclamation-triangle"></i> Important Disclaimer
        </h4>
        <p class="text-xs leading-relaxed text-gray-400">
            Bunker is an independent <strong>student-developed project</strong>. It is <strong>NOT</strong> an official application of PSG College of Technology or PSG institutions. Use entirely at your own risk.
        </p>
    </div>

    <!-- Privacy Section -->
    <div>
        <h3 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <i class="fas fa-shield-alt text-indigo-400"></i> Privacy Policy
        </h3>
        
        <div class="space-y-4">
            <div class="bg-white/5 p-4 rounded-xl border border-white/5">
                <h5 class="font-bold text-white text-sm mb-2">1. Information We Use 📊</h5>
                <ul class="text-xs list-disc pl-4 space-y-1 text-gray-400">
                    <li>Roll number / username (to fetch data)</li>
                    <li>Attendance & timetable data (temporarily)</li>
                    <li>Locally stored preferences (theme, cache)</li>
                </ul>
            </div>

            <div class="bg-white/5 p-4 rounded-xl border border-white/5">
                <h5 class="font-bold text-white text-sm mb-2">2. Passwords & Security 🔐</h5>
                <p class="text-xs text-gray-400 leading-relaxed">
                    Your password is <strong>NEVER</strong> stored on our servers, cookies, or logs. It is used <strong>once</strong> to authenticate and then immediately discarded.
                </p>
            </div>

            <div class="bg-white/5 p-4 rounded-xl border border-white/5">
                <h5 class="font-bold text-white text-sm mb-2">3. Local Storage 🍪</h5>
                <p class="text-xs text-gray-400 leading-relaxed">
                    We store data like your session and cache <strong>only on your device</strong> to make the app faster. You can clear this anytime in Settings.
                </p>
            </div>
        </div>
    </div>

    <!-- Terms Section -->
    <div>
        <h3 class="text-xl font-bold text-white mb-4 flex items-center gap-2">
            <i class="fas fa-gavel text-rose-400"></i> Terms & Conditions
        </h3>
        
        <div class="space-y-4">
            <div class="p-3">
                <h5 class="font-bold text-gray-200 text-sm mb-1">❌ Not Official</h5>
                <p class="text-xs text-gray-500">Do not treat this as a replacement for official PSG portals.</p>
            </div>
            
            <div class="p-3">
                <h5 class="font-bold text-gray-200 text-sm mb-1">📉 No Accuracy Guarantee</h5>
                <p class="text-xs text-gray-500">We are not responsible for calculation errors, attendance shortages, or academic decisions made based on this app. Verify with official sources.</p>
            </div>
        </div>
    </div>

    <!-- Control Section -->
    <div class="border-t border-white/10 pt-6">
        <h3 class="text-lg font-bold text-white mb-2 flex items-center gap-2">
            <i class="fas fa-user-cog text-emerald-400"></i> Your Control
        </h3>
        <p class="text-xs text-gray-400 mb-4">
            You can at any time <strong>Log out</strong>, <strong>Clear Data</strong>, or stop using the service.
        </p>
        <p class="text-xs text-gray-500 text-center">
            Questions? Contact: <a href="mailto:Bunk@gmail.com" class="text-blue-400 hover:underline">Bunk@gmail.com</a>
        </p>
    </div>
</div>
`;
