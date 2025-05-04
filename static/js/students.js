/**
 * Student Management System
 * Handles CRUD operations for student data
 */
document.addEventListener('DOMContentLoaded', () => {
    // DOM element references
    const elements = {
        // Tables and counters
        studentsTableBody: document.getElementById('studentsTableBody'),
        studentCounter: document.getElementById('studentCounter'),
        // Search and filter
        searchInput: document.getElementById('searchInput'),
        searchBtn: document.getElementById('searchBtn'),
        sortYearLevel: document.getElementById('sortYearLevel'),
        // Buttons
        btnEnrollStudent: document.getElementById('btnEnrollStudent'),
        // Modals
        enrollModal: document.getElementById('enrollModal'),
        picturesModal: document.getElementById('picturesModal'),
        editModal: document.getElementById('editModal'),
        editPicturesModal: document.getElementById('editPicturesModal'),
        confirmationModal: document.getElementById('confirmationModal'),
        // Modal close buttons
        closeEnrollModal: document.getElementById('closeEnrollModal'),
        closePicturesModal: document.getElementById('closePicturesModal'),
        closeEditModal: document.getElementById('closeEditModal'),
        closeEditPicturesModal: document.getElementById('closeEditPicturesModal'),
        // Modal confirmation buttons
        confirmYesBtn: document.getElementById('confirmYesBtn'),
        confirmNoBtn: document.getElementById('confirmNoBtn'),
        // Forms
        enrollStudentForm: document.getElementById('enrollStudentForm'),
        editStudentForm: document.getElementById('editStudentForm'),
        // Picture management
        uploadPicturesBtn: document.getElementById('uploadPicturesBtn'),
        editUploadPicturesBtn: document.getElementById('editUploadPicturesBtn'),
        picturesPreview: document.getElementById('picturesPreview'),
        editPicturesPreview: document.getElementById('editPicturesPreview'),
        savePicturesBtn: document.getElementById('savePicturesBtn'),
        saveEditPicturesBtn: document.getElementById('saveEditPicturesBtn')
    };

    // Application state
    const state = {
        students: [],
        filteredStudents: [],
        currentStudentId: null,
        uploadedPictures: [],
        editUploadedPictures: []
    };

    // Initialize the application
    init();

    // Add event listeners
    function addEventListeners() {
        // Open enroll student modal
        if (elements.btnEnrollStudent) {
            elements.btnEnrollStudent.addEventListener('click', () => {
                showModal(elements.enrollModal);
            });
        }

        // Close modals
        if (elements.closeEnrollModal) {
            elements.closeEnrollModal.addEventListener('click', () => {
                hideModal(elements.enrollModal);
            });
        }
        if (elements.closePicturesModal) {
            elements.closePicturesModal.addEventListener('click', () => {
                hideModal(elements.picturesModal);
            });
        }
        if (elements.closeEditModal) {
            elements.closeEditModal.addEventListener('click', () => {
                hideModal(elements.editModal);
            });
        }
        if (elements.closeEditPicturesModal) {
            elements.closeEditPicturesModal.addEventListener('click', () => {
                hideModal(elements.editPicturesModal);
            });
        }

        // Form submissions
        if (elements.enrollStudentForm) {
            elements.enrollStudentForm.addEventListener('submit', handleEnrollStudent);
        }
        if (elements.editStudentForm) {
            elements.editStudentForm.addEventListener('submit', handleEditStudent);
        }

        // Search functionality
        if (elements.searchBtn) {
            elements.searchBtn.addEventListener('click', performSearch);
        }
        if (elements.searchInput) {
            elements.searchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    performSearch();
                }
            });
        }

        // Sort by year level
        if (elements.sortYearLevel) {
            elements.sortYearLevel.addEventListener('click', sortByYearLevel);
        }

        // Confirmation modal handlers
        if (elements.confirmYesBtn) {
            elements.confirmYesBtn.addEventListener('click', confirmDeleteStudent);
        }
        if (elements.confirmNoBtn) {
            elements.confirmNoBtn.addEventListener('click', () => {
                hideModal(elements.confirmationModal);
            });
        }

        // Table click delegation for actions
        if (elements.studentsTableBody) {
            elements.studentsTableBody.addEventListener('click', handleTableActions);
        }

        // Generate Student ID
        document.getElementById('generateIdBtn')?.addEventListener('click', generateStudentId);
    }

    // Initialize the application
    async function init() {
        try {
            await fetchStudents();
            renderStudentsTable(state.students);
            updateStudentCounter();
            addEventListeners();
        } catch (error) {
            console.error('Initialization error:', error);
            showAlert('Failed to load students. Please try again.', 'danger');
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
            state.filteredStudents = [...data];
            return data;
        } catch (error) {
            console.error('Error fetching students:', error);
            throw error;
        }
    }

    // Render the students table
    function renderStudentsTable(students) {
        if (!elements.studentsTableBody) return;
        
        elements.studentsTableBody.innerHTML = '';
        
        if (students.length === 0) {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td colspan="5" class="text-center">No students found</td>
            `;
            elements.studentsTableBody.appendChild(row);
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
                    <button class="action-btn btn-edit" data-student-id="${student.id}" title="Edit Student">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button class="action-btn btn-delete" data-student-id="${student.id}" title="Delete Student">
                        <i class="fas fa-trash"></i>
                    </button>
                </td>
            `;
            
            elements.studentsTableBody.appendChild(row);
        });
    }

    // Handle table actions (edit, delete)
    function handleTableActions(e) {
        const editBtn = e.target.closest('.btn-edit');
        const deleteBtn = e.target.closest('.btn-delete');
        
        if (editBtn) {
            const studentId = editBtn.dataset.studentId;
            openEditModal(studentId);
        } else if (deleteBtn) {
            const studentId = deleteBtn.dataset.studentId;
            openDeleteConfirmation(studentId);
        }
    }

    // Open the edit modal for a student
    function openEditModal(studentId) {
        const student = state.students.find(s => s.id === studentId);
        if (!student) return;
        
        state.currentStudentId = studentId;
        
        // Populate the edit form
        document.getElementById('editFirstName').value = student.firstName;
        document.getElementById('editLastName').value = student.lastName;
        document.getElementById('editStudentId').value = student.id;
        document.getElementById('editYearLevel').value = student.yearLevel;
        document.getElementById('editPhone').value = student.phone;
        document.getElementById('editEmail').value = student.email || '';
        
        showModal(elements.editModal);
    }

    // Open delete confirmation modal
    function openDeleteConfirmation(studentId) {
        const student = state.students.find(s => s.id === studentId);
        if (!student) return;
        
        state.currentStudentId = studentId;
        
        const confirmationText = document.getElementById('confirmationText');
        if (confirmationText) {
            confirmationText.textContent = `Are you sure you want to delete ${student.firstName} ${student.lastName}?`;
        }
        
        showModal(elements.confirmationModal);
    }

    // Confirm delete student
    async function confirmDeleteStudent() {
        if (!state.currentStudentId) return;
        
        try {
            const response = await fetch(`/students/api/delete/${state.currentStudentId}`, {
                method: 'DELETE'
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Remove from the state
                state.students = state.students.filter(s => s.id !== state.currentStudentId);
                state.filteredStudents = state.filteredStudents.filter(s => s.id !== state.currentStudentId);
                
                // Update the UI
                renderStudentsTable(state.filteredStudents);
                updateStudentCounter();
                
                showAlert('Student deleted successfully', 'success');
            } else {
                showAlert(data.message || 'Failed to delete student', 'danger');
            }
            
            hideModal(elements.confirmationModal);
            state.currentStudentId = null;
            
        } catch (error) {
            console.error('Error deleting student:', error);
            showAlert('An error occurred while deleting the student', 'danger');
            hideModal(elements.confirmationModal);
        }
    }

    // Handle enroll student form submission
    async function handleEnrollStudent(e) {
        e.preventDefault();
        
        const form = e.target;
        const formData = new FormData(form);
        
        const student = {
            firstName: formData.get('firstName'),
            lastName: formData.get('lastName'),
            id: formData.get('studentId'),
            yearLevel: formData.get('yearLevel'),
            phone: formData.get('phone'),
            email: formData.get('email') || ''
        };
        
        try {
            const response = await fetch('/students/api/create', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(student)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Add to state
                state.students.push(data.student);
                state.filteredStudents.push(data.student);
                
                // Update UI
                renderStudentsTable(state.filteredStudents);
                updateStudentCounter();
                
                // Reset form and close modal
                form.reset();
                hideModal(elements.enrollModal);
                
                showAlert('Student enrolled successfully', 'success');
            } else {
                showAlert(data.message || 'Failed to enroll student', 'danger');
            }
            
        } catch (error) {
            console.error('Error enrolling student:', error);
            showAlert('An error occurred while enrolling the student', 'danger');
        }
    }

    // Handle edit student form submission
    async function handleEditStudent(e) {
        e.preventDefault();
        
        if (!state.currentStudentId) return;
        
        const form = e.target;
        const formData = new FormData(form);
        
        const updatedStudent = {
            firstName: formData.get('firstName'),
            lastName: formData.get('lastName'),
            yearLevel: formData.get('yearLevel'),
            phone: formData.get('phone'),
            email: formData.get('email') || ''
        };
        
        try {
            const response = await fetch(`/students/api/update/${state.currentStudentId}`, {
                method: 'PUT',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(updatedStudent)
            });
            
            const data = await response.json();
            
            if (data.success) {
                // Update in state
                const index = state.students.findIndex(s => s.id === state.currentStudentId);
                if (index !== -1) {
                    state.students[index] = {
                        ...state.students[index],
                        ...updatedStudent
                    };
                }
                
                const filteredIndex = state.filteredStudents.findIndex(s => s.id === state.currentStudentId);
                if (filteredIndex !== -1) {
                    state.filteredStudents[filteredIndex] = {
                        ...state.filteredStudents[filteredIndex],
                        ...updatedStudent
                    };
                }
                
                // Update UI
                renderStudentsTable(state.filteredStudents);
                
                // Close modal
                hideModal(elements.editModal);
                state.currentStudentId = null;
                
                showAlert('Student updated successfully', 'success');
            } else {
                showAlert(data.message || 'Failed to update student', 'danger');
            }
            
        } catch (error) {
            console.error('Error updating student:', error);
            showAlert('An error occurred while updating the student', 'danger');
        }
    }

    // Perform search
    function performSearch() {
        if (!elements.searchInput) return;
        
        const searchTerm = elements.searchInput.value.toLowerCase().trim();
        
        if (searchTerm === '') {
            state.filteredStudents = [...state.students];
        } else {
            state.filteredStudents = state.students.filter(student => 
                student.firstName.toLowerCase().includes(searchTerm) || 
                student.lastName.toLowerCase().includes(searchTerm) ||
                student.id.toLowerCase().includes(searchTerm) ||
                student.yearLevel.toLowerCase().includes(searchTerm) ||
                student.phone.includes(searchTerm)
            );
        }
        
        renderStudentsTable(state.filteredStudents);
        updateStudentCounter();
    }

    // Sort by year level
    function sortByYearLevel() {
        const yearLevelOrder = {
            '1st Year': 1,
            '2nd Year': 2,
            '3rd Year': 3,
            '4th Year': 4
        };
        
        state.filteredStudents.sort((a, b) => yearLevelOrder[a.yearLevel] - yearLevelOrder[b.yearLevel]);
        renderStudentsTable(state.filteredStudents);
    }

    // Update student counter
    function updateStudentCounter() {
        if (elements.studentCounter) {
            elements.studentCounter.textContent = state.filteredStudents.length;
        }
    }

    // Generate a new student ID
    async function generateStudentId() {
        try {
            const response = await fetch('/students/api/generate-id');
            const data = await response.json();
            
            if (data.success) {
                document.getElementById('studentId').value = data.id;
            }
        } catch (error) {
            console.error('Error generating student ID:', error);
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
