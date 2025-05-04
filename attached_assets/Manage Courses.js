// Enhanced Manage Courses.js - with localStorage integration

// Store courses in memory and localStorage
let courses = JSON.parse(localStorage.getItem('courses')) || [
    { code: 'ITC321', description: 'Applications Development' },
    { code: 'ITP323', description: 'Capstone Project 1' },
    { code: 'ITP324', description: 'Information Assurance and Security 2' },
    { code: 'ITP325', description: 'Social and Professional Issues' },
    { code: 'ITP326', description: 'Systems Administration' }
];

// Save courses to localStorage
function saveCourses() {
    localStorage.setItem('courses', JSON.stringify(courses));
}

// Modal elements
const addCourseModal = document.getElementById('addCourseModal');
const editCourseModal = document.getElementById('editCourseModal');
const confirmationModal = document.getElementById('confirmationModal');
const closeAddCourseModal = document.getElementById('closeAddCourseModal');
const closeEditCourseModal = document.getElementById('closeEditCourseModal');
const btnAddCourse = document.getElementById('add-course-btn');
const btnConfirmYes = document.getElementById('confirm-yes');
const btnConfirmNo = document.getElementById('confirm-no');

// Track the course being deleted
let courseToDelete = null;

// Modal show/hide functions (with fade)
function showModal(modal) {
    modal.style.display = 'flex';
    void modal.offsetWidth;
    modal.classList.add('active');
    document.body.classList.add('modal-open');
}

function hideModal(modal) {
    modal.classList.remove('active');
    document.body.classList.remove('modal-open');
    
    // Reset form if it's the add course modal
    if (modal.id === 'addCourseModal') {
        document.getElementById('add-course-form').reset();
    }
    
    // Reset form if it's the edit course modal
    if (modal.id === 'editCourseModal') {
        document.getElementById('edit-course-form').reset();
    }
    
    modal.addEventListener('transitionend', function handler() {
        if (!modal.classList.contains('active')) {
            modal.style.display = 'none';
        }
        modal.removeEventListener('transitionend', handler);
    });
}

// Event listeners
document.addEventListener('DOMContentLoaded', function() {
    // First, save initial courses to localStorage if not already saved
    if (!localStorage.getItem('courses')) {
        saveCourses();
    }

    updateCourseCount();
    refreshCourseTable();

    // Add Course button
    if (btnAddCourse) {
        btnAddCourse.addEventListener('click', function() {
            showModal(addCourseModal);
        });
    }

    // Close buttons for modals
    closeAddCourseModal.addEventListener('click', function() {
        hideModal(addCourseModal);
    });

    closeEditCourseModal.addEventListener('click', function() {
        hideModal(editCourseModal);
    });

    // No button in confirmation modal
    btnConfirmNo.addEventListener('click', function() {
        courseToDelete = null;  // Reset the course to delete
        hideModal(confirmationModal);
    });

    document.getElementById('add-course-form').addEventListener('submit', function(e) {
        e.preventDefault();
        addCourse();
    });

    document.getElementById('edit-course-form').addEventListener('submit', function(e) {
        e.preventDefault();
        saveCourseEdit();
    });

    btnConfirmYes.addEventListener('click', function() {
        if (courseToDelete) {
            deleteCourse(courseToDelete);
        }
        hideModal(confirmationModal);
    });

    // Sidebar menu clicks
    document.querySelectorAll('.menu-item').forEach(item => {
        item.addEventListener('click', function() {
            const menuText = this.textContent.trim();
            if (menuText === 'Manage Students') {
                window.location.href = 'Manage Students.html';
            } else if (menuText === 'Manage Instructors') {
                window.location.href = 'Manage Instructor.html';
            } else if (menuText === 'Manage Courses') {
                window.location.href = 'Manage Courses.html';
            } else if (menuText === 'Manage Class') {
                window.location.href = 'Manage Class.html';
            } else if (menuText === 'Manage Instructor Attendance') {
                window.location.href = 'Manage Instructor Attendance.html';
            }
        });
    });

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
});

// Add a new course
function addCourse() {
    const courseCode = document.getElementById('course-code-input').value;
    const courseDescription = document.getElementById('course-description-input').value;

    if (courses.some(course => course.code === courseCode)) {
        alert('Course code already exists!');
        return;
    }

    courses.push({ code: courseCode, description: courseDescription });
    addCourseToTable(courseCode, courseDescription);
    updateCourseCount();
    saveCourses(); // Save to localStorage
    document.getElementById('add-course-form').reset();
    hideModal(addCourseModal);
}

// Add course to table
function addCourseToTable(code, description) {
    const tableBody = document.getElementById('course-table-body');
    const newRow = document.createElement('tr');

    newRow.innerHTML = `
        <td>${code}</td>
        <td>${description}</td>
        <td>
            <div class="action-icons">
                <button class="delete-icon" onclick="confirmDelete('${code}')">
                    <i class="fa-solid fa-trash-can fa-lg"></i>
                </button>
                <button class="edit-icon" onclick="openEditModal('${code}', '${description}')">
                    <i class="fa-solid fa-pen-to-square fa-lg"></i>
                </button>
            </div>
        </td>
    `;

    tableBody.appendChild(newRow);
}

// Open edit modal
function openEditModal(code, description) {
    document.getElementById('original-course-code').value = code;
    document.getElementById('edit-course-code').value = code;
    document.getElementById('edit-course-description').value = description;
    showModal(editCourseModal);
}

// Save course edit
function saveCourseEdit() {
    const originalCode = document.getElementById('original-course-code').value;
    const newCode = document.getElementById('edit-course-code').value;
    const newDescription = document.getElementById('edit-course-description').value;

    if (newCode !== originalCode && courses.some(course => course.code === newCode)) {
        alert('Course code already exists!');
        return;
    }

    const index = courses.findIndex(course => course.code === originalCode);
    if (index !== -1) {
        courses[index] = { code: newCode, description: newDescription };
        
        // Update any classes using this course code
        updateClassesForCourseChange(originalCode, newCode, newDescription);
    }

    saveCourses(); // Save to localStorage
    refreshCourseTable();
    hideModal(editCourseModal);
}

// Update classes when a course is changed
function updateClassesForCourseChange(oldCode, newCode, newDescription) {
    // Get classes from localStorage
    let classes = JSON.parse(localStorage.getItem('classes')) || [];
    
    // Check if any classes are using the old course code
    const updatedClasses = classes.map(cls => {
        if (cls.courseCode === oldCode) {
            return {
                ...cls,
                courseCode: newCode,
                description: newDescription
            };
        }
        return cls;
    });
    
    // Save updated classes
    localStorage.setItem('classes', JSON.stringify(updatedClasses));
}

// Confirm delete
function confirmDelete(code) {
    // Check if any classes use this course code
    const classes = JSON.parse(localStorage.getItem('classes')) || [];
    const courseInUse = classes.some(cls => cls.courseCode === code);
    
    if (courseInUse) {
        alert('Cannot delete course because it is currently being used by one or more classes.');
        return;
    }
    
    courseToDelete = code;
    showModal(confirmationModal);
}

// Delete course
function deleteCourse(code) {
    courses = courses.filter(course => course.code !== code);
    saveCourses(); // Save to localStorage
    refreshCourseTable();
    updateCourseCount();
}

// Refresh course table
function refreshCourseTable() {
    const tableBody = document.getElementById('course-table-body');
    tableBody.innerHTML = '';
    courses.forEach(course => {
        addCourseToTable(course.code, course.description);
    });
}

// Update course count
function updateCourseCount() {
    document.getElementById('course-count').textContent = courses.length;
}