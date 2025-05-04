/**
 * Class Management System
 * Handles CRUD operations for classes and student enrollment
 */
document.addEventListener('DOMContentLoaded', () => {
    // DOM element references
    const elements = {
        // Views
        classesView: document.getElementById('classes-view'),
        classDetailView: document.getElementById('class-detail-view'),
        studentSelectionView: document.getElementById('student-selection-view'),
        // Navigation buttons
        backToClasses: document.getElementById('back-to-classes'),
        backToClassDetail: document.getElementById('back-to-class-detail'),
        enrollStudentBtn: document.getElementById('enroll-student-btn'),
        // Tables
        classesTableBody: document.getElementById('classes-table-body'),
        enrolledStudentsList: document.getElementById('enrolled-students-list'),
        allStudentsList: document.getElementById('all-students-list'),
        // Class form elements
        addClassBtn: document.getElementById('add-class-btn'),
        classModal: document.getElementById('class-modal'),
        closeClassModal: document.getElementById('close-class-modal'),
        classForm: document.getElementById('class-form'),
        classTitle: document.getElementById('class-modal-title'),
        // Confirmation modal
        confirmationModal: document.getElementById('confirmation-modal'),
        confirmationText: document.getElementById('confirmation-text'),
        confirmYes: document.getElementById('confirm-yes'),
        confirmNo: document.getElementById('confirm-no')
    };
    
    // Log DOM elements to help debug
    console.log('DOM Elements:', {
        classesTableBody: elements.classesTableBody,
        classesView: elements.classesView,
        addClassBtn: elements.addClassBtn
    });

    // Application state
    const state = {
        classes: [],
        students: [],
        courses: [],
        currentClassId: null,
        studentToUnenroll: null,
        isEditingClass: false
    };

    // Initialize the application
    init();

    // Add event listeners
    function addEventListeners() {
        // Navigation
        if (elements.backToClasses) {
            elements.backToClasses.addEventListener('click', showClassesView);
        }
        if (elements.backToClassDetail) {
            elements.backToClassDetail.addEventListener('click', () => {
                showClassDetailView(state.currentClassId);
            });
        }
        if (elements.enrollStudentBtn) {
            elements.enrollStudentBtn.addEventListener('click', showStudentSelectionView);
        }

        // Class modal
        if (elements.addClassBtn) {
            elements.addClassBtn.addEventListener('click', () => {
                state.isEditingClass = false;
                elements.classTitle.textContent = 'Add New Class';
                elements.classForm.reset();
                showModal(elements.classModal);
            });
        }
        if (elements.closeClassModal) {
            elements.closeClassModal.addEventListener('click', () => {
                hideModal(elements.classModal);
            });
        }
        if (elements.classForm) {
            elements.classForm.addEventListener('submit', handleClassFormSubmit);
        }

        // Confirmation modal
        if (elements.confirmYes) {
            elements.confirmYes.addEventListener('click', handleConfirmUnenroll);
        }
        if (elements.confirmNo) {
            elements.confirmNo.addEventListener('click', () => {
                hideModal(elements.confirmationModal);
                state.studentToUnenroll = null;
            });
        }

        // Table click delegation
        document.addEventListener('click', function(e) {
            // Edit class button
            const editClass = e.target.closest('.edit-class');
            if (editClass) {
                const classId = parseInt(editClass.dataset.classId);
                openEditClassModal(classId);
            }
            
            // Delete class button
            const deleteClass = e.target.closest('.delete-class');
            if (deleteClass) {
                const classId = parseInt(deleteClass.dataset.classId);
                openDeleteClassConfirmation(classId);
            }
            
            // Unenroll button
            const unenrollBtn = e.target.closest('.unenroll-btn');
            if (unenrollBtn) {
                state.studentToUnenroll = {
                    classId: state.currentClassId,
                    studentId: unenrollBtn.dataset.studentId
                };
                elements.confirmationText.textContent = 'Are you sure you want to unenroll this student?';
                showModal(elements.confirmationModal);
            }
            
            // Enroll button in student selection view
            const enrollBtn = e.target.closest('.enroll-btn');
            if (enrollBtn) {
                enrollStudent(enrollBtn.dataset.studentId);
            }
        });
    }

    // Initialize the application
    async function init() {
        try {
            // Try to fetch each resource separately to identify which one is failing
            let errorMessages = [];
            let fetchSuccess = true;
            
            try {
                await fetchClasses();
            } catch (e) {
                console.error('Error fetching classes:', e);
                errorMessages.push('classes');
                fetchSuccess = false;
                // Default to empty array to allow UI to render
                state.classes = [];
            }
            
            try {
                await fetchStudents();
            } catch (e) {
                console.error('Error fetching students:', e);
                errorMessages.push('students');
                fetchSuccess = false;
                // Default to empty array to allow UI to render
                state.students = [];
            }
            
            try {
                await fetchCourses();
            } catch (e) {
                console.error('Error fetching courses:', e);
                errorMessages.push('courses');
                fetchSuccess = false;
                // Default to empty array to allow UI to render
                state.courses = [];
            }
            
            // Even if some fetches failed, continue with what we have
            renderClassesTable();
            addEventListeners();
            showClassesView();
            
            // Show specific error message if any fetch failed
            if (!fetchSuccess) {
                let errorMessage = 'Failed to load ' + errorMessages.join(', ') + '. ';
                errorMessage += 'Some data may be missing. Please refresh the page to try again.';
                showAlert(errorMessage, 'warning');
            }
        } catch (error) {
            console.error('Initialization error:', error);
            showAlert('Failed to load data. Please try again by refreshing the page.', 'danger');
            
            // Display helpful debug info on the page
            if (elements.classesTableBody) {
                elements.classesTableBody.innerHTML = `
                    <tr>
                        <td colspan="6" class="text-center">
                            <div class="alert alert-danger mb-0">
                                <p>Failed to load data. Please try refreshing the page.</p>
                                <p><small>Error details: ${error.message || 'Unknown error'}</small></p>
                            </div>
                        </td>
                    </tr>
                `;
            }
        }
    }
    
    // Fetch courses from the API
    async function fetchCourses() {
        try {
            console.log('Fetching courses from API...');
            const response = await fetch('/courses/api/list');
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error(`HTTP error! status: ${response.status}, response: ${errorText}`);
                throw new Error(`Server error: ${response.status} - ${errorText}`);
            }
            
            const data = await response.json();
            console.log(`Received ${data.length} courses from API`);
            
            // Check if the response is an error object
            if (data.error) {
                console.error('API returned error:', data.error);
                throw new Error(`API error: ${data.error}`);
            }
            
            state.courses = Array.isArray(data) ? data : [];
            populateCourseDropdown();
            return state.courses;
        } catch (error) {
            console.error('Error fetching courses:', error);
            
            // Display error in console with more details
            if (error.message) {
                console.error('Error message:', error.message);
            }
            
            // Reset the state to empty array to prevent null errors
            state.courses = [];
            
            throw error;
        }
    }
    
    // Populate the course dropdown
    function populateCourseDropdown() {
        const courseSelect = document.getElementById('course');
        if (!courseSelect) return;
        
        // Clear existing options except the first one
        while (courseSelect.options.length > 1) {
            courseSelect.remove(1);
        }
        
        // Add course options
        state.courses.forEach(course => {
            const option = document.createElement('option');
            option.value = JSON.stringify({code: course.code, description: course.description});
            option.textContent = `${course.code}: ${course.description}`;
            courseSelect.appendChild(option);
        });
        
        // Add event listener to handle course selection
        courseSelect.addEventListener('change', handleCourseSelection);
    }
    
    // Handle course selection
    function handleCourseSelection(e) {
        const selectedValue = e.target.value;
        if (!selectedValue) {
            // Reset fields if no course is selected
            document.getElementById('classCode').value = '';
            document.getElementById('description').value = '';
            return;
        }
        
        try {
            const courseData = JSON.parse(selectedValue);
            
            // Set the hidden description field
            document.getElementById('description').value = courseData.description;
            
            // Generate a suggestion for class code if it's not already set or is the default course code
            const classCodeInput = document.getElementById('classCode');
            const currentClassCode = classCodeInput.value;
            
            // Only suggest a code if field is empty or matches previous course code
            if (!currentClassCode || currentClassCode === state.lastSelectedCourseCode) {
                // If editing, don't change the class code unless it matches the previous suggestion
                if (!state.isEditingClass) {
                    // Generate a suggested class code
                    const existingCodes = state.classes
                        .filter(c => (c.class_code || c.classCode || '').startsWith(courseData.code))
                        .map(c => c.class_code || c.classCode || '');
                    
                    if (existingCodes.length === 0) {
                        // First section with this course code
                        classCodeInput.value = courseData.code;
                    } else {
                        // Find the next available section letter (A, B, C, etc.)
                        let sectionLetter = 'A';
                        while (existingCodes.includes(`${courseData.code}-${sectionLetter}`)) {
                            sectionLetter = String.fromCharCode(sectionLetter.charCodeAt(0) + 1);
                        }
                        classCodeInput.value = `${courseData.code}-${sectionLetter}`;
                    }
                }
            }
            
            // Store the last selected course code for comparison
            state.lastSelectedCourseCode = courseData.code;
            
        } catch (error) {
            console.error('Error parsing course data:', error);
        }
    }

    // Fetch classes from the API
    async function fetchClasses() {
        try {
            console.log('Fetching classes from API...');
            const response = await fetch('/classes/api/list');
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error(`HTTP error! status: ${response.status}, response: ${errorText}`);
                throw new Error(`Server error: ${response.status} - ${errorText}`);
            }
            
            const data = await response.json();
            console.log(`Received ${data.length} classes from API`);
            
            // Check if the response is an error object
            if (data.error) {
                console.error('API returned error:', data.error);
                throw new Error(`API error: ${data.error}`);
            }
            
            state.classes = Array.isArray(data) ? data : [];
            return state.classes;
        } catch (error) {
            console.error('Error fetching classes:', error);
            
            // Display error in console with more details
            if (error.message) {
                console.error('Error message:', error.message);
            }
            
            // Reset the state to empty array to prevent null errors
            state.classes = [];
            
            throw error;
        }
    }

    // Fetch students from the API
    async function fetchStudents() {
        try {
            console.log('Fetching students from API...');
            const response = await fetch('/students/api/list');
            
            if (!response.ok) {
                const errorText = await response.text();
                console.error(`HTTP error! status: ${response.status}, response: ${errorText}`);
                throw new Error(`Server error: ${response.status} - ${errorText}`);
            }
            
            const data = await response.json();
            console.log(`Received ${data.length} students from API`);
            
            // Check if the response is an error object
            if (data.error) {
                console.error('API returned error:', data.error);
                throw new Error(`API error: ${data.error}`);
            }
            
            state.students = Array.isArray(data) ? data : [];
            return state.students;
        } catch (error) {
            console.error('Error fetching students:', error);
            
            // Display error in console with more details
            if (error.message) {
                console.error('Error message:', error.message);
            }
            
            // Reset the state to empty array to prevent null errors
            state.students = [];
            
            throw error;
        }
    }

    // Show Classes View
    function showClassesView() {
        hideAllViews();
        if (elements.classesView) {
            elements.classesView.classList.remove('d-none');
            state.currentClassId = null;
            renderClassesTable();
        } else {
            console.error('Classes view element not found');
        }
    }

    // Show Class Detail View
    async function showClassDetailView(classId) {
        state.currentClassId = classId;
        const classData = state.classes.find(c => c.id === classId);
        
        if (!classData) {
            showAlert('Class not found', 'danger');
            return showClassesView();
        }
        
        const titleElement = document.getElementById('class-detail-title');
        if (titleElement) {
            titleElement.textContent = classData.description;
        }
        
        // Get students enrolled in this class
        try {
            const response = await fetch(`/classes/api/${classId}/students`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const students = await response.json();
            renderEnrolledStudents(students);
            
            hideAllViews();
            if (elements.classDetailView) {
                elements.classDetailView.classList.remove('d-none');
            } else {
                console.error('Class detail view element not found');
                showAlert('Error displaying class details', 'danger');
            }
            
        } catch (error) {
            console.error('Error fetching enrolled students:', error);
            showAlert('Failed to load enrolled students', 'danger');
        }
    }

    // Show Student Selection View
    function showStudentSelectionView() {
        hideAllViews();
        if (elements.studentSelectionView) {
            elements.studentSelectionView.classList.remove('d-none');
            renderAvailableStudents();
        } else {
            console.error('Student selection view element not found');
            showAlert('Error displaying student selection', 'danger');
        }
    }

    // Hide all views
    function hideAllViews() {
        if (elements.classesView) elements.classesView.classList.add('d-none');
        if (elements.classDetailView) elements.classDetailView.classList.add('d-none');
        if (elements.studentSelectionView) elements.studentSelectionView.classList.add('d-none');
    }

    // Render the classes table
    function renderClassesTable() {
        if (!elements.classesTableBody) return;
        
        elements.classesTableBody.innerHTML = '';
        
        if (state.classes.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td colspan="6" class="text-center">No classes found</td>
            `;
            elements.classesTableBody.appendChild(row);
            return;
        }
        
        state.classes.forEach(classData => {
            const row = document.createElement('tr');
            
            // Store the class ID in dataset for reference
            row.dataset.classId = classData.id;
            
            row.innerHTML = `
                <td>${classData.class_code || classData.classCode}</td>
                <td>${classData.description}</td>
                <td>${classData.roomNumber}</td>
                <td>${classData.schedule}</td>
                <td>${classData.enrolledCount}</td>
                <td>${classData.instructorName}</td>
                <td>
                    <button class="action-btn edit-class" data-class-id="${classData.id}" title="Edit Class">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="action-btn delete-class" data-class-id="${classData.id}" title="Delete Class">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            
            elements.classesTableBody.appendChild(row);
            
            // Add click event to the row only for instructors
            const isInstructor = document.querySelector('.user-role')?.textContent.trim().toLowerCase() === 'instructor';
            if (isInstructor) {
                row.addEventListener('click', function(e) {
                    // If the click was on an action button, don't navigate to details
                    if (e.target.closest('.action-btn')) return;
                    
                    showClassDetailView(parseInt(this.dataset.classId));
                });
                // Add clickable class to show it's interactive
                row.classList.add('clickable-row');
            }
        });
    }

    // Render enrolled students
    function renderEnrolledStudents(students) {
        if (!elements.enrolledStudentsList) return;
        
        elements.enrolledStudentsList.innerHTML = '';
        
        if (students.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td colspan="5" class="text-center">No students enrolled</td>
            `;
            elements.enrolledStudentsList.appendChild(row);
            return;
        }
        
        // Get current user role from the page
        const isInstructor = document.querySelector('.user-role')?.textContent.trim().toLowerCase() === 'instructor';
        
        students.forEach(student => {
            const row = document.createElement('tr');
            
            // Only show unenroll button for instructors
            const actionColumn = isInstructor ? `
                <td>
                    <button class="btn btn-danger btn-sm unenroll-btn" data-student-id="${student.id}">
                        Unenroll
                    </button>
                </td>
            ` : '<td>-</td>';
            
            row.innerHTML = `
                <td>${student.firstName} ${student.lastName}</td>
                <td>${student.id}</td>
                <td>${student.yearLevel}</td>
                <td>${student.phone}</td>
                ${actionColumn}
            `;
            
            elements.enrolledStudentsList.appendChild(row);
        });
    }

    // Render available students for enrollment
    function renderAvailableStudents() {
        if (!elements.allStudentsList || !state.currentClassId) return;
        
        elements.allStudentsList.innerHTML = '';
        
        // Get students already enrolled in this class
        const enrolledStudentIds = new Set();
        
        // Fetch enrolled students for this class
        fetch(`/classes/api/${state.currentClassId}/students`)
            .then(response => response.json())
            .then(enrolledStudents => {
                // Create a set of enrolled student IDs
                enrolledStudents.forEach(student => {
                    enrolledStudentIds.add(student.id);
                });
                
                // Render all students, disabling the already enrolled ones
                state.students.forEach(student => {
                    const isEnrolled = enrolledStudentIds.has(student.id);
                    
                    const row = document.createElement('tr');
                    row.innerHTML = `
                        <td>${student.firstName} ${student.lastName}</td>
                        <td>${student.id}</td>
                        <td>${student.yearLevel}</td>
                        <td>${student.phone}</td>
                        <td>
                            ${isEnrolled ? 
                                '<button class="btn btn-secondary btn-sm" disabled>Enrolled</button>' :
                                `<button class="btn btn-success btn-sm enroll-btn" data-student-id="${student.id}">Enroll</button>`
                            }
                        </td>
                    `;
                    
                    elements.allStudentsList.appendChild(row);
                });
            })
            .catch(error => {
                console.error('Error fetching enrolled students:', error);
                showAlert('Failed to load student enrollment data', 'danger');
            });
    }

    // Open edit class modal
    function openEditClassModal(classId) {
        const classData = state.classes.find(c => c.id === classId);
        if (!classData) return;
        
        // Set form fields
        document.getElementById('classCode').value = classData.class_code || classData.classCode; // Handle different property names
        document.getElementById('description').value = classData.description;
        document.getElementById('roomNumber').value = classData.roomNumber;
        document.getElementById('schedule').value = classData.schedule;
        document.getElementById('instructorId').value = classData.instructorId;
        document.getElementById('classId').value = classData.id;
        
        // Set editing state flag to true
        state.isEditingClass = true;
        
        // Set up schedule builder with existing schedule
        if (window.setupScheduleBuilder && typeof window.setupScheduleBuilder === 'function') {
            window.setupScheduleBuilder(classData.schedule);
        }
        
        // Set course dropdown
        const courseSelect = document.getElementById('course');
        if (courseSelect) {
            // Try to find the matching course
            let found = false;
            for (let i = 0; i < courseSelect.options.length; i++) {
                const option = courseSelect.options[i];
                if (!option.value) continue;
                
                try {
                    const courseData = JSON.parse(option.value);
                    // Extract the base course code from the class code
                    const classCode = classData.class_code || classData.classCode;
                    // If class code is something like "ITP321-A", we just need "ITP321" 
                    const baseCourseCode = classCode.split('-')[0];
                    
                    if (courseData.code === baseCourseCode) {
                        courseSelect.selectedIndex = i;
                        found = true;
                        break;
                    }
                } catch (error) {
                    console.error('Error parsing course option:', error);
                }
            }
            
            // If no matching course found, reset to first option
            if (!found) {
                courseSelect.selectedIndex = 0;
            }
        }
        
        // Set state and modal title
        state.isEditingClass = true;
        elements.classTitle.textContent = 'Edit Class';
        
        // Show modal
        showModal(elements.classModal);
    }

    // Open delete class confirmation
    function openDeleteClassConfirmation(classId) {
        const classData = state.classes.find(c => c.id === classId);
        if (!classData) return;
        
        state.currentClassId = classId;
        
        elements.confirmationText.textContent = `Are you sure you want to delete class "${classData.description}"?`;
        
        // Set up handler for confirmation
        const originalHandler = elements.confirmYes.onclick;
        elements.confirmYes.onclick = async () => {
            try {
                const response = await fetch(`/classes/api/delete/${classId}`, {
                    method: 'DELETE'
                });
                
                const data = await response.json();
                
                if (data.success) {
                    // Remove from state
                    state.classes = state.classes.filter(c => c.id !== classId);
                    
                    // Update UI
                    renderClassesTable();
                    
                    showAlert('Class deleted successfully', 'success');
                } else {
                    showAlert(data.message || 'Failed to delete class', 'danger');
                }
                
            } catch (error) {
                console.error('Error deleting class:', error);
                showAlert('An error occurred while deleting the class', 'danger');
            }
            
            // Reset handler and hide modal
            elements.confirmYes.onclick = originalHandler;
            hideModal(elements.confirmationModal);
        };
        
        // Show confirmation modal
        showModal(elements.confirmationModal);
    }

    // Handle class form submission
    async function handleClassFormSubmit(e) {
        e.preventDefault();
        
        const form = e.target;
        const formData = new FormData(form);
        
        const classData = {
            classCode: formData.get('classCode'),
            description: formData.get('description'),
            roomNumber: formData.get('roomNumber'),
            schedule: formData.get('schedule'),
            instructorId: parseInt(formData.get('instructorId'))
        };
        
        try {
            let response;
            
            if (state.isEditingClass) {
                // Update existing class
                const classId = formData.get('classId');
                response = await fetch(`/classes/api/update/${classId}`, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(classData)
                });
            } else {
                // Create new class
                response = await fetch('/classes/api/create', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify(classData)
                });
            }
            
            const data = await response.json();
            
            if (data.success) {
                if (state.isEditingClass) {
                    // Update in state with complete class data from server
                    const index = state.classes.findIndex(c => c.id === parseInt(formData.get('classId')));
                    if (index !== -1) {
                        if (data.class) {
                            // Use complete class data from server if available
                            state.classes[index] = data.class;
                        } else {
                            // Fallback to just updating fields from form
                            state.classes[index] = {
                                ...state.classes[index],
                                ...classData
                            };
                            
                            // Update instructor name by getting the selected option text
                            const instructorSelect = document.getElementById('instructorId');
                            if (instructorSelect && instructorSelect.selectedIndex >= 0) {
                                const selectedOption = instructorSelect.options[instructorSelect.selectedIndex];
                                state.classes[index].instructorName = selectedOption.text;
                            }
                        }
                    }
                    
                    showAlert('Class updated successfully', 'success');
                } else {
                    // Add to state
                    state.classes.push(data.class);
                    
                    showAlert('Class created successfully', 'success');
                }
                
                // Update UI and close modal
                renderClassesTable();
                hideModal(elements.classModal);
                form.reset();
                
            } else {
                showAlert(data.message || 'Failed to save class', 'danger');
            }
            
        } catch (error) {
            console.error('Error saving class:', error);
            showAlert('An error occurred while saving the class', 'danger');
        }
    }

    // Handle confirm unenroll
    async function handleConfirmUnenroll() {
        if (!state.studentToUnenroll) return;
        
        try {
            const { classId, studentId } = state.studentToUnenroll;
            
            const response = await fetch(`/classes/api/${classId}/unenroll/${studentId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Update UI by refreshing the class detail view
                showAlert('Student unenrolled successfully', 'success');
                
                // Refresh the enrolled students list
                const response = await fetch(`/classes/api/${classId}/students`);
                if (response.ok) {
                    const students = await response.json();
                    renderEnrolledStudents(students);
                }
            } else {
                // Just show the error message without refreshing the view
                showAlert(data.message || 'Failed to unenroll student', 'danger');
            }
            
        } catch (error) {
            console.error('Error unenrolling student:', error);
            showAlert('An error occurred while unenrolling the student', 'danger');
        }
        
        // Hide modal and reset state
        hideModal(elements.confirmationModal);
        state.studentToUnenroll = null;
    }

    // Enroll a student
    async function enrollStudent(studentId) {
        if (!state.currentClassId) return;
        
        try {
            const response = await fetch(`/classes/api/${state.currentClassId}/enroll`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ studentId })
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Update UI
                renderAvailableStudents();
                
                showAlert('Student enrolled successfully', 'success');
            } else {
                showAlert(data.message || 'Failed to enroll student', 'danger');
            }
            
        } catch (error) {
            console.error('Error enrolling student:', error);
            showAlert('An error occurred while enrolling the student', 'danger');
        }
    }

    // Show modal
    function showModal(modal) {
        if (!modal) return;
        
        modal.style.display = 'flex';
        // Force reflow
        void modal.offsetWidth;
        modal.classList.add('active');
        document.body.classList.add('modal-open');
    }

    // Hide modal
    function hideModal(modal) {
        if (!modal) return;
        
        modal.classList.remove('active');
        document.body.classList.remove('modal-open');
        
        // Wait for transition to finish
        const handleTransitionEnd = () => {
            if (!modal.classList.contains('active')) {
                modal.style.display = 'none';
            }
            modal.removeEventListener('transitionend', handleTransitionEnd);
        };
        
        modal.addEventListener('transitionend', handleTransitionEnd);
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
