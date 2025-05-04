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

    // Application state
    const state = {
        classes: [],
        students: [],
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
            // View class button
            const viewClass = e.target.closest('.view-class');
            if (viewClass) {
                const classId = parseInt(viewClass.dataset.classId);
                showClassDetailView(classId);
            }
            
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
            await Promise.all([
                fetchClasses(),
                fetchStudents()
            ]);
            renderClassesTable();
            addEventListeners();
            showClassesView();
        } catch (error) {
            console.error('Initialization error:', error);
            showAlert('Failed to load data. Please try again.', 'danger');
        }
    }

    // Fetch classes from the API
    async function fetchClasses() {
        try {
            const response = await fetch('/classes/api/list');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            state.classes = data;
            return data;
        } catch (error) {
            console.error('Error fetching classes:', error);
            throw error;
        }
    }

    // Fetch students from the API
    async function fetchStudents() {
        try {
            const response = await fetch('/students/api/list');
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            const data = await response.json();
            state.students = data;
            return data;
        } catch (error) {
            console.error('Error fetching students:', error);
            throw error;
        }
    }

    // Show Classes View
    function showClassesView() {
        hideAllViews();
        elements.classesView.classList.remove('d-none');
        state.currentClassId = null;
        renderClassesTable();
    }

    // Show Class Detail View
    async function showClassDetailView(classId) {
        state.currentClassId = classId;
        const classData = state.classes.find(c => c.id === classId);
        
        if (!classData) {
            showAlert('Class not found', 'danger');
            return showClassesView();
        }
        
        document.getElementById('class-detail-title').textContent = classData.description;
        
        // Get students enrolled in this class
        try {
            const response = await fetch(`/classes/api/${classId}/students`);
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            
            const students = await response.json();
            renderEnrolledStudents(students);
            
            hideAllViews();
            elements.classDetailView.classList.remove('d-none');
            
        } catch (error) {
            console.error('Error fetching enrolled students:', error);
            showAlert('Failed to load enrolled students', 'danger');
        }
    }

    // Show Student Selection View
    function showStudentSelectionView() {
        hideAllViews();
        elements.studentSelectionView.classList.remove('d-none');
        renderAvailableStudents();
    }

    // Hide all views
    function hideAllViews() {
        elements.classesView.classList.add('d-none');
        elements.classDetailView.classList.add('d-none');
        elements.studentSelectionView.classList.add('d-none');
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
            
            row.innerHTML = `
                <td>${classData.description}</td>
                <td>${classData.roomNumber}</td>
                <td>${classData.schedule}</td>
                <td>${classData.enrolledCount}</td>
                <td>${classData.instructorName}</td>
                <td>
                    <button class="action-btn view-class" data-class-id="${classData.id}" title="View Class">
                        <i class="fas fa-eye"></i>
                    </button>
                    <button class="action-btn edit-class" data-class-id="${classData.id}" title="Edit Class">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="action-btn delete-class" data-class-id="${classData.id}" title="Delete Class">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            
            elements.classesTableBody.appendChild(row);
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
        
        students.forEach(student => {
            const row = document.createElement('tr');
            
            row.innerHTML = `
                <td>${student.firstName} ${student.lastName}</td>
                <td>${student.id}</td>
                <td>${student.yearLevel}</td>
                <td>${student.phone}</td>
                <td>
                    <button class="btn btn-danger btn-sm unenroll-btn" data-student-id="${student.id}">
                        Unenroll
                    </button>
                </td>
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
        document.getElementById('classCode').value = classData.classCode;
        document.getElementById('description').value = classData.description;
        document.getElementById('roomNumber').value = classData.roomNumber;
        document.getElementById('schedule').value = classData.schedule;
        document.getElementById('instructorId').value = classData.instructorId;
        document.getElementById('classId').value = classData.id;
        
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
                    // Update in state
                    const index = state.classes.findIndex(c => c.id === parseInt(formData.get('classId')));
                    if (index !== -1) {
                        state.classes[index] = {
                            ...state.classes[index],
                            ...classData
                        };
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
                showClassDetailView(classId);
                
                showAlert('Student unenrolled successfully', 'success');
            } else {
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
