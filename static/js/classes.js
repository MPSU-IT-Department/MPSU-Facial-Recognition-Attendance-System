/**
 * Classes Management JavaScript
 * Handles the UI interactions for managing classes
 */

// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Classes page initialized');
    
    // Fetch initial data
    fetchClasses();
    
    // Populate courses dropdown
    populateCourseDropdown();
    
    // Set up event listeners
    setupEventListeners();
    
    // Set up course change handler
    setupCourseChangeHandler();
});

// Global variables to track state
let classes = [];
let selectedClassId = null;
let currentView = 'classes'; // 'classes', 'class-detail', 'student-selection'
let courses = [];

/**
 * Set up all event listeners for interactive elements
 */
function setupEventListeners() {
    // Add class button (admin only)
    const addClassBtn = document.getElementById('add-class-btn');
    if (addClassBtn) {
        // Check if user is admin before showing the button
        fetch('/auth/check-auth')
            .then(response => response.json())
            .then(data => {
                if (data.user && data.user.role === 'admin') {
                    addClassBtn.addEventListener('click', showAddClassModal);
                } else {
                    // Hide button for non-admin users
                    addClassBtn.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Error checking user role:', error);
                // Hide button on error
                addClassBtn.style.display = 'none';
            });
    }
    
    // Search class input
    const searchClassInput = document.getElementById('searchClassInput');
    const searchClassBtn = document.getElementById('searchClassBtn');
    
    if (searchClassInput && searchClassBtn) {
        searchClassBtn.addEventListener('click', function() {
            searchClasses(searchClassInput.value);
        });
        
        searchClassInput.addEventListener('keyup', function(e) {
            if (e.key === 'Enter') {
                searchClasses(searchClassInput.value);
            }
        });
    }
    
    // Close class modal
    const closeClassModalBtn = document.getElementById('close-class-modal');
    if (closeClassModalBtn) {
        closeClassModalBtn.addEventListener('click', closeClassModal);
    }
    
    // Class form submission
    const classForm = document.getElementById('class-form');
    if (classForm) {
        classForm.addEventListener('submit', function(e) {
            e.preventDefault();
            saveClass();
        });
    }
    
    // Close confirmation modal
    const closeConfirmationModalBtn = document.getElementById('close-confirmation-modal');
    const confirmNoBtn = document.getElementById('confirm-no');
    
    if (closeConfirmationModalBtn && confirmNoBtn) {
        closeConfirmationModalBtn.addEventListener('click', closeConfirmationModal);
        confirmNoBtn.addEventListener('click', closeConfirmationModal);
    }
    
    // Confirm delete button
    const confirmYesBtn = document.getElementById('confirm-yes');
    if (confirmYesBtn) {
        confirmYesBtn.addEventListener('click', confirmDeleteClass);
    }
    
    // Back to classes button
    const backToClassesBtn = document.getElementById('back-to-classes');
    if (backToClassesBtn) {
        backToClassesBtn.addEventListener('click', function() {
            showView('classes');
        });
    }
    
    // Enroll student button
    const enrollStudentBtn = document.getElementById('enroll-student-btn');
    if (enrollStudentBtn) {
        enrollStudentBtn.addEventListener('click', function() {
            showView('student-selection');
            getAllStudents();
        });
    }
    
    // Back to class detail button
    const backToClassDetailBtn = document.getElementById('back-to-class-detail');
    if (backToClassDetailBtn) {
        backToClassDetailBtn.addEventListener('click', function() {
            showView('class-detail');
        });
    }
    
    // Search student input
    const searchStudentInput = document.getElementById('searchStudentInput');
    const searchStudentBtn = document.getElementById('searchStudentBtn');
    
    if (searchStudentInput && searchStudentBtn) {
        searchStudentBtn.addEventListener('click', function() {
            searchStudents(searchStudentInput.value);
        });
        
        searchStudentInput.addEventListener('keyup', function(e) {
            if (e.key === 'Enter') {
                searchStudents(searchStudentInput.value);
            }
        });
    }
}

/**
 * Set up the course change handler
 */
function setupCourseChangeHandler() {
    const courseSelect = document.getElementById('course');
    const classCodeInput = document.getElementById('classCode');
    const descriptionInput = document.getElementById('description');
    
    if (courseSelect && classCodeInput && descriptionInput) {
        courseSelect.addEventListener('change', function() {
            const selectedCourse = courseSelect.value;
            if (selectedCourse) {
                // Find the course details
                const course = courses.find(c => c.code === selectedCourse);
                if (course) {
                    // Auto-fill the class code (course code + section) and description
                    // Only do this for new classes, not for edits
                    if (!selectedClassId) {
                        // Generate next available section (A, B, C, etc.)
                        const courseClasses = classes.filter(c => c.classCode.startsWith(selectedCourse));
                        const sections = courseClasses.map(c => c.classCode.split('-')[1] || '');
                        
                        let nextSection = 'A';
                        // Find next available section letter
                        while (sections.includes(nextSection)) {
                            nextSection = String.fromCharCode(nextSection.charCodeAt(0) + 1);
                        }
                        
                        classCodeInput.value = `${selectedCourse}-${nextSection}`;
                    }
                    
                    // Set the description from the course
                    descriptionInput.value = course.description;
                }
            }
        });
    }
}

/**
 * Fetch all classes from the API
 */
function fetchClasses() {
    const classesTableBody = document.getElementById('classes-table-body');
    if (!classesTableBody) return;
    
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    
    fetch(`/classes/api/list?_=${timestamp}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Classes data:', data);
            classes = data;
            renderClassesTable();
        })
        .catch(error => {
            console.error('Error fetching classes:', error);
            classesTableBody.innerHTML = `
                <tr>
                    <td colspan="6" class="text-center text-danger">
                        Error loading classes. Please try again later.<br>
                        <small>${error.message}</small>
                    </td>
                </tr>
            `;
            
            // Show a retry button
            const retryButton = document.createElement('button');
            retryButton.textContent = 'Retry';
            retryButton.className = 'btn btn-sm btn-primary mt-2';
            retryButton.addEventListener('click', () => {
                classesTableBody.innerHTML = '<tr><td colspan="6" class="text-center">Loading classes...</td></tr>';
                fetchClasses();
            });
            
            classesTableBody.querySelector('td').appendChild(retryButton);
        });
}

/**
 * Render the classes table with the current data
 */
function renderClassesTable() {
    const classesTableBody = document.getElementById('classes-table-body');
    if (!classesTableBody) return;
    
    if (classes.length === 0) {
        classesTableBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center">No classes found</td>
            </tr>
        `;
        return;
    }
    
    classesTableBody.innerHTML = '';
    
    // Display all classes
    classes.forEach(cls => {
        const row = document.createElement('tr');
        row.className = 'clickable-row';
        row.dataset.classId = cls.id;
        
        // Get user role from the page context instead of fetching
        const isAdmin = document.body.classList.contains('admin-role'); 
        
        // For admin users, show edit and delete buttons
        // For instructors, only show view button
        row.innerHTML = `
            <td>${cls.classCode}</td>
            <td>${cls.description}</td>
            <td>${cls.roomNumber}</td>
            <td>${cls.schedule}</td>
            <td>${cls.instructorName}</td>
            <td>
                ${isAdmin ? `
                    <button class="action-btn edit-class" title="Edit Class">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="action-btn delete-class" title="Delete Class">
                        <i class="fas fa-trash"></i>
                    </button>
                ` : `
                    <button class="action-btn view-class" title="View Class">
                        <i class="fas fa-eye"></i>
                    </button>
                `}
            </td>
        `;

        classesTableBody.appendChild(row);
        
        // Add event listeners to the row for showing class detail
        row.addEventListener('click', function(e) {
            // Ignore clicks on action buttons
            if (e.target.closest('.action-btn')) return;
            
            const classId = parseInt(this.dataset.classId);
            showClassDetail(classId);
        });
        
        // Add event listeners to buttons
        const editButton = row.querySelector('.edit-class');
        const deleteButton = row.querySelector('.delete-class');
        
        editButton.addEventListener('click', function() {
            const classId = parseInt(row.dataset.classId);
            editClass(classId);
        });
        
        deleteButton.addEventListener('click', function() {
            const classId = parseInt(row.dataset.classId);
            deleteClass(classId);
        });
    });
    
    console.log('Classes table rendered with', classes.length, 'classes');
}

/**
 * Fetch courses for the dropdown
 */
function populateCourseDropdown() {
    const courseSelect = document.getElementById('course');
    if (!courseSelect) return;
    
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    
    fetch(`/courses/api/list?_=${timestamp}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('Courses data:', data);
            courses = data;
            
            // Clear existing options except the first one
            while (courseSelect.options.length > 1) {
                courseSelect.remove(1);
            }
            
            // Add course options
            courses.forEach(course => {
                const option = document.createElement('option');
                option.value = course.code;
                option.textContent = `${course.code} - ${course.description}`;
                courseSelect.appendChild(option);
            });
        })
        .catch(error => {
            console.error('Error fetching courses:', error);
            
            // Add a placeholder option
            const option = document.createElement('option');
            option.disabled = true;
            option.textContent = 'Error loading courses';
            courseSelect.appendChild(option);
        });
}

/**
 * Search classes based on a query string
 * @param {string} query - The search query
 */
function searchClasses(query) {
    const classesTableBody = document.getElementById('classes-table-body');
    if (!classesTableBody) return;
    
    query = query.toLowerCase().trim();
    
    if (query === '') {
        renderClassesTable();
        return;
    }
    
    const filteredClasses = classes.filter(cls => 
        cls.classCode.toLowerCase().includes(query) ||
        cls.description.toLowerCase().includes(query) ||
        cls.roomNumber.toLowerCase().includes(query) ||
        cls.schedule.toLowerCase().includes(query) ||
        cls.instructorName.toLowerCase().includes(query)
    );
    
    if (filteredClasses.length === 0) {
        classesTableBody.innerHTML = `
            <tr>
                <td colspan="6" class="text-center">No classes found matching "${query}"</td>
            </tr>
        `;
        return;
    }
    
    classesTableBody.innerHTML = '';
    
    // Display filtered classes
    filteredClasses.forEach(cls => {
        const row = document.createElement('tr');
        row.className = 'clickable-row';
        row.dataset.classId = cls.id;
        
        // Get user role from the page context instead of fetching
        const isAdmin = document.body.classList.contains('admin-role'); 
        
        // For admin users, show edit and delete buttons
        // For instructors, only show view button
        row.innerHTML = `
            <td>${cls.classCode}</td>
            <td>${cls.description}</td>
            <td>${cls.roomNumber}</td>
            <td>${cls.schedule}</td>
            <td>${cls.instructorName}</td>
            <td>
                ${isAdmin ? `
                    <button class="action-btn edit-class" title="Edit Class">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="action-btn delete-class" title="Delete Class">
                        <i class="fas fa-trash"></i>
                    </button>
                ` : `
                    <button class="action-btn view-class" title="View Class">
                        <i class="fas fa-eye"></i>
                    </button>
                `}
            </td>
        `;

        classesTableBody.appendChild(row);
        
        // Add event listeners to the row for showing class detail
        row.addEventListener('click', function(e) {
            // Ignore clicks on action buttons
            if (e.target.closest('.action-btn')) return;
            
            const classId = parseInt(this.dataset.classId);
            showClassDetail(classId);
        });
        
        // Add event listeners to buttons
        const editButton = row.querySelector('.edit-class');
        const deleteButton = row.querySelector('.delete-class');
        
        editButton.addEventListener('click', function() {
            const classId = parseInt(row.dataset.classId);
            editClass(classId);
        });
        
        deleteButton.addEventListener('click', function() {
            const classId = parseInt(row.dataset.classId);
            deleteClass(classId);
        });
    });
}

/**
 * Show the class detail view for a specific class
 * @param {number} classId - The ID of the class to show
 */
function showClassDetail(classId) {
    console.log('Showing detail for class ID:', classId);
    selectedClassId = classId;
    
    // Find the class in our data
    const selectedClass = classes.find(c => c.id === classId);
    if (!selectedClass) {
        console.error('Class not found:', classId);
        return;
    }
    
    // Set the title
    const detailTitle = document.getElementById('class-detail-title');
    if (detailTitle) {
        detailTitle.textContent = `${selectedClass.classCode}: ${selectedClass.description}`;
    }
    
    // Switch to the detail view
    showView('class-detail');
    
    // Get enrolled students for this class
    getClassStudents(classId);
}

/**
 * Get students enrolled in a specific class
 * @param {number} classId - The ID of the class
 */
function getClassStudents(classId) {
    const enrolledStudentsList = document.getElementById('enrolled-students-list');
    if (!enrolledStudentsList) return;
    
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    
    enrolledStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">Loading enrolled students...</td></tr>`;
    
    fetch(`/classes/api/${classId}/students?_=${timestamp}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(students => {
            console.log('Enrolled students:', students);
            
            if (students.length === 0) {
                enrolledStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">No students enrolled</td></tr>`;
                return;
            }
            
            enrolledStudentsList.innerHTML = '';
            
            students.forEach(student => {
                const row = document.createElement('tr');
                row.innerHTML = `
                    <td>${student.firstName} ${student.lastName}</td>
                    <td>${student.id}</td>
                    <td>${student.yearLevel}</td>
                    <td>${student.phone}</td>
                    <td>
                        <button class="btn btn-sm btn-outline-danger btn-unenroll" data-student-id="${student.id}" data-enrollment-id="${student.enrollmentId}">
                            <i class="fas fa-user-minus"></i> Unenroll
                        </button>
                    </td>
                `;
                
                enrolledStudentsList.appendChild(row);
                
                // Add unenroll button handler
                const unenrollBtn = row.querySelector('.btn-unenroll');
                if (unenrollBtn) {
                    unenrollBtn.addEventListener('click', function() {
                        const studentId = this.dataset.studentId;
                        const enrollmentId = parseInt(this.dataset.enrollmentId);
                        unenrollStudent(studentId, enrollmentId);
                    });
                }
            });
        })
        .catch(error => {
            console.error('Error fetching enrolled students:', error);
            enrolledStudentsList.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-danger">
                        Error loading enrolled students. Please try again later.<br>
                        <small>${error.message}</small>
                    </td>
                </tr>
            `;
        });
}

/**
 * Get all students for the enrollment view
 */
function getAllStudents() {
    const allStudentsList = document.getElementById('all-students-list');
    if (!allStudentsList) return;
    
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    
    allStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">Loading students...</td></tr>`;
    
    fetch(`/students/api/list?_=${timestamp}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(students => {
            console.log('All students:', students);
            
            if (students.length === 0) {
                allStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">No students found</td></tr>`;
                return;
            }
            
            // Get currently enrolled students
            const classId = selectedClassId;
            
            fetch(`/classes/api/${classId}/students?_=${timestamp}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(enrolledStudents => {
                    console.log('Enrolled students for comparison:', enrolledStudents);
                    
                    // Get IDs of enrolled students
                    const enrolledStudentIds = enrolledStudents.map(student => student.id);
                    
                    allStudentsList.innerHTML = '';
                    
                    // Show only students who are not already enrolled
                    students.filter(student => !enrolledStudentIds.includes(student.id))
                            .forEach(student => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${student.firstName} ${student.lastName}</td>
                            <td>${student.id}</td>
                            <td>${student.yearLevel}</td>
                            <td>${student.phone}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary btn-enroll" data-student-id="${student.id}">
                                    <i class="fas fa-user-plus"></i> Enroll
                                </button>
                            </td>
                        `;
                        
                        allStudentsList.appendChild(row);
                        
                        // Add enroll button handler
                        const enrollBtn = row.querySelector('.btn-enroll');
                        if (enrollBtn) {
                            enrollBtn.addEventListener('click', function() {
                                const studentId = this.dataset.studentId;
                                enrollStudent(studentId);
                            });
                        }
                    });
                    
                    if (allStudentsList.children.length === 0) {
                        allStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">All students are already enrolled in this class</td></tr>`;
                    }
                })
                .catch(error => {
                    console.error('Error fetching enrolled students for comparison:', error);
                    // Continue showing all students if we can't get enrollment data
                    showAllStudents(students);
                });
        })
        .catch(error => {
            console.error('Error fetching all students:', error);
            allStudentsList.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-danger">
                        Error loading students. Please try again later.<br>
                        <small>${error.message}</small>
                    </td>
                </tr>
            `;
        });
}

/**
 * Search students in the all students list
 * @param {string} query - The search query
 */
function searchStudents(query) {
    const allStudentsList = document.getElementById('all-students-list');
    if (!allStudentsList) return;
    
    query = query.toLowerCase().trim();
    
    if (query === '') {
        getAllStudents();
        return;
    }
    
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    
    allStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">Searching students...</td></tr>`;
    
    fetch(`/students/api/search?query=${encodeURIComponent(query)}&_=${timestamp}`)
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(students => {
            console.log('Search results:', students);
            
            if (students.length === 0) {
                allStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">No students found matching "${query}"</td></tr>`;
                return;
            }
            
            // Get currently enrolled students
            const classId = selectedClassId;
            
            fetch(`/classes/api/${classId}/students?_=${timestamp}`)
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! Status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(enrolledStudents => {
                    console.log('Enrolled students for comparison:', enrolledStudents);
                    
                    // Get IDs of enrolled students
                    const enrolledStudentIds = enrolledStudents.map(student => student.id);
                    
                    allStudentsList.innerHTML = '';
                    
                    // Show only students who are not already enrolled
                    students.filter(student => !enrolledStudentIds.includes(student.id))
                            .forEach(student => {
                        const row = document.createElement('tr');
                        row.innerHTML = `
                            <td>${student.firstName} ${student.lastName}</td>
                            <td>${student.id}</td>
                            <td>${student.yearLevel}</td>
                            <td>${student.phone}</td>
                            <td>
                                <button class="btn btn-sm btn-outline-primary btn-enroll" data-student-id="${student.id}">
                                    <i class="fas fa-user-plus"></i> Enroll
                                </button>
                            </td>
                        `;
                        
                        allStudentsList.appendChild(row);
                        
                        // Add enroll button handler
                        const enrollBtn = row.querySelector('.btn-enroll');
                        if (enrollBtn) {
                            enrollBtn.addEventListener('click', function() {
                                const studentId = this.dataset.studentId;
                                enrollStudent(studentId);
                            });
                        }
                    });
                    
                    if (allStudentsList.children.length === 0) {
                        allStudentsList.innerHTML = `<tr><td colspan="5" class="text-center">No matching students available for enrollment</td></tr>`;
                    }
                })
                .catch(error => {
                    console.error('Error fetching enrolled students for comparison:', error);
                    // Continue showing all students if we can't get enrollment data
                    showAllStudents(students);
                });
        })
        .catch(error => {
            console.error('Error searching students:', error);
            allStudentsList.innerHTML = `
                <tr>
                    <td colspan="5" class="text-center text-danger">
                        Error searching students. Please try again later.<br>
                        <small>${error.message}</small>
                    </td>
                </tr>
            `;
        });
}

/**
 * Show all students without filtering based on enrollment
 * @param {Array} students - The students to display
 */
function showAllStudents(students) {
    const allStudentsList = document.getElementById('all-students-list');
    if (!allStudentsList) return;
    
    allStudentsList.innerHTML = '';
    
    students.forEach(student => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${student.firstName} ${student.lastName}</td>
            <td>${student.id}</td>
            <td>${student.yearLevel}</td>
            <td>${student.phone}</td>
            <td>
                <button class="btn btn-sm btn-outline-primary btn-enroll" data-student-id="${student.id}">
                    <i class="fas fa-user-plus"></i> Enroll
                </button>
            </td>
        `;
        
        allStudentsList.appendChild(row);
        
        // Add enroll button handler
        const enrollBtn = row.querySelector('.btn-enroll');
        if (enrollBtn) {
            enrollBtn.addEventListener('click', function() {
                const studentId = this.dataset.studentId;
                enrollStudent(studentId);
            });
        }
    });
}

/**
 * Enroll a student in the selected class
 * @param {string} studentId - The ID of the student to enroll
 */
function enrollStudent(studentId) {
    if (!selectedClassId) {
        console.error('No class selected for enrollment');
        return;
    }
    
    console.log(`Enrolling student ${studentId} in class ${selectedClassId}`);
    
    // Add timestamp to prevent caching
    const timestamp = new Date().getTime();
    
    fetch(`/classes/api/${selectedClassId}/enroll`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({
            studentId: studentId
        })
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.message || `HTTP error! Status: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Enrollment successful:', data);
        
        // Show a success message
        alert('Student enrolled successfully!');
        
        // Refresh the class detail view
        showClassDetail(selectedClassId);
    })
    .catch(error => {
        console.error('Error enrolling student:', error);
        alert(`Error enrolling student: ${error.message}`);
    });
}

/**
 * Unenroll a student from the selected class
 * @param {string} studentId - The ID of the student to unenroll
 * @param {number} enrollmentId - The ID of the enrollment record
 */
function unenrollStudent(studentId, enrollmentId) {
    if (!selectedClassId) {
        console.error('No class selected for unenrollment');
        return;
    }
    
    if (!confirm(`Are you sure you want to unenroll this student from the class?`)) {
        return;
    }
    
    console.log(`Unenrolling student ${studentId} from class ${selectedClassId} with enrollment ID ${enrollmentId}`);
    
    // Using the endpoint that takes an enrollment ID
    fetch(`/classes/api/${selectedClassId}/unenroll/${enrollmentId}`, {
        method: 'DELETE',
        headers: {
            'Accept': 'application/json'
        }
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.message || `HTTP error! Status: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Unenrollment successful:', data);
        
        // Show a success message
        alert('Student unenrolled successfully!');
        
        // Refresh the class detail view
        showClassDetail(selectedClassId);
    })
    .catch(error => {
        console.error('Error unenrolling student:', error);
        alert(`Error unenrolling student: ${error.message}`);
    });
}

/**
 * Show the add class modal
 */
function showAddClassModal() {
    console.log('Showing add class modal');
    
    // Get all form elements
    const classForm = document.getElementById('class-form');
    const classIdInput = document.getElementById('classId');
    const classCodeInput = document.getElementById('classCode');
    const courseSelect = document.getElementById('course');
    const descriptionInput = document.getElementById('description');
    const roomNumberInput = document.getElementById('roomNumber');
    const scheduleInput = document.getElementById('schedule');
    const instructorIdSelect = document.getElementById('instructorId');
    const modalTitle = document.getElementById('class-modal-title');
    const scheduleDisplay = document.getElementById('scheduleDisplay');
    
    // Completely reset the form
    if (classForm) {
        classForm.reset();
    }
    
    // Clear all form fields manually to ensure no residual data
    if (classIdInput) classIdInput.value = '';
    if (classCodeInput) classCodeInput.value = '';
    if (descriptionInput) descriptionInput.value = '';
    if (roomNumberInput) roomNumberInput.value = '';
    if (scheduleInput) scheduleInput.value = '';
    
    // Reset the course dropdown
    if (courseSelect) {
        // Clear selection by setting to the first blank option
        courseSelect.selectedIndex = 0;
    }
    
    // Reset instructor dropdown to first option
    if (instructorIdSelect && instructorIdSelect.options.length > 0) {
        instructorIdSelect.selectedIndex = 0;
    }
    
    // Reset day checkboxes
    const dayCheckboxes = document.querySelectorAll('.day-checkbox');
    dayCheckboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    
    // Clear schedule display
    if (scheduleDisplay) {
        scheduleDisplay.innerHTML = '<span class="text-muted">No time slots added</span>';
    }
    
    // Reset time inputs to default values
    const startTime = document.getElementById('startTime');
    const endTime = document.getElementById('endTime');
    if (startTime) startTime.value = '10:00';
    if (endTime) endTime.value = '12:00';
    
    if (modalTitle) {
        modalTitle.textContent = 'Add New Class';
    }
    
    // Clear the selected class ID
    selectedClassId = null;
    
    // Show the modal
    const classModal = document.getElementById('class-modal');
    if (classModal) {
        classModal.classList.add('show');
        
        // Set initial focus after a small delay to ensure DOM is ready
        if (courseSelect) {
            setTimeout(() => courseSelect.focus(), 100);
        }
    }
}

/**
 * Edit an existing class
 * @param {number} classId - The ID of the class to edit
 */
function editClass(classId) {
    console.log('Editing class ID:', classId);
    
    const classToEdit = classes.find(c => c.id === classId);
    if (!classToEdit) {
        console.error('Class not found:', classId);
        return;
    }
    
    // Set up the form with existing values
    const classForm = document.getElementById('class-form');
    const classIdInput = document.getElementById('classId');
    const classCodeInput = document.getElementById('classCode');
    const courseSelect = document.getElementById('course');
    const descriptionInput = document.getElementById('description');
    const roomNumberInput = document.getElementById('roomNumber');
    const scheduleInput = document.getElementById('schedule');
    const instructorIdSelect = document.getElementById('instructorId');
    const modalTitle = document.getElementById('class-modal-title');
    
    if (classForm && classIdInput && classCodeInput && courseSelect && 
        descriptionInput && roomNumberInput && scheduleInput && 
        instructorIdSelect && modalTitle) {
        
        // Extract course code from class code (before the dash)
        const courseCode = classToEdit.classCode.split('-')[0];
        
        classIdInput.value = classToEdit.id;
        classCodeInput.value = classToEdit.classCode;
        
        // Set the course dropdown
        for (let i = 0; i < courseSelect.options.length; i++) {
            if (courseSelect.options[i].value === courseCode) {
                courseSelect.selectedIndex = i;
                break;
            }
        }
        
        descriptionInput.value = classToEdit.description;
        roomNumberInput.value = classToEdit.roomNumber;
        
        // Set up the schedule builder with existing schedule
        if (typeof setupScheduleBuilder === 'function') {
            setupScheduleBuilder(classToEdit.schedule);
        } else {
            scheduleInput.value = classToEdit.schedule;
        }
        
        // Set the instructor dropdown
        for (let i = 0; i < instructorIdSelect.options.length; i++) {
            if (parseInt(instructorIdSelect.options[i].value) === classToEdit.instructorId) {
                instructorIdSelect.selectedIndex = i;
                break;
            }
        }
        
        modalTitle.textContent = 'Edit Class';
        selectedClassId = classId;
    }
    
    // Show the modal
    const classModal = document.getElementById('class-modal');
    if (classModal) {
        classModal.classList.add('show');
        
        // Set initial focus
        if (roomNumberInput) {
            setTimeout(() => roomNumberInput.focus(), 100);
        }
    }
}

/**
 * Save a class (create or update)
 */
function saveClass() {
    console.log('Saving class');
    
    const classIdInput = document.getElementById('classId');
    const classCodeInput = document.getElementById('classCode');
    const descriptionInput = document.getElementById('description');
    const roomNumberInput = document.getElementById('roomNumber');
    const scheduleInput = document.getElementById('schedule');
    const instructorIdSelect = document.getElementById('instructorId');
    
    if (!classCodeInput || !descriptionInput || !roomNumberInput || !scheduleInput || !instructorIdSelect) {
        console.error('Missing form elements');
        return;
    }
    
    const classId = classIdInput.value ? parseInt(classIdInput.value) : null;
    const classCode = classCodeInput.value.trim();
    const description = descriptionInput.value.trim();
    const roomNumber = roomNumberInput.value.trim();
    let schedule = scheduleInput.value.trim();
    const instructorId = parseInt(instructorIdSelect.value);
    
    console.log('Schedule value:', schedule);
    
    // Get any time slots that may have been added
    const scheduleDisplay = document.getElementById('scheduleDisplay');
    const slots = scheduleDisplay ? scheduleDisplay.querySelectorAll('.schedule-slot') : [];
    
    console.log('Found', slots.length, 'time slots in the display');
    
    // If there are slots but the schedule field is empty, let's build a schedule from the slots
    if (slots.length > 0 && !schedule) {
        schedule = '';
        slots.forEach((slot, index) => {
            const days = slot.querySelector('.days').textContent;
            const time = slot.querySelector('.time').textContent;
            
            schedule += `${days.replace(/,\s*/g, '')} ${time}`;
            
            if (index < slots.length - 1) {
                schedule += ', ';
            }
        });
        
        // Update the hidden schedule field
        scheduleInput.value = schedule;
        console.log('Built schedule from slots:', schedule);
    }
    
    // Validate form
    if (!classCode) {
        alert('Please enter a class code');
        classCodeInput.focus();
        return;
    }
    
    if (!description) {
        alert('Please enter a description');
        descriptionInput.focus();
        return;
    }
    
    if (!roomNumber) {
        alert('Please enter a room number');
        roomNumberInput.focus();
        return;
    }
    
    // Final check for schedule
    schedule = scheduleInput.value.trim();
    if (!schedule) {
        // Check if we have time inputs that can be used to create a schedule
        const startTime = document.getElementById('startTime');
        const endTime = document.getElementById('endTime');
        const selectedDays = getSelectedDays ? getSelectedDays() : [];
        
        if (startTime && endTime && startTime.value && endTime.value && selectedDays.length > 0) {
            // Build a schedule from the current inputs
            const formattedStartTime = formatTime ? formatTime(startTime.value) : startTime.value;
            const formattedEndTime = formatTime ? formatTime(endTime.value) : endTime.value;
            schedule = `${selectedDays.join('')} ${formattedStartTime} - ${formattedEndTime}`;
            scheduleInput.value = schedule;
            console.log('Created schedule from current inputs:', schedule);
        } else {
            alert('Please set a schedule by clicking the Add button after selecting days and times');
            // Focus on the Add button to guide the user
            const addTimeBtn = document.getElementById('addTimeBtn');
            if (addTimeBtn) {
                addTimeBtn.focus();
                // Add a visual highlight to the Add button
                addTimeBtn.style.boxShadow = '0 0 0 3px rgba(23, 206, 154, 0.5)';
                setTimeout(() => {
                    addTimeBtn.style.boxShadow = '';
                }, 2000);
            }
            return;
        }
    }
    
    if (!instructorId) {
        alert('Please select an instructor');
        instructorIdSelect.focus();
        return;
    }
    
    const classData = {
        classCode,
        description,
        roomNumber,
        schedule,
        instructorId
    };
    
    console.log('Class data to save:', classData);
    
    // Determine if this is a create or update operation
    const isUpdate = !!classId;
    
    const url = isUpdate 
        ? `/classes/api/update/${classId}`
        : '/classes/api/create';
    
    const method = isUpdate ? 'PUT' : 'POST';
    
    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json',
        },
        body: JSON.stringify(classData)
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.message || `HTTP error! Status: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Class saved successfully:', data);
        
        // Close the modal
        closeClassModal();
        
        // Show a success message
        alert(isUpdate ? 'Class updated successfully!' : 'Class created successfully!');
        
        // Refresh the classes list
        fetchClasses();
    })
    .catch(error => {
        console.error('Error saving class:', error);
        alert(`Error saving class: ${error.message}`);
    });
}

/**
 * Delete a class
 * @param {number} classId - The ID of the class to delete
 */
function deleteClass(classId) {
    console.log('Deleting class ID:', classId);
    
    const classToDelete = classes.find(c => c.id === classId);
    if (!classToDelete) {
        console.error('Class not found:', classId);
        return;
    }
    
    // Set up the confirmation modal
    const confirmationText = document.getElementById('confirmation-text');
    
    if (confirmationText) {
        confirmationText.innerHTML = `
            Are you sure you want to delete class <strong>${classToDelete.classCode}</strong>?<br>
            This will remove all enrollments and attendance records for this class.
        `;
    }
    
    // Store the class ID for the confirmation handler
    selectedClassId = classId;
    
    // Show the confirmation modal
    const confirmationModal = document.getElementById('confirmation-modal');
    if (confirmationModal) {
        confirmationModal.classList.add('show');
    }
}

/**
 * Confirm and execute class deletion
 */
function confirmDeleteClass() {
    if (!selectedClassId) {
        console.error('No class selected for deletion');
        return;
    }
    
    console.log('Confirming deletion of class ID:', selectedClassId);
    
    fetch(`/classes/api/delete/${selectedClassId}`, {
        method: 'DELETE'
    })
    .then(response => {
        if (!response.ok) {
            return response.json().then(data => {
                throw new Error(data.message || `HTTP error! Status: ${response.status}`);
            });
        }
        return response.json();
    })
    .then(data => {
        console.log('Class deleted successfully:', data);
        
        // Close the confirmation modal
        closeConfirmationModal();
        
        // Show a success message
        alert('Class deleted successfully!');
        
        // Refresh the classes list
        fetchClasses();
    })
    .catch(error => {
        console.error('Error deleting class:', error);
        alert(`Error deleting class: ${error.message}`);
        
        // Close the confirmation modal
        closeConfirmationModal();
    });
}

/**
 * Close the class modal
 */
function closeClassModal() {
    const classModal = document.getElementById('class-modal');
    if (classModal) {
        classModal.classList.remove('show');
    }
}

/**
 * Close the confirmation modal
 */
function closeConfirmationModal() {
    const confirmationModal = document.getElementById('confirmation-modal');
    if (confirmationModal) {
        confirmationModal.classList.remove('show');
    }
}

/**
 * Show the specified view and hide others
 * @param {string} viewName - The name of the view to show
 */
function showView(viewName) {
    currentView = viewName;
    
    const classesView = document.getElementById('classes-view');
    const classDetailView = document.getElementById('class-detail-view');
    const studentSelectionView = document.getElementById('student-selection-view');
    
    if (classesView && classDetailView && studentSelectionView) {
        classesView.classList.add('d-none');
        classDetailView.classList.add('d-none');
        studentSelectionView.classList.add('d-none');
        
        switch (viewName) {
            case 'classes':
                classesView.classList.remove('d-none');
                break;
            case 'class-detail':
                classDetailView.classList.remove('d-none');
                break;
            case 'student-selection':
                studentSelectionView.classList.remove('d-none');
                break;
        }
    }
}