// Utility to get classes from localStorage
function getAllClasses() {
    return JSON.parse(localStorage.getItem('classes') || '[]');
}
// Utility to get students from localStorage
function getAllStudents() {
    return JSON.parse(localStorage.getItem('students') || '[]');
}
// Utility to get attendance from localStorage
function getAttendance() {
    return JSON.parse(localStorage.getItem('studentAttendance') || '{}');
}
function saveAttendance(att) {
    localStorage.setItem('studentAttendance', JSON.stringify(att));
}

function renderClassOverview() {
    const tbody = document.getElementById('class-overview-tbody');
    tbody.innerHTML = '';
    const classes = getAllClasses();
    const students = getAllStudents();
    const attendance = getAttendance();
    classes.forEach(cls => {
        const enrolled = students.filter(s => Array.isArray(s.enrolledClasses) && s.enrolledClasses.includes(cls.id));
        const presentCount = enrolled.filter(s => (attendance[cls.id] && attendance[cls.id][s.id] && attendance[cls.id][s.id].status === 'Present') || !attendance[cls.id] || !attendance[cls.id][s.id]).length;
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${cls.classCode || cls.id}</td>
            <td><a href="#" class="course-link" data-class-id="${cls.id}">${cls.description}</a></td>
            <td>${enrolled.length}</td>
            <td>${cls.schedule}</td>
            <td>March 30 2025</td>
            <td>${presentCount} out of ${enrolled.length}</td>
        `;
        tbody.appendChild(row);
    });
    // Add click event only to course links
    tbody.querySelectorAll('.course-link').forEach(link => {
        link.addEventListener('click', function(e) {
            e.preventDefault();
            showClassDetail(this.dataset.classId);
        });
    });
}

function showClassDetail(classId) {
    const classes = getAllClasses();
    const students = getAllStudents();
    const attendance = getAttendance();
    const cls = classes.find(c => c.id == classId);
    if (!cls) return;
    
    // Hide overview and show class detail
    document.getElementById('classOverview').style.display = 'none';
    document.getElementById('classDetailView').style.display = 'block';
    document.getElementById('studentDetailView').style.display = 'none';
    
    document.getElementById('classDetailTitle').textContent = `Class: ${cls.description}`;
    document.getElementById('classDetailCode').textContent = `Class Code: ${cls.classCode || cls.id}`;
    
    const tbody = document.getElementById('class-detail-tbody');
    tbody.innerHTML = '';
    
    const enrolled = students.filter(s => Array.isArray(s.enrolledClasses) && s.enrolledClasses.includes(cls.id));
    enrolled.forEach(student => {
        const status = (attendance[cls.id] && attendance[cls.id][student.id] && attendance[cls.id][student.id].status) || 'Present';
        const row = document.createElement('tr');
        row.innerHTML = `
            <td><a href="#" class="student-link" data-student-id="${student.id}">${student.firstName} ${student.lastName}</a></td>
            <td class="${status === 'Present' ? 'present-status' : 'absent-status'}">${status}</td>
            <td>
                <button class="btn btn-sm ${status === 'Present' ? 'btn-danger' : 'btn-success'} toggle-status-btn">${status === 'Present' ? 'Mark Absent' : 'Mark Present'}</button>
            </td>
        `;
        
        // Add click event to the student link
        const studentLink = row.querySelector('.student-link');
        studentLink.addEventListener('click', (e) => {
            e.preventDefault();
            showStudentDetail(student.id, cls.id);
        });
        
        // Add click event to the toggle button
        const toggleBtn = row.querySelector('.toggle-status-btn');
        toggleBtn.addEventListener('click', (e) => {
            e.stopPropagation();
            const att = getAttendance();
            if (!att[cls.id]) att[cls.id] = {};
            att[cls.id][student.id] = { status: status === 'Present' ? 'Absent' : 'Present' };
            saveAttendance(att);
            showClassDetail(classId);
        });
        
        tbody.appendChild(row);
    });
}

function showStudentDetail(studentId, classId) {
    const students = getAllStudents();
    const classes = getAllClasses();
    const attendance = getAttendance();
    
    const student = students.find(s => s.id === studentId);
    const cls = classes.find(c => c.id === classId);
    
    if (!student || !cls) return;
    
    // Hide class detail view and show student detail view
    document.getElementById('classDetailView').style.display = 'none';
    document.getElementById('studentDetailView').style.display = 'block';
    
    // Update student detail view header
    document.getElementById('studentDetailTitle').textContent = `Student: ${student.firstName} ${student.lastName}`;
    document.getElementById('studentDetailClass').textContent = `Class: ${cls.description} (${cls.classCode || cls.id})`;
    
    // Generate dates for January, February, and March
    const dates = {
        january: generateMonthDates(2025, 0), // January
        february: generateMonthDates(2025, 1), // February
        march: generateMonthDates(2025, 2) // March
    };
    
    // Populate the attendance table
    const tbody = document.getElementById('studentDatesBody');
    tbody.innerHTML = '';
    
    // Combine all dates and sort them
    const allDates = [...dates.january, ...dates.february, ...dates.march];
    allDates.sort((a, b) => new Date(a) - new Date(b));
    
    let presentCount = 0;
    let absentCount = 0;
    
    allDates.forEach(date => {
        // Initialize attendance data structure if it doesn't exist
        if (!attendance[classId]) attendance[classId] = {};
        if (!attendance[classId][studentId]) attendance[classId][studentId] = {};
        
        // Get the current status, defaulting to 'Present' if not set
        const currentStatus = attendance[classId][studentId][date] || 'Present';
        
        // Update counters
        if (currentStatus === 'Present') presentCount++;
        else absentCount++;
        
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${date}</td>
            <td class="${currentStatus === 'Present' ? 'present-status' : 'absent-status'}">${currentStatus}</td>
            <td>
                <button class="toggle-status-btn ${currentStatus === 'Present' ? 'absent-btn' : 'present-btn'}"
                        data-date="${date}">
                    ${currentStatus === 'Present' ? 'Mark Absent' : 'Mark Present'}
                </button>
            </td>
        `;
        
        // Add click event to the toggle button
        const toggleBtn = row.querySelector('.toggle-status-btn');
        toggleBtn.addEventListener('click', () => {
            // Get the current status from the data structure
            const currentStatus = attendance[classId][studentId][date] || 'Present';
            const newStatus = currentStatus === 'Present' ? 'Absent' : 'Present';
            
            // Update attendance data
            attendance[classId][studentId][date] = newStatus;
            saveAttendance(attendance);
            
            // Update the row
            const statusCell = row.querySelector('td:nth-child(2)');
            statusCell.className = newStatus === 'Present' ? 'present-status' : 'absent-status';
            statusCell.textContent = newStatus;
            
            // Update the button
            toggleBtn.className = `toggle-status-btn ${newStatus === 'Present' ? 'absent-btn' : 'present-btn'}`;
            toggleBtn.textContent = newStatus === 'Present' ? 'Mark Absent' : 'Mark Present';
            
            // Update counters
            if (newStatus === 'Present') {
                presentCount++;
                absentCount--;
            } else {
                presentCount--;
                absentCount++;
            }
            
            // Update summary
            document.getElementById('presentCount').textContent = presentCount;
            document.getElementById('absentCount').textContent = absentCount;
        });
        
        tbody.appendChild(row);
    });
    
    // Update summary
    document.getElementById('presentCount').textContent = presentCount;
    document.getElementById('absentCount').textContent = absentCount;
}

function generateMonthDates(year, month) {
    const dates = [];
    const daysInMonth = new Date(year, month + 1, 0).getDate();
    
    for (let day = 1; day <= daysInMonth; day++) {
        const date = new Date(year, month, day);
        // Only include MWF days (Monday, Wednesday, Friday)
        if (date.getDay() === 1 || date.getDay() === 3 || date.getDay() === 5) {
            const monthNames = ['January', 'February', 'March', 'April', 'May', 'June',
                              'July', 'August', 'September', 'October', 'November', 'December'];
            dates.push(`${monthNames[month]} ${day} ${year}`);
        }
    }
    
    return dates;
}

document.addEventListener('DOMContentLoaded', function() {
    renderClassOverview();
    document.getElementById('backToOverview').addEventListener('click', function() {
        document.getElementById('classOverview').style.display = 'block';
        document.getElementById('classDetailView').style.display = 'none';
        renderClassOverview();
    });
    
    // Add back button functionality for student detail view
    document.getElementById('backToAttendance').addEventListener('click', function() {
        document.getElementById('studentDetailView').style.display = 'none';
        document.getElementById('classDetailView').style.display = 'block';
    });
});