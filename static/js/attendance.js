/**
 * Attendance Management System
 * Handles student attendance tracking
 */
document.addEventListener('DOMContentLoaded', () => {
    // DOM element references
    const elements = {
        // Views
        classOverview: document.getElementById('classOverview'),
        classDetailView: document.getElementById('classDetailView'),
        studentDetailView: document.getElementById('studentDetailView'),
        // Tables
        classOverviewTbody: document.getElementById('class-overview-tbody'),
        classDetailTbody: document.getElementById('class-detail-tbody'),
        studentDatesBody: document.getElementById('studentDatesBody'),
        // Navigation buttons
        backToOverview: document.getElementById('backToOverview'),
        backToAttendance: document.getElementById('backToAttendance'),
        // Student detail elements
        studentDetailTitle: document.getElementById('studentDetailTitle'),
        studentDetailClass: document.getElementById('studentDetailClass'),
        presentCount: document.getElementById('presentCount'),
        absentCount: document.getElementById('absentCount'),
        // Class detail elements
        classDetailTitle: document.getElementById('classDetailTitle'),
        classDetailCode: document.getElementById('classDetailCode')
    };

    // Application state
    const state = {
        currentClassId: null,
        currentStudentId: null,
        currentDate: new Date().toISOString().split('T')[0] // Today's date in YYYY-MM-DD format
    };

    // Initialize the application
    init();

    // Add event listeners
    function addEventListeners() {
        // Navigation
        if (elements.backToOverview) {
            elements.backToOverview.addEventListener('click', () => {
                showClassOverview();
            });
        }

        if (elements.backToAttendance) {
            elements.backToAttendance.addEventListener('click', () => {
                // Go back to class detail view
                if (state.currentClassId) {
                    showClassDetail(state.currentClassId);
                } else {
                    showClassOverview();
                }
            });
        }

        // Table delegation for class links
        if (elements.classOverviewTbody) {
            elements.classOverviewTbody.addEventListener('click', (e) => {
                const courseLink = e.target.closest('.course-link');
                if (courseLink) {
                    e.preventDefault();
                    const classId = parseInt(courseLink.dataset.classId);
                    showClassDetail(classId);
                }
            });
        }
    }

    // Initialize the application
    async function init() {
        try {
            await fetchClassesWithAttendance();
            addEventListeners();
            showClassOverview();
        } catch (error) {
            console.error('Initialization error:', error);
            showAlert('Failed to load attendance data. Please try again.', 'danger');
        }
    }

    // Fetch classes with attendance data
    async function fetchClassesWithAttendance() {
        try {
            const response = await fetch('/attendance/api/classes');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            renderClassOverview(await response.json());
        } catch (error) {
            console.error('Error fetching classes with attendance:', error);
            showAlert('Failed to load class attendance data', 'danger');
        }
    }

    // Show Class Overview
    function showClassOverview() {
        // Hide other views
        elements.classDetailView.style.display = 'none';
        elements.studentDetailView.style.display = 'none';
        
        // Show class overview
        elements.classOverview.style.display = 'block';
        
        // Reset state
        state.currentClassId = null;
        state.currentStudentId = null;
        
        // Refresh data
        fetchClassesWithAttendance();
    }

    // Render Class Overview
    function renderClassOverview(classes) {
        if (!elements.classOverviewTbody) return;
        
        elements.classOverviewTbody.innerHTML = '';
        
        if (!classes || classes.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = '<td colspan="6" class="text-center">No classes found</td>';
            elements.classOverviewTbody.appendChild(row);
            return;
        }
        
        classes.forEach(cls => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${cls.classCode}</td>
                <td><a href="#" class="course-link" data-class-id="${cls.id}">${cls.description}</a></td>
                <td>${cls.enrolledCount}</td>
                <td>${cls.schedule}</td>
                <td>${cls.date}</td>
                <td>${cls.presentCount} out of ${cls.enrolledCount}</td>
            `;
            elements.classOverviewTbody.appendChild(row);
        });
    }

    // Show Class Detail
    async function showClassDetail(classId) {
        state.currentClassId = classId;
        
        try {
            // Fetch class detail
            const classResponse = await fetch(`/classes/api/list`);
            const classes = await classResponse.json();
            const classData = classes.find(c => c.id === classId);
            
            if (!classData) {
                throw new Error('Class not found');
            }
            
            // Update class detail title
            elements.classDetailTitle.textContent = `Class: ${classData.description}`;
            elements.classDetailCode.textContent = `Class Code: ${classData.classCode}`;
            
            // Fetch attendance for this class
            const attendanceResponse = await fetch(`/attendance/api/class/${classId}/attendance?date=${state.currentDate}`);
            const attendanceData = await attendanceResponse.json();
            
            // Render student attendance
            renderClassAttendance(attendanceData);
            
            // Show class detail view
            elements.classOverview.style.display = 'none';
            elements.classDetailView.style.display = 'block';
            elements.studentDetailView.style.display = 'none';
            
        } catch (error) {
            console.error('Error showing class detail:', error);
            showAlert('Failed to load class attendance detail', 'danger');
            showClassOverview();
        }
    }

    // Render Class Attendance
    function renderClassAttendance(data) {
        if (!elements.classDetailTbody) return;
        
        elements.classDetailTbody.innerHTML = '';
        
        if (!data.attendance || data.attendance.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = '<td colspan="3" class="text-center">No students enrolled</td>';
            elements.classDetailTbody.appendChild(row);
            return;
        }
        
        data.attendance.forEach(record => {
            const row = document.createElement('tr');
            const statusClass = record.status === 'Present' ? 'present-status' : 'absent-status';
            const buttonClass = record.status === 'Present' ? 'btn-danger' : 'btn-success';
            const buttonText = record.status === 'Present' ? 'Mark Absent' : 'Mark Present';
            
            row.innerHTML = `
                <td><a href="#" class="student-link" data-student-id="${record.studentId}">${record.studentName}</a></td>
                <td class="${statusClass}">${record.status}</td>
                <td>
                    <button class="btn btn-sm ${buttonClass} toggle-status-btn" 
                            data-student-id="${record.studentId}" 
                            data-current-status="${record.status}">
                        ${buttonText}
                    </button>
                </td>
            `;
            
            // Add event listener for student link
            const studentLink = row.querySelector('.student-link');
            studentLink.addEventListener('click', (e) => {
                e.preventDefault();
                showStudentDetail(record.studentId);
            });
            
            // Add event listener for toggle button
            const toggleBtn = row.querySelector('.toggle-status-btn');
            toggleBtn.addEventListener('click', (e) => {
                toggleAttendanceStatus(
                    record.studentId, 
                    state.currentClassId, 
                    data.date, 
                    record.status
                );
            });
            
            elements.classDetailTbody.appendChild(row);
        });
    }

    // Show Student Detail
    async function showStudentDetail(studentId) {
        if (!state.currentClassId) return;
        
        state.currentStudentId = studentId;
        
        try {
            // Fetch student attendance details
            const response = await fetch(`/attendance/api/student/${studentId}/attendance?class_id=${state.currentClassId}`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const data = await response.json();
            
            // Update student detail header
            elements.studentDetailTitle.textContent = `Student: ${data.studentName}`;
            elements.studentDetailClass.textContent = `Class: ${data.className} (${data.classCode})`;
            elements.presentCount.textContent = data.presentCount;
            elements.absentCount.textContent = data.absentCount;
            
            // Render student attendance dates
            renderStudentAttendanceDates(data.attendance);
            
            // Show student detail view
            elements.classOverview.style.display = 'none';
            elements.classDetailView.style.display = 'none';
            elements.studentDetailView.style.display = 'block';
            
        } catch (error) {
            console.error('Error showing student detail:', error);
            showAlert('Failed to load student attendance detail', 'danger');
            showClassDetail(state.currentClassId);
        }
    }

    // Render Student Attendance Dates
    function renderStudentAttendanceDates(attendance) {
        if (!elements.studentDatesBody) return;
        
        elements.studentDatesBody.innerHTML = '';
        
        if (!attendance || attendance.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = '<td colspan="3" class="text-center">No attendance records found</td>';
            elements.studentDatesBody.appendChild(row);
            return;
        }
        
        attendance.forEach(record => {
            const row = document.createElement('tr');
            const statusClass = record.status === 'Present' ? 'present-status' : 'absent-status';
            const btnClass = record.status === 'Present' ? 'absent-btn' : 'present-btn';
            const btnText = record.status === 'Present' ? 'Mark Absent' : 'Mark Present';
            
            row.innerHTML = `
                <td>${record.date}</td>
                <td class="${statusClass}">${record.status}</td>
                <td>
                    <button class="toggle-status-btn ${btnClass}" data-date="${record.date}">
                        ${btnText}
                    </button>
                </td>
            `;
            
            // Add click event to the toggle button
            const toggleBtn = row.querySelector('.toggle-status-btn');
            toggleBtn.addEventListener('click', () => {
                toggleAttendanceStatus(
                    state.currentStudentId,
                    state.currentClassId,
                    record.date,
                    record.status
                );
            });
            
            elements.studentDatesBody.appendChild(row);
        });
    }

    // Toggle Attendance Status
    async function toggleAttendanceStatus(studentId, classId, date, currentStatus) {
        if (!studentId || !classId || !date) return;
        
        const newStatus = currentStatus === 'Present' ? 'Absent' : 'Present';
        
        try {
            const response = await fetch('/attendance/api/update', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    studentId,
                    classId,
                    date,
                    status: newStatus
                })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // If in student detail view, refresh the student detail
                if (elements.studentDetailView.style.display !== 'none') {
                    showStudentDetail(studentId);
                } 
                // If in class detail view, refresh the class detail
                else if (elements.classDetailView.style.display !== 'none') {
                    showClassDetail(classId);
                }
                
                showAlert(`Attendance updated to ${newStatus}`, 'success');
            } else {
                showAlert(data.message || 'Failed to update attendance', 'danger');
            }
            
        } catch (error) {
            console.error('Error updating attendance:', error);
            showAlert('An error occurred while updating attendance', 'danger');
        }
    }

    // Show alert message
    function showAlert(message, type = 'info') {
        const alertContainer = document.getElementById('alertContainer');
        if (!alertContainer) return;
        
        const alert = document.createElement('div');
        alert.className = `alert alert-${type} alert-dismissible fade show`;
        alert.role = 'alert';
        
        alert.innerHTML = `
            ${message}
            <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>
        `;
        
        alertContainer.appendChild(alert);
        
        // Auto-remove after 5 seconds
        setTimeout(() => {
            alert.classList.remove('show');
            setTimeout(() => {
                alertContainer.removeChild(alert);
            }, 150);
        }, 5000);
    }
});
