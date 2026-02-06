# PSG IAS Timetable & Calendar Enhancement - Walkthrough

## Overview
I have enhanced the application to fully support PSG IAS timetable display with course names and gracefully handle the lack of academic calendar data for PSG IAS, while preserving full functionality for PSG Tech.

## Features Implemented

### 1. Enhanced Timetable Display (PSG IAS)
- **Scraping:** The system now scrapes the weekly schedule directly from the PSG IAS timetable page.
- **Course Mapping:** Course codes (e.g., "19E101") from the timetable are automatically mapped to Subject Names (e.g., "Mathematics I") using data from the attendance page.
- **Frontend:** The timetable view now displays useful Subject Names instead of cryptic codes.

### 2. Calendar Handling (PSG IAS vs PSG Tech)
- **College Detection:** The system automatically detects the college based on roll number length (6 digits = PSG Tech, 7 digits = PSG IAS).
- **Conditional Rendering:**
  - **PSG Tech User:** Sees full academic calendar, holiday countdowns, exam schedules, and semester progress.
  - **PSG IAS User:** Sees "---" placeholders for these widgets to indicate data is unavailable, preventing confusion or errors.

### 3. Error Prevention & Fallbacks
-   **Invalid Calendar API Calls:** Prevented the app from calling the PSG Tech calendar API for PSG IAS students.
-   **Empty States:** Added nice empty states for holidays and exams when no data is available.
-   **Timetable Fallback:** If the timetable is unavailable, the "Planner" tab automatically falls back to showing the list of subjects for manual tracking.

### 4. Manual Tracking Enhancements
-   **Impact Toggle:** Users can toggle whether manual entries affect the main attendance percentage.
-   **Persistence:** Manual tracking data is saved per roll number and persists across sessions.


## Verification Checklist

### For PSG IAS Students (7-digit roll no)
1.  **Login:** Should succeed.
2.  **Dashboard:**
    -   Progress Widget: Shows "---"
    -   Next Exam: Shows "--"
    -   Next Holiday: Shows "--"
3.  **Timetable Tab:** Should show your weekly schedule with **Subject Names**.
4.  **Planner Tab:** Should allow toggling bunks for mapped subjects.
5.  **Timeline Tab:** Should show "Calendar Unavailable".

### For PSG Tech Students (6-digit roll no)
1.  **Login:** Should work as before.
2.  **Dashboard:** Should show all widgets with live data.
3.  **Timetable:** Should show schedule with course names.
4.  **Timeline:** Should show upcoming holidays and exams.

## Technical Details

- **Backend:** Updated `EcampusIASScraper` to scrape the `TimeTableStud` page and handle table structure variations (e.g., `<th>` vs `<td>` tags for slots).
- **API:** Modified `/api/login` to return `college` type and `has_calendar` flag.
- **Frontend:** Updated `static/app.js` to conditionally render widgets based on `state.hasCalendar`.
