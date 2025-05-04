// Data model
const instructors = {
    "Lebron James": {
        classes: ["F77"],
        attendance: {
            "F77": "38 out of 38"
        }
    },
    "Stephen Curry": {
        classes: ["F78"],
        attendance: {
            "F78": "38 out of 38"
        }
    },
    "Kobe Bryant": {
        classes: ["F79", "F80", "F81"],
        attendance: {
            "F79": "38 out of 38",
            "F80": "38 out of 38",
            "F81": "37 out of 38"
        }
    }
};

const classes = {
    "F77": {
        code: "F77",
        description: "Application Development",
        instructor: "Lebron James",
        schedule: "7-8 AM MW, 8-9AM MWF",
        attendance: generateAttendanceData("Present")
    },
    "F78": {
        code: "F78",
        description: "Capstone Project 1",
        instructor: "Stephen Curry",
        schedule: "1-2PM MWF",
        attendance: generateAttendanceData("Present")
    },
    "F79": {
        code: "F79",
        description: "Information Assurance and Security 2",
        instructor: "Kobe Bryant",
        schedule: "11AM-12PM MW,12-1PM MWF",
        attendance: generateAttendanceData("Present")
    },
    "F80": {
        code: "F80",
        description: "Social and Professional Issues",
        instructor: "Kobe Bryant",
        schedule: "10:30AM-12PM TTh",
        attendance: generateAttendanceData("Present")
    },
    "F81": {
        code: "F81",
        description: "Systems Administration",
        instructor: "Kobe Bryant",
        schedule: "2-3PM MW,3-4MWF",
        attendance: generateAttendanceData("Present", {
            "March 30 2025": "Absent"
        })
    }
};

// Generate sample attendance data
function generateAttendanceData(defaultStatus, overrides = {}) {
    const januaryDates = [1, 3, 6, 8, 10, 13, 15, 18, 20, 23, 25, 28, 31];
    const februaryDates = [3, 5, 7, 10, 12, 14, 17, 19, 21, 24, 26, 28];
    const marchDates = [2, 4, 7, 9, 11, 14, 16, 18, 21, 23, 25, 28, 30];
    
    const data = {
        january: {},
        february: {},
        march: {}
    };
    
    januaryDates.forEach(date => {
        const dateString = `January ${date} 2025`;
        data.january[dateString] = overrides[dateString] || defaultStatus;
    });
    
    februaryDates.forEach(date => {
        const dateString = `February ${date} 2025`;
        data.february[dateString] = overrides[dateString] || defaultStatus;
    });
    
    marchDates.forEach(date => {
        const dateString = `March ${date} 2025`;
        data.march[dateString] = overrides[dateString] || defaultStatus;
    });
    
    return data;
}

// DOM elements
const instructorAttendanceView = document.getElementById('instructor-attendance-view');
const classDetailView = document.getElementById('class-detail-view');
const instructorDetailView = document.getElementById('instructor-detail-view');

// Back buttons
const backFromClassBtn = document.getElementById('back-from-class');
const backFromInstructorBtn = document.getElementById('back-from-instructor');

// Class detail elements
const classCodeElement = document.getElementById('class-code');
const classDescriptionElement = document.getElementById('class-description');
const classInstructorElement = document.getElementById('class-instructor');
const januaryAttendanceTable = document.getElementById('january-attendance');
const februaryAttendanceTable = document.getElementById('february-attendance');
const marchAttendanceTable = document.getElementById('march-attendance');

// Instructor detail elements
const instructorNameElement = document.getElementById('instructor-name');
const instructorClassesTable = document.getElementById('instructor-classes');

// Initialize everything when DOM is loaded
document.addEventListener('DOMContentLoaded', function() {
    // Initialize attendance table
    initializeAttendanceTable();

    // Add logout functionality
    const logoutBtn = document.getElementById('logout-btn');
    if (logoutBtn) {
        // Remove any existing event listeners
        const newLogoutBtn = logoutBtn.cloneNode(true);
        logoutBtn.parentNode.replaceChild(newLogoutBtn, logoutBtn);
        
        // Add single event listener
        newLogoutBtn.addEventListener('click', function(e) {
            e.preventDefault();
            if (confirm('Are you sure you want to logout?')) {
                window.location.href = '/Login Page.html';
            }
        });
    }

    // Add click event listeners for course links
    attachLinkListeners();

    // Back button event listeners
    backFromClassBtn.addEventListener('click', function() {
        classDetailView.style.display = 'none';
        instructorAttendanceView.style.display = 'block';
    });

    backFromInstructorBtn.addEventListener('click', function() {
        instructorDetailView.style.display = 'none';
        instructorAttendanceView.style.display = 'block';
    });
});

// Function to toggle attendance status
function toggleAttendance(classCode, date) {
    const month = date.split(' ')[0].toLowerCase();
    const currentStatus = classes[classCode].attendance[month][date];
    const newStatus = currentStatus === 'Present' ? 'Absent' : 'Present';
    
    // Update the status in the data model
    classes[classCode].attendance[month][date] = newStatus;
    
    // Update instructor attendance counts
    const instructor = classes[classCode].instructor;
    const totalDays = 38;
    
    // Count present days
    let presentDays = 0;
    ['january', 'february', 'march'].forEach(m => {
        Object.values(classes[classCode].attendance[m]).forEach(status => {
            if (status === 'Present') presentDays++;
        });
    });
    
    // Update instructor's attendance record
    instructors[instructor].attendance[classCode] = `${presentDays} out of ${totalDays}`;
    
    // Update the UI in the main table view
    const row = document.querySelector(`tr[data-class="${classCode}"]`);
    if (row) {
        // Update status cell
        const statusCell = row.querySelector('td:nth-child(6)');
        statusCell.textContent = newStatus;
        statusCell.className = newStatus === 'Present' ? 'status-present' : 'status-absent';
        
        // Update action button
        const actionCell = row.querySelector('td:nth-child(7)');
        const buttonClass = newStatus === 'Present' ? 'absent-btn' : 'present-btn';
        const buttonText = newStatus === 'Present' ? 'Mark Absent' : 'Mark Present';
        
        actionCell.innerHTML = `
            <button type="button" class="toggle-status-btn ${buttonClass}" 
                    onclick="toggleAttendance('${classCode}', '${date}')">
                ${buttonText}
            </button>
        `;
    }
    
    // If we're in class detail view, refresh that view too
    if (classDetailView.style.display === 'block') {
        showClassDetail(classCode);
    }

    // Re-attach event listeners after table update
    attachLinkListeners();
}

// Function to update a specific row in the main attendance table
function updateAttendanceRow(classCode) {
    const table = document.querySelector('#instructor-attendance-view table tbody');
    const rows = table.querySelectorAll('tr');
    
    rows.forEach(row => {
        if (row.querySelector('td:first-child').textContent === classCode) {
            const statusCell = row.querySelector('td:nth-child(6)');
            const date = row.querySelector('td:nth-child(5)').textContent;
            const month = date.split(' ')[0].toLowerCase();
            
            statusCell.textContent = classes[classCode].attendance[month][date];
            
            // Update or add the action button
            let actionCell = row.querySelector('td:nth-child(7)');
            if (!actionCell) {
                actionCell = document.createElement('td');
                row.appendChild(actionCell);
            }
            
            const currentStatus = classes[classCode].attendance[month][date];
            actionCell.innerHTML = `
                <button class="toggle-status-btn ${currentStatus === 'Present' ? 'absent-btn' : 'present-btn'}"
                        data-class="${classCode}" data-date="${date}">
                    ${currentStatus === 'Present' ? 'Mark Absent' : 'Mark Present'}
                </button>
            `;
            
            // Add event listener to the new button
            const button = actionCell.querySelector('button');
            button.addEventListener('click', function() {
                toggleAttendance(this.getAttribute('data-class'), this.getAttribute('data-date'));
            });
        }
    });

    // Re-attach event listeners after table update
    attachLinkListeners();
}

// Initialize the attendance table with action buttons
function initializeAttendanceTable() {
    const table = document.querySelector('#instructor-attendance-view table');
    
    // Add event listeners to all toggle buttons
    document.querySelectorAll('.toggle-status-btn').forEach(button => {
        button.addEventListener('click', function() {
            const classCode = this.getAttribute('data-class');
            const date = this.getAttribute('data-date');
            toggleAttendance(classCode, date);
        });
    });
}

// Function to show class detail with toggle buttons
function showClassDetail(classCode) {
    const classData = classes[classCode];
    
    // Update class info
    classCodeElement.textContent = classData.code;
    classDescriptionElement.textContent = classData.description;
    classInstructorElement.textContent = classData.instructor;
    
    // Clear previous attendance data
    januaryAttendanceTable.innerHTML = '';
    februaryAttendanceTable.innerHTML = '';
    marchAttendanceTable.innerHTML = '';
    
    // Add column headers for actions if not exists
    const janTable = januaryAttendanceTable.closest('table');
    const febTable = februaryAttendanceTable.closest('table');
    const marTable = marchAttendanceTable.closest('table');
    
    // Add "Actions" header to January table
    const janHeader = janTable.querySelector('thead tr');
    if (janHeader.querySelectorAll('th').length < 3) {
        const actionHeader = document.createElement('th');
        actionHeader.textContent = 'Actions';
        janHeader.appendChild(actionHeader);
    }
    
    // Add "Actions" header to February table
    const febHeader = febTable.querySelector('thead tr');
    if (febHeader.querySelectorAll('th').length < 3) {
        const actionHeader = document.createElement('th');
        actionHeader.textContent = 'Actions';
        febHeader.appendChild(actionHeader);
    }
    
    // Add "Actions" header to March table
    const marHeader = marTable.querySelector('thead tr');
    if (marHeader.querySelectorAll('th').length < 3) {
        const actionHeader = document.createElement('th');
        actionHeader.textContent = 'Actions';
        marHeader.appendChild(actionHeader);
    }
    
    // Populate January attendance
    Object.entries(classData.attendance.january).forEach(([date, status]) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${date}</td>
            <td style="color: ${status === 'Present' ? 'green' : 'red'}">${status}</td>
            <td>
                <button class="toggle-status-btn ${status === 'Present' ? 'absent-btn' : 'present-btn'}"
                        data-class="${classCode}" data-date="${date}">
                    ${status === 'Present' ? 'Mark Absent' : 'Mark Present'}
                </button>
            </td>
        `;
        januaryAttendanceTable.appendChild(row);
    });
    
    // Populate February attendance
    Object.entries(classData.attendance.february).forEach(([date, status]) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${date}</td>
            <td style="color: ${status === 'Present' ? 'green' : 'red'}">${status}</td>
            <td>
                <button class="toggle-status-btn ${status === 'Present' ? 'absent-btn' : 'present-btn'}"
                        data-class="${classCode}" data-date="${date}">
                    ${status === 'Present' ? 'Mark Absent' : 'Mark Present'}
                </button>
            </td>
        `;
        februaryAttendanceTable.appendChild(row);
    });
    
    // Populate March attendance
    Object.entries(classData.attendance.march).forEach(([date, status]) => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${date}</td>
            <td style="color: ${status === 'Present' ? 'green' : 'red'}">${status}</td>
            <td>
                <button class="toggle-status-btn ${status === 'Present' ? 'absent-btn' : 'present-btn'}"
                        data-class="${classCode}" data-date="${date}">
                    ${status === 'Present' ? 'Mark Absent' : 'Mark Present'}
                </button>
            </td>
        `;
        marchAttendanceTable.appendChild(row);
    });
    
    // Add event listeners to all toggle buttons
    classDetailView.querySelectorAll('.toggle-status-btn').forEach(button => {
        button.addEventListener('click', function() {
            toggleAttendance(this.getAttribute('data-class'), this.getAttribute('data-date'));
        });
    });
    
    // Show class detail view, hide others
    instructorAttendanceView.style.display = 'none';
    instructorDetailView.style.display = 'none';
    classDetailView.style.display = 'block';

    // Re-attach event listeners after table update
    attachLinkListeners();
}

// Function to show instructor detail
function showInstructorDetail(instructorName) {
    const instructorData = instructors[instructorName];
    
    // Update instructor name
    instructorNameElement.textContent = instructorName;
    
    // Clear previous class data
    instructorClassesTable.innerHTML = '';
    
    // Populate instructor classes
    instructorData.classes.forEach(classCode => {
        const classData = classes[classCode];
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${classCode}</td>
            <td>${classData.schedule}</td>
            <td>${instructorData.attendance[classCode]}</td>
        `;
        instructorClassesTable.appendChild(row);
    });
    
    // Show instructor detail view, hide others
    instructorAttendanceView.style.display = 'none';
    classDetailView.style.display = 'none';
    instructorDetailView.style.display = 'block';

    // Re-attach event listeners after table update
    attachLinkListeners();
}

// Side menu event listeners
document.getElementById('manage-instructor-attendance').addEventListener('click', function(e) {
    e.preventDefault();
    classDetailView.style.display = 'none';
    instructorDetailView.style.display = 'none';
    instructorAttendanceView.style.display = 'block';
});

// Other menu items (placeholders)
const menuItems = [
    'manage-instructors',
    'manage-students',
    'manage-courses',
    'manage-class',
    'logout'
];

menuItems.forEach(id => {
    document.getElementById(id).addEventListener('click', function(e) {
        e.preventDefault();
        alert(`Feature: ${id.replace('-', ' ')} (not implemented in this demo)`);
    });
});

function attachLinkListeners() {
    document.querySelectorAll('.course-link').forEach(link => {
        link.onclick = function(e) {
            e.preventDefault();
            const classCode = this.closest('tr').getAttribute('data-class');
            showClassDetail(classCode);
        };
    });
    document.querySelectorAll('.instructor-link').forEach(link => {
        link.onclick = function(e) {
            e.preventDefault();
            const instructorName = this.closest('tr').getAttribute('data-instructor');
            showInstructorDetail(instructorName);
        };
    });
}

// Call this after any table update or DOM change
attachLinkListeners();