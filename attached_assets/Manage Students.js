/**
 * Student Management System
 * Handles CRUD operations for student data with localStorage
 */
console.log("Student Management JS loaded!");

document.addEventListener('DOMContentLoaded', () => {
  // DOM element references - cached for performance
  const elements = {
    studentsTable: document.getElementById('students-table'),
    studentCount: document.getElementById('student-count'),
    searchInput: document.getElementById('searchInput'),
    yearLevelFilter: document.getElementById('yearLevelFilter'),
    logoutBtn: document.getElementById('logout-btn'),
    // Forms
    editStudentForm: document.getElementById('editStudentForm'),
    addStudentForm: document.getElementById('addStudentForm'),
    // Modals
    confirmationModal: document.getElementById('confirmationModal'),
    editStudentModal: document.getElementById('editStudentModal'),
    addStudentModal: document.getElementById('addStudentModal'),
    studentPicturesModal: document.getElementById('studentPicturesModal'),
    editPicturesModal: document.getElementById('editPicturesModal'),
    // Buttons
    btnAddStudent: document.getElementById('btnAddStudent'),
    btnConfirmYes: document.getElementById('btnConfirmYes'),
    btnConfirmNo: document.getElementById('btnConfirmNo'),
    closeEditModal: document.getElementById('closeEditModal'),
    closeAddModal: document.getElementById('closeAddModal'),
    closePicturesModal: document.getElementById('closePicturesModal'),
    closeEditPicturesModal: document.getElementById('closeEditPicturesModal'),
    btnUploadPictures: document.getElementById('btnUploadPictures'),
    btnChangePictures: document.getElementById('btnChangePictures'),
    btnSavePictures: document.getElementById('btnSavePictures'),
    btnSaveEditPictures: document.getElementById('btnSaveEditPictures'),
    // File input
    fileInput: document.getElementById('fileInput'),
    picturePreview: document.getElementById('picturePreview'),
    editPicturePreview: document.getElementById('editPicturePreview')
  };

  // State variables
  const state = {
    studentToDelete: null,
    newStudentData: null,
    uploadedPictures: [],
    currentEditingStudent: null,
    MAX_PICTURES: 6,
    MIN_PICTURES: 3
  };

  // Constants
  const STORAGE_KEYS = {
    STUDENTS: 'students',
    STUDENT_PICTURES: 'studentPictures'
  };

  // Initial data
  const initialStudents = [
    { id: '20-00001', firstName: 'Joker', lastName: 'Carantes', yearLevel: '1st Year', phone: '09123456789' },
    { id: '20-00002', firstName: 'Tristan', lastName: 'Tangilang', yearLevel: '1st Year', phone: '09123465765' },
    { id: '20-00003', firstName: 'Zoren', lastName: 'Okko', yearLevel: '2nd Year', phone: '09123456432' },
    { id: '20-00004', firstName: 'Amiel', lastName: 'Oliquiano', yearLevel: '2nd Year', phone: '09123443234' },
    { id: '20-00005', firstName: 'Chadli', lastName: 'Fanaang', yearLevel: '3rd Year', phone: '09123423123' }
  ];

  const dummyPictures = {
    default: [
      'https://placehold.co/100x100?text=Photo1',
      'https://placehold.co/100x100?text=Photo2',
      'https://placehold.co/100x100?text=Photo3'
    ]
  };

  /**
   * Storage Service - Handles all localStorage operations
   */
  const StorageService = {
    // Get data from localStorage with default fallback
    get(key, defaultValue = []) {
      try {
        const data = localStorage.getItem(key);
        return data ? JSON.parse(data) : defaultValue;
      } catch (error) {
        console.error(`Error getting ${key} from localStorage:`, error);
        return defaultValue;
      }
    },

    // Save data to localStorage
    save(key, data) {
      try {
        localStorage.setItem(key, JSON.stringify(data));
        return true;
      } catch (error) {
        console.error(`Error saving ${key} to localStorage:`, error);
        return false;
      }
    },

    // Initialize storage with default data if not already set
    init(key, defaultData) {
      if (!localStorage.getItem(key)) {
        this.save(key, defaultData);
      }
    }
  };

  /**
   * Student Service - Handles student CRUD operations
   */
  const StudentService = {
    getAll() {
      return StorageService.get(STORAGE_KEYS.STUDENTS);
    },

    getById(id) {
      return this.getAll().find(student => student.id === id);
    },

    create(student) {
      const students = this.getAll();
      students.push(student);
      return StorageService.save(STORAGE_KEYS.STUDENTS, students);
    },

    update(id, updatedData) {
      const students = this.getAll();
      const index = students.findIndex(student => student.id === id);
      
      if (index !== -1) {
        students[index] = { ...students[index], ...updatedData };
        return StorageService.save(STORAGE_KEYS.STUDENTS, students);
      }
      return false;
    },

    delete(id) {
      const students = this.getAll();
      const filteredStudents = students.filter(student => student.id !== id);
      return StorageService.save(STORAGE_KEYS.STUDENTS, filteredStudents);
    },

    search(term) {
      const students = this.getAll();
      const searchTerm = term.toLowerCase();
      
      return students.filter(student => 
        student.firstName.toLowerCase().includes(searchTerm) || 
        student.lastName.toLowerCase().includes(searchTerm) ||
        student.id.toLowerCase().includes(searchTerm)
      );
    },

    filterByYearLevel(yearLevel) {
      if (yearLevel === 'All') {
        return this.getAll();
      }
      
      return this.getAll().filter(student => student.yearLevel === yearLevel);
    },

    validateStudent(student) {
      // Basic validation for student data
      if (!student.firstName || !student.lastName || !student.id || !student.yearLevel || !student.phone) {
        return { valid: false, message: 'All fields are required' };
      }
      
      // ID format validation (optional)
      const idRegex = /^\d{2}-\d{5}$/;
      if (!idRegex.test(student.id)) {
        return { valid: false, message: 'ID should be in format: XX-XXXXX' };
      }
      
      // Phone number validation (optional)
      const phoneRegex = /^09\d{9}$/;
      if (!phoneRegex.test(student.phone)) {
        return { valid: false, message: 'Phone number should start with 09 and have 11 digits' };
      }
      
      return { valid: true };
    }
  };

  /**
   * Picture Service - Handles student pictures
   */
  const PictureService = {
    getForStudent(studentId) {
      const picturesData = StorageService.get(STORAGE_KEYS.STUDENT_PICTURES, {});
      return picturesData[studentId] || picturesData.default || [];
    },

    saveForStudent(studentId, pictures) {
      const picturesData = StorageService.get(STORAGE_KEYS.STUDENT_PICTURES, {});
      picturesData[studentId] = pictures;
      return StorageService.save(STORAGE_KEYS.STUDENT_PICTURES, picturesData);
    },

    removeForStudent(studentId) {
      const picturesData = StorageService.get(STORAGE_KEYS.STUDENT_PICTURES, {});
      delete picturesData[studentId];
      return StorageService.save(STORAGE_KEYS.STUDENT_PICTURES, picturesData);
    }
  };

  /**
   * UI Service - Handles UI-related operations
   */
  const UIService = {
    // Modal functions
    showModal(modal) {
      if (!modal) return;
      
      modal.style.display = 'flex';
      // Force reflow to ensure the transition happens
      void modal.offsetWidth;
      modal.classList.add('active');
      document.body.classList.add('modal-open');
    },

    hideModal(modal) {
      if (!modal) return;
      
      modal.classList.remove('active');
      document.body.classList.remove('modal-open');
      
      // Wait for the transition to finish before hiding completely
      const handleTransitionEnd = () => {
        if (!modal.classList.contains('active')) {
          modal.style.display = 'none';
        }
        modal.removeEventListener('transitionend', handleTransitionEnd);
      };
      
      modal.addEventListener('transitionend', handleTransitionEnd);
    },

    // Table functions
    renderStudentsTable(students) {
      if (!elements.studentsTable || !elements.studentCount) return;
      
      elements.studentsTable.innerHTML = '';
      elements.studentCount.textContent = students.length;

      students.forEach(student => {
        const row = document.createElement('tr');
        row.setAttribute('data-id', student.id);
        
        row.innerHTML = `
          <td>${student.firstName} ${student.lastName}</td>
          <td>${student.id}</td>
          <td>${student.yearLevel}</td>
          <td>${student.phone}</td>
          <td class="action-icons">
            <button class="btn-delete" data-id="${student.id}">
              <i class="fas fa-trash-alt"></i>
            </button>
            <button class="btn-edit" data-id="${student.id}">
              <i class="fas fa-edit"></i>
            </button>
          </td>
        `;

        elements.studentsTable.appendChild(row);
      });

      // Set up event handlers for the newly created buttons
      this.setupActionButtons();
    },

    setupActionButtons() {
      // Setup delete buttons
      document.querySelectorAll('.btn-delete').forEach(button => {
        button.addEventListener('click', function() {
          state.studentToDelete = this.getAttribute('data-id');
          UIService.showModal(elements.confirmationModal);
        });
      });

      // Setup edit buttons
      document.querySelectorAll('.btn-edit').forEach(button => {
        button.addEventListener('click', function() {
          const studentId = this.getAttribute('data-id');
          const student = StudentService.getById(studentId);
          
          if (student) {
            state.currentEditingStudent = student;
            
            // Fill the edit form
            document.getElementById('edit-student-id').value = student.id;
            document.getElementById('edit-first-name').value = student.firstName;
            document.getElementById('edit-last-name').value = student.lastName;
            document.getElementById('edit-phone').value = student.phone;
            document.getElementById('edit-year-level').value = student.yearLevel;
            
            UIService.showModal(elements.editStudentModal);
          }
        });
      });
    },

    // Picture preview functions
    renderPicturePreview(pictures, container) {
      if (!container) {
        console.error('Picture preview container not found');
        return;
      }
      
      // Clear the preview
      container.innerHTML = '';
      
      // Display all pictures
      pictures.forEach((picture, index) => {
        const imgContainer = document.createElement('div');
        imgContainer.className = 'picture-container';
        
        const img = document.createElement('img');
        img.src = picture;
        img.alt = `Picture ${index + 1}`;
        img.style.width = '100%';
        img.style.height = '100%';
        img.style.objectFit = 'cover';
        
        const removeBtn = document.createElement('button');
        removeBtn.textContent = 'Remove';
        removeBtn.className = 'remove-picture-btn';
        removeBtn.onclick = (event) => {
          event.preventDefault();
          event.stopPropagation();
          
          const pictureIndex = state.uploadedPictures.indexOf(picture);
          if (pictureIndex > -1) {
            state.uploadedPictures.splice(pictureIndex, 1);
            imgContainer.remove();
            this.updateSaveButtonState();
          }
        };
        
        imgContainer.appendChild(img);
        imgContainer.appendChild(removeBtn);
        container.appendChild(imgContainer);
      });
    },

    updateSaveButtonState() {
      const saveButton = elements.btnSavePictures || elements.btnSaveEditPictures;
      if (!saveButton) return;
      
      const disabled = state.uploadedPictures.length < state.MIN_PICTURES;
      saveButton.disabled = disabled;
      saveButton.style.opacity = disabled ? '0.5' : '1';
      saveButton.style.cursor = disabled ? 'not-allowed' : 'pointer';
    },

    resetAddForm() {
      if (!elements.addStudentForm) return;
      
      elements.addStudentForm.reset();
      if (elements.picturePreview) {
        elements.picturePreview.innerHTML = '';
      }
    },

    showPicturesModal() {
      if (!elements.studentPicturesModal || !elements.picturePreview) {
        console.error('Pictures modal or preview container not found');
        return;
      }
      
      state.uploadedPictures = [];
      elements.picturePreview.innerHTML = '';
      this.showModal(elements.studentPicturesModal);
      this.updateSaveButtonState();
    },

    showEditPicturesModal() {
      if (!state.currentEditingStudent || !elements.editPicturePreview) return;
      
      // Get the current pictures for this student
      const pictures = PictureService.getForStudent(state.currentEditingStudent.id);
      
      // Reset the uploadedPictures array with the current pictures
      state.uploadedPictures = [...pictures];
      
      // Display the pictures
      this.renderPicturePreview(state.uploadedPictures, elements.editPicturePreview);
      this.showModal(elements.editPicturesModal);
      this.updateSaveButtonState();
    }
  };

  /**
   * Event Handlers
   */
  const EventHandlers = {
    // File handling
    handleFileSelection(e) {
      const files = e.target.files;
      if (!files || files.length === 0) return;

      // Check if adding new files would exceed the maximum limit
      if (state.uploadedPictures.length + files.length > state.MAX_PICTURES) {
        alert(`Maximum of ${state.MAX_PICTURES} pictures allowed. Please remove some pictures first.`);
        e.target.value = '';
        return;
      }

      // Determine which modal is currently active to select the correct preview container
      let activeModal, previewContainer;
      if (elements.editPicturesModal && elements.editPicturesModal.classList.contains('active')) {
        activeModal = 'edit';
        previewContainer = elements.editPicturePreview;
      } else {
        activeModal = 'add';
        previewContainer = elements.picturePreview;
      }

      console.log(`Active modal: ${activeModal}, using container:`, previewContainer);

      // Convert files to base64 and add to uploadedPictures
      let filesProcessed = 0;
      const imageFiles = Array.from(files).filter(file => file.type.startsWith('image/'));
      const totalFiles = imageFiles.length;

      if (totalFiles === 0) {
        alert('Please select valid image files.');
        return;
      }

      imageFiles.forEach(file => {
        const reader = new FileReader();
        reader.onload = function(e) {
          state.uploadedPictures.push(e.target.result);
          filesProcessed++;
          
          // Only update display after all files are processed
          if (filesProcessed === totalFiles) {
            UIService.renderPicturePreview(state.uploadedPictures, previewContainer);
            UIService.updateSaveButtonState();
          }
        };
        reader.readAsDataURL(file);
      });

      // Reset file input
      e.target.value = '';
    },

    // Form submissions
    handleAddStudentSubmit(e) {
      e.preventDefault();
      
      const firstName = document.getElementById('add-first-name').value.trim();
      const lastName = document.getElementById('add-last-name').value.trim();
      const phone = document.getElementById('add-phone').value.trim();
      const yearLevel = document.getElementById('add-year-level').value;
      const idNumber = document.getElementById('add-id-number').value.trim();

      const newStudent = {
        id: idNumber,
        firstName,
        lastName,
        yearLevel,
        phone
      };

      // Validate student data
      const validation = StudentService.validateStudent(newStudent);
      if (!validation.valid) {
        alert(validation.message);
        return;
      }

      state.newStudentData = newStudent;
      UIService.hideModal(elements.addStudentModal);
      UIService.showPicturesModal();
    },

    handleEditStudentSubmit(e) {
      e.preventDefault();
      
      const studentId = document.getElementById('edit-student-id').value;
      const firstName = document.getElementById('edit-first-name').value.trim();
      const lastName = document.getElementById('edit-last-name').value.trim();
      const phone = document.getElementById('edit-phone').value.trim();
      const yearLevel = document.getElementById('edit-year-level').value;

      const updatedStudent = {
        firstName,
        lastName,
        yearLevel,
        phone
      };

      // Validate updated data
      const validation = StudentService.validateStudent({ ...updatedStudent, id: studentId });
      if (!validation.valid) {
        alert(validation.message);
        return;
      }

      StudentService.update(studentId, updatedStudent);
      UIService.hideModal(elements.editStudentModal);
      UIService.showEditPicturesModal();
    },

    handleSearch(e) {
      const searchTerm = e.target.value.trim();
      const filteredStudents = StudentService.search(searchTerm);
      UIService.renderStudentsTable(filteredStudents);
    },

    handleYearLevelFilter(e) {
      const selectedYearLevel = e.target.value;
      const filteredStudents = StudentService.filterByYearLevel(selectedYearLevel);
      UIService.renderStudentsTable(filteredStudents);
    },

    // Button actions
    handleDeleteConfirmation() {
      if (state.studentToDelete) {
        StudentService.delete(state.studentToDelete);
        PictureService.removeForStudent(state.studentToDelete);
        UIService.hideModal(elements.confirmationModal);
        state.studentToDelete = null;
        UIService.renderStudentsTable(StudentService.getAll());
      }
    },

    handleSaveNewStudent() {
      if (state.newStudentData && state.uploadedPictures.length >= state.MIN_PICTURES) {
        StudentService.create(state.newStudentData);
        PictureService.saveForStudent(state.newStudentData.id, state.uploadedPictures);
        
        state.newStudentData = null;
        state.uploadedPictures = [];
        UIService.resetAddForm();
        UIService.hideModal(elements.studentPicturesModal);
        UIService.renderStudentsTable(StudentService.getAll());
      } else {
        alert(`Please upload at least ${state.MIN_PICTURES} pictures before saving.`);
      }
    },

    handleSaveEditedStudentPictures() {
      if (state.currentEditingStudent && state.uploadedPictures.length >= state.MIN_PICTURES) {
        PictureService.saveForStudent(state.currentEditingStudent.id, state.uploadedPictures);
        
        state.currentEditingStudent = null;
        state.uploadedPictures = [];
        UIService.hideModal(elements.editPicturesModal);
        UIService.renderStudentsTable(StudentService.getAll());
      } else {
        alert(`Please upload at least ${state.MIN_PICTURES} pictures before saving.`);
      }
    },

    handleUploadPicturesClick() {
      if (state.uploadedPictures.length >= state.MAX_PICTURES) {
        alert(`Maximum of ${state.MAX_PICTURES} pictures allowed.`);
        return;
      }
      if (elements.fileInput) {
        elements.fileInput.value = '';
        elements.fileInput.click();
      }
    },

    handleLogout(e) {
      e.preventDefault();
      if (confirm('Are you sure you want to logout?')) {
        window.location.href = '/Login Page.html';
      }
    },

    // Sidebar menu navigation
    handleSidebarNavigation(menuText) {
      const routes = {
        'Logout': () => {
          if (confirm('Are you sure you want to logout?')) {
            window.location.href = '/Login Page.html';
          }
        },
        'Manage Students': () => window.location.href = 'Manage Students.html',
        'Manage Instructors': () => window.location.href = 'Manage Instructor.html',
        'Manage Courses': () => window.location.href = 'Manage Courses.html',
        'Manage Class': () => alert('Navigating to Manage Class page...'),
        'Manage Instructor Attendance': () => alert('Navigating to Manage Instructor Attendance page...')
      };

      const action = routes[menuText];
      if (action) action();
      else alert(`Navigating to ${menuText} page...`);
    }
  };

  /**
   * Initialize the application
   */
  function init() {
    // Initialize storage
    StorageService.init(STORAGE_KEYS.STUDENTS, initialStudents);
    StorageService.init(STORAGE_KEYS.STUDENT_PICTURES, dummyPictures);
    
    // Render the students table
    UIService.renderStudentsTable(StudentService.getAll());
    
    // Debug DOM elements to ensure they're being found correctly
    console.log('DOM Elements check:', {
      studentsTable: elements.studentsTable,
      studentCount: elements.studentCount,
      picturePreview: elements.picturePreview,
      editPicturePreview: elements.editPicturePreview
    });
    
    // Set up event listeners
    setupEventListeners();
  }

  /**
   * Set up all event listeners
   */
  function setupEventListeners() {
    // Logout button
    if (elements.logoutBtn) {
      const newLogoutBtn = elements.logoutBtn.cloneNode(true);
      elements.logoutBtn.parentNode.replaceChild(newLogoutBtn, elements.logoutBtn);
      newLogoutBtn.addEventListener('click', EventHandlers.handleLogout);
    }

    // Add student
    if (elements.btnAddStudent) {
      elements.btnAddStudent.addEventListener('click', () => {
        UIService.resetAddForm();
        UIService.showModal(elements.addStudentModal);
      });
    }

    // Modal close buttons
    if (elements.closeAddModal) {
      elements.closeAddModal.addEventListener('click', () => UIService.hideModal(elements.addStudentModal));
    }
    if (elements.closeEditModal) {
      elements.closeEditModal.addEventListener('click', () => UIService.hideModal(elements.editStudentModal));
    }
    if (elements.closePicturesModal) {
      elements.closePicturesModal.addEventListener('click', () => UIService.hideModal(elements.studentPicturesModal));
    }
    if (elements.closeEditPicturesModal) {
      elements.closeEditPicturesModal.addEventListener('click', () => UIService.hideModal(elements.editPicturesModal));
    }

    // Confirmation buttons
    if (elements.btnConfirmNo) {
      elements.btnConfirmNo.addEventListener('click', () => UIService.hideModal(elements.confirmationModal));
    }
    if (elements.btnConfirmYes) {
      elements.btnConfirmYes.addEventListener('click', EventHandlers.handleDeleteConfirmation);
    }

    // File upload buttons
    if (elements.btnUploadPictures) {
      elements.btnUploadPictures.addEventListener('click', EventHandlers.handleUploadPicturesClick);
    }
    if (elements.btnChangePictures) {
      elements.btnChangePictures.addEventListener('click', EventHandlers.handleUploadPicturesClick);
    }

    // File input
    if (elements.fileInput) {
      elements.fileInput.addEventListener('change', EventHandlers.handleFileSelection);
    }

    // Save buttons
    if (elements.btnSavePictures) {
      elements.btnSavePictures.addEventListener('click', EventHandlers.handleSaveNewStudent);
    }
    if (elements.btnSaveEditPictures) {
      elements.btnSaveEditPictures.addEventListener('click', EventHandlers.handleSaveEditedStudentPictures);
    }

    // Forms
    if (elements.addStudentForm) {
      elements.addStudentForm.addEventListener('submit', EventHandlers.handleAddStudentSubmit);
    }
    if (elements.editStudentForm) {
      elements.editStudentForm.addEventListener('submit', EventHandlers.handleEditStudentSubmit);
    }

    // Search
    if (elements.searchInput) {
      elements.searchInput.addEventListener('input', EventHandlers.handleSearch);
    }

    // Year Level Filter
    if (elements.yearLevelFilter) {
      elements.yearLevelFilter.addEventListener('change', EventHandlers.handleYearLevelFilter);
    }

    // Sidebar menu
    document.querySelectorAll('.sidebar-menu li').forEach(item => {
      item.addEventListener('click', function() {
        const menuText = this.textContent.trim();
        EventHandlers.handleSidebarNavigation(menuText);
      });
    });
  }

  // Start the application
  init();
});

// Public function for updating student count - needed for external calls
function updateStudentCount() {
  const studentCount = document.getElementById('student-count');
  const students = JSON.parse(localStorage.getItem('students') || '[]');
  if (studentCount) {
    studentCount.textContent = students.length;
  }
}

// Public function for rendering student table - needed for external calls
function renderStudentTable() {
  const students = JSON.parse(localStorage.getItem('students') || '[]');
  const studentsTable = document.getElementById('students-table');
  
  if (!studentsTable) return;
  
  studentsTable.innerHTML = '';
  
  students.forEach(student => {
    const row = document.createElement('tr');
    row.setAttribute('data-id', student.id);
    
    row.innerHTML = `
      <td>${student.firstName} ${student.lastName}</td>
      <td>${student.id}</td>
      <td>${student.yearLevel}</td>
      <td>${student.phone}</td>
      <td class="action-icons">
        <button class="btn-delete" data-id="${student.id}">
          <i class="fas fa-trash-alt"></i>
        </button>
        <button class="btn-edit" data-id="${student.id}">
          <i class="fas fa-edit"></i>
        </button>
      </td>
    `;
    
    studentsTable.appendChild(row);
  });
}