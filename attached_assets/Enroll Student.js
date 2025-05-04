/**
 * Student Management System
 * Handles CRUD operations for student data with localStorage
 * Improved version based on service-oriented architecture
 */
console.log("Student Management System loaded!");

document.addEventListener('DOMContentLoaded', () => {
  // DOM element references - cached for better performance
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
    logoutBtn: document.getElementById('logoutBtn'),
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
    fileInput: document.getElementById('fileInput'),
    picturesPreview: document.getElementById('picturesPreview'),
    editPicturesPreview: document.getElementById('editPicturesPreview'),
    savePicturesBtn: document.getElementById('savePicturesBtn'),
    saveEditPicturesBtn: document.getElementById('saveEditPicturesBtn')
  };

  // Application state
  const state = {
    currentStudentId: null,
    uploadedPictures: [],
    minPictures: 3,
    maxPictures: 6
  };

  // Constants
  const STORAGE_KEYS = {
    STUDENTS: 'students',
    PICTURES: 'studentPictures',
    ATTENDANCE: 'studentAttendance',
    COURSES: 'studentCourses'
  };

  /**
   * Storage Service - Handles localStorage operations
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
      return StorageService.get(STORAGE_KEYS.STUDENTS, []);
    },

    getById(id) {
      return this.getAll().find(student => student.id === id);
    },

    create(student) {
      const students = this.getAll();
      // Ensure enrolledClasses is always present
      if (!student.enrolledClasses) student.enrolledClasses = [];
      students.push(student);
      return StorageService.save(STORAGE_KEYS.STUDENTS, students);
    },

    update(id, updatedData) {
      const students = this.getAll();
      const index = students.findIndex(student => student.id === id);
      
      if (index !== -1) {
        const oldName = `${students[index].firstName} ${students[index].lastName}`;
        const newName = `${updatedData.firstName} ${updatedData.lastName}`;
        
        students[index] = { ...students[index], ...updatedData };
        StorageService.save(STORAGE_KEYS.STUDENTS, students);
        
        // Update related records
        CourseService.updateStudentReferences(oldName, newName);
        AttendanceService.updateStudentReferences(oldName, newName);
        
        return true;
      }
      return false;
    },

    delete(id) {
      const students = this.getAll();
      const studentToDelete = this.getById(id);
      
      if (studentToDelete) {
        const studentName = `${studentToDelete.firstName} ${studentToDelete.lastName}`;
        
        // Remove student from related records
        CourseService.removeStudentReferences(studentName);
        AttendanceService.removeStudent(studentName);
        PictureService.removeForStudent(id);
        
        // Remove the student
        const updatedStudents = students.filter(student => student.id !== id);
        return StorageService.save(STORAGE_KEYS.STUDENTS, updatedStudents);
      }
      return false;
    },

    search(term) {
      const students = this.getAll();
      const searchTerm = term.toLowerCase();
      
      return students.filter(student => 
        student.firstName.toLowerCase().includes(searchTerm) || 
        student.lastName.toLowerCase().includes(searchTerm) ||
        student.id.toLowerCase().includes(searchTerm) ||
        student.yearLevel.toLowerCase().includes(searchTerm) ||
        student.phone.includes(searchTerm)
      );
    },

    generateNewId() {
      // Create ID in format YY-XXXXX (e.g., 24-00001)
      const year = new Date().getFullYear().toString().substr(-2);
      const students = this.getAll();
      
      // If no students, start with 00001
      if (students.length === 0) return `${year}-00001`;
      
      // Get only the IDs from current year
      const currentYearIds = students
        .map(s => s.id)
        .filter(id => id.startsWith(year));
      
      if (currentYearIds.length === 0) return `${year}-00001`;
      
      // Find the highest number and increment
      const highestNumber = currentYearIds
        .map(id => parseInt(id.split('-')[1]))
        .reduce((max, num) => Math.max(max, num), 0);
      
      return `${year}-${(highestNumber + 1).toString().padStart(5, '0')}`;
    },

    validatePhone(phone) {
      // Phone must start with 09 and have 11 digits total
      const phoneRegex = /^09\d{9}$/;
      return phoneRegex.test(phone);
    },

    validateId(id) {
      // ID must be in format XX-XXXXX
      const idRegex = /^\d{2}-\d{5}$/;
      return idRegex.test(id);
    },

    sortByYearLevel() {
      const students = this.getAll();
      const yearLevelOrder = {
        '1st Year': 1,
        '2nd Year': 2,
        '3rd Year': 3,
        '4th Year': 4
      };
      
      students.sort((a, b) => yearLevelOrder[a.yearLevel] - yearLevelOrder[b.yearLevel]);
      return students;
    },

    // Enroll a student in a class
    enrollInClass(studentId, classId) {
      const students = this.getAll();
      const student = students.find(s => s.id === studentId);
      if (student && !student.enrolledClasses.includes(classId)) {
        student.enrolledClasses.push(classId);
        StorageService.save(STORAGE_KEYS.STUDENTS, students);
      }
    },

    // Unenroll a student from a class
    unenrollFromClass(studentId, classId) {
      const students = this.getAll();
      const student = students.find(s => s.id === studentId);
      if (student && student.enrolledClasses.includes(classId)) {
        student.enrolledClasses = student.enrolledClasses.filter(cid => cid !== classId);
        StorageService.save(STORAGE_KEYS.STUDENTS, students);
      }
    }
  };

  /**
   * Picture Service - Handles student pictures
   */
  const PictureService = {
    getForStudent(studentId) {
      const picturesData = StorageService.get(STORAGE_KEYS.PICTURES, {});
      return picturesData[studentId] || picturesData.default || [];
    },

    saveForStudent(studentId, pictures) {
      const picturesData = StorageService.get(STORAGE_KEYS.PICTURES, {});
      picturesData[studentId] = pictures;
      return StorageService.save(STORAGE_KEYS.PICTURES, picturesData);
    },

    removeForStudent(studentId) {
      const picturesData = StorageService.get(STORAGE_KEYS.PICTURES, {});
      delete picturesData[studentId];
      return StorageService.save(STORAGE_KEYS.PICTURES, picturesData);
    }
  };

  /**
   * Course Service - Handles course-related operations for students
   */
  const CourseService = {
    updateStudentReferences(oldName, newName) {
      const courses = StorageService.get(STORAGE_KEYS.COURSES, {});
      
      // Update student name in course enrollments
      Object.keys(courses).forEach(courseId => {
        const enrolledStudents = courses[courseId].enrolledStudents || [];
        const updatedEnrollments = enrolledStudents.map(name => 
          name === oldName ? newName : name
        );
        courses[courseId].enrolledStudents = updatedEnrollments;
      });
      
      StorageService.save(STORAGE_KEYS.COURSES, courses);
    },

    removeStudentReferences(studentName) {
      const courses = StorageService.get(STORAGE_KEYS.COURSES, {});
      
      // Remove student from all course enrollments
      Object.keys(courses).forEach(courseId => {
        const enrolledStudents = courses[courseId].enrolledStudents || [];
        courses[courseId].enrolledStudents = enrolledStudents.filter(name => name !== studentName);
      });
      
      StorageService.save(STORAGE_KEYS.COURSES, courses);
    }
  };

  /**
   * Attendance Service - Handles attendance-related operations
   */
  const AttendanceService = {
    updateStudentReferences(oldName, newName) {
      const attendance = StorageService.get(STORAGE_KEYS.ATTENDANCE, {});
      
      if (attendance[oldName]) {
        attendance[newName] = attendance[oldName];
        delete attendance[oldName];
        StorageService.save(STORAGE_KEYS.ATTENDANCE, attendance);
      }
    },

    removeStudent(studentName) {
      const attendance = StorageService.get(STORAGE_KEYS.ATTENDANCE, {});
      delete attendance[studentName];
      StorageService.save(STORAGE_KEYS.ATTENDANCE, attendance);
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

    hideAllModals() {
      const modals = [
        elements.enrollModal, 
        elements.picturesModal, 
        elements.editModal, 
        elements.editPicturesModal, 
        elements.confirmationModal
      ];
      
      modals.forEach(modal => {
        if (modal) this.hideModal(modal);
      });
    },

    // Student table rendering
    renderStudentsTable(students) {
      if (!elements.studentsTableBody) return;
      
      elements.studentsTableBody.innerHTML = '';
      
      students.forEach(student => {
        const row = document.createElement('tr');
        
        row.innerHTML = `
          <td>${student.firstName} ${student.lastName}</td>
          <td>${student.id}</td>
          <td>${student.yearLevel}</td>
          <td>${student.phone}</td>
          <td>
            <button class="action-btn btn-delete" data-id="${student.id}">
              <i class="fas fa-trash-alt"></i>
            </button>
            <button class="action-btn btn-edit" data-id="${student.id}">
              <i class="fas fa-edit"></i>
            </button>
          </td>
        `;
        
        elements.studentsTableBody.appendChild(row);
      });
      
      // Update student counter
      if (elements.studentCounter) {
        elements.studentCounter.textContent = students.length;
      }
      
      // Attach event listeners to action buttons
      this.setupActionButtons();
    },

    // Setup action buttons for each student row
    setupActionButtons() {
      // Delete buttons
      document.querySelectorAll('.btn-delete').forEach(btn => {
        btn.addEventListener('click', function() {
          state.currentStudentId = this.getAttribute('data-id');
          UIService.showModal(elements.confirmationModal);
        });
      });
      
      // Edit buttons
      document.querySelectorAll('.btn-edit').forEach(btn => {
        btn.addEventListener('click', function() {
          state.currentStudentId = this.getAttribute('data-id');
          const student = StudentService.getById(state.currentStudentId);
          
          if (student) {
            document.getElementById('editStudentId').value = student.id;
            document.getElementById('editFirstName').value = student.firstName;
            document.getElementById('editLastName').value = student.lastName;
            document.getElementById('editPhoneNumber').value = student.phone;
            document.getElementById('editYearLevel').value = student.yearLevel;
            document.getElementById('editIdNumber').value = student.id;
            
            UIService.showModal(elements.editModal);
          }
        });
      });
    },

    // Reset form inputs
    resetForm(form) {
      if (form) form.reset();
    },

    // Picture preview rendering
    renderPicturesPreview(pictures, container) {
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
        img.className = 'student-picture';
        
        const removeBtn = document.createElement('button');
        removeBtn.textContent = 'Remove';
        removeBtn.className = 'remove-picture-btn';
        removeBtn.onclick = (event) => {
          event.preventDefault();
          event.stopPropagation();
          
          state.uploadedPictures.splice(index, 1);
          this.renderPicturesPreview(state.uploadedPictures, container);
          this.updateSaveButtonState();
        };
        
        imgContainer.appendChild(img);
        imgContainer.appendChild(removeBtn);
        container.appendChild(imgContainer);
      });
    },

    // Update save button state based on picture count
    updateSaveButtonState() {
      const saveBtns = [elements.savePicturesBtn, elements.saveEditPicturesBtn].filter(btn => btn);
      
      saveBtns.forEach(btn => {
        if (state.uploadedPictures.length < state.minPictures) {
          btn.disabled = true;
          btn.classList.add('disabled');
        } else {
          btn.disabled = false;
          btn.classList.remove('disabled');
        }
      });
    },

    showPicturesModal() {
      if (!elements.picturesModal || !elements.picturesPreview) {
        console.error('Pictures modal or preview container not found');
        return;
      }
      
      state.uploadedPictures = [];
      elements.picturesPreview.innerHTML = '';
      this.showModal(elements.picturesModal);
      this.updateSaveButtonState();
    },

    showEditPicturesModal() {
      if (!state.currentStudentId || !elements.editPicturesPreview) return;
      
      // Get the current pictures for this student
      const pictures = PictureService.getForStudent(state.currentStudentId);
      
      // Reset the uploadedPictures array with the current pictures
      state.uploadedPictures = [...pictures];
      
      // Display the pictures
      this.renderPicturesPreview(state.uploadedPictures, elements.editPicturesPreview);
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
      if (state.uploadedPictures.length + files.length > state.maxPictures) {
        alert(`Maximum of ${state.maxPictures} pictures allowed. Please remove some pictures first.`);
        e.target.value = '';
        return;
      }

      // Determine which modal is currently active to select the correct preview container
      let previewContainer;
      if (elements.editPicturesModal && elements.editPicturesModal.classList.contains('active')) {
        previewContainer = elements.editPicturesPreview;
      } else {
        previewContainer = elements.picturesPreview;
      }

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
            UIService.renderPicturesPreview(state.uploadedPictures, previewContainer);
            UIService.updateSaveButtonState();
          }
        };
        reader.readAsDataURL(file);
      });

      // Reset file input
      e.target.value = '';
    },

    // Form submissions
    handleEnrollSubmit(e) {
      e.preventDefault();

      const firstName = document.getElementById('firstName').value.trim();
      const lastName = document.getElementById('lastName').value.trim();
      const phone = document.getElementById('phoneNumber').value.trim();
      const yearLevel = document.getElementById('yearLevel').value;
      const idNumber = document.getElementById('idNumber').value.trim();

      // Basic validation
      if (!firstName || !lastName || !phone || !yearLevel) {
        alert('Please fill in all required fields');
        return;
      }

      // Validate phone number
      if (!StudentService.validatePhone(phone)) {
        alert('Please enter a valid phone number starting with 09 followed by 9 digits.');
        return;
      }

      // Validate ID number if provided
      if (idNumber) {
        if (!StudentService.validateId(idNumber)) {
          alert('Please enter a valid ID number in format XX-XXXXX.');
          return;
        }

        // Check if ID is already in use
        if (StudentService.getById(idNumber)) {
          alert('This ID number is already in use.');
          return;
        }
      }

      // Create the student object
      const studentId = idNumber || StudentService.generateNewId();
      const newStudent = {
        id: studentId,
        firstName,
        lastName,
        yearLevel,
        phone
      };

      // Add student to storage
      StudentService.create(newStudent);
      state.currentStudentId = studentId;
      state.uploadedPictures = [];

      // Reset form and hide modal
      UIService.resetForm(elements.enrollStudentForm);
      UIService.hideModal(elements.enrollModal);

      // Show pictures modal
      UIService.showPicturesModal();
    },

    handleEditSubmit(e) {
      e.preventDefault();

      const id = document.getElementById('editStudentId').value;
      const firstName = document.getElementById('editFirstName').value.trim();
      const lastName = document.getElementById('editLastName').value.trim();
      const phone = document.getElementById('editPhoneNumber').value.trim();
      const yearLevel = document.getElementById('editYearLevel').value;

      // Basic validation
      if (!firstName || !lastName || !phone || !yearLevel) {
        alert('Please fill in all required fields');
        return;
      }

      // Validate phone number
      if (!StudentService.validatePhone(phone)) {
        alert('Please enter a valid phone number starting with 09 followed by 9 digits.');
        return;
      }

      // Update student data
      StudentService.update(id, { firstName, lastName, phone, yearLevel });
      UIService.hideModal(elements.editModal);

      // Show edit pictures modal
      UIService.showEditPicturesModal();
    },

    handleSearch(e) {
      const searchTerm = e.target.value.trim();
      const filteredStudents = searchTerm ? 
        StudentService.search(searchTerm) : 
        StudentService.getAll();
      
      UIService.renderStudentsTable(filteredStudents);
    },

    handleSortByYearLevel() {
      const sortedStudents = StudentService.sortByYearLevel();
      UIService.renderStudentsTable(sortedStudents);
    },

    // Picture actions
    handleUploadPicturesClick() {
      if (state.uploadedPictures.length >= state.maxPictures) {
        alert(`Maximum of ${state.maxPictures} pictures allowed.`);
        return;
      }
      
      if (elements.fileInput) {
        elements.fileInput.value = '';
        elements.fileInput.click();
      }
    },

    handleSavePictures() {
      if (state.uploadedPictures.length < state.minPictures) {
        alert(`Please upload at least ${state.minPictures} pictures.`);
        return;
      }
      
      PictureService.saveForStudent(state.currentStudentId, state.uploadedPictures);
      UIService.hideAllModals();
      
      // Update the table and reset state
      UIService.renderStudentsTable(StudentService.getAll());
      state.currentStudentId = null;
      state.uploadedPictures = [];
    },

    handleSaveEditPictures() {
      if (state.uploadedPictures.length < state.minPictures) {
        alert(`Please upload at least ${state.minPictures} pictures.`);
        return;
      }
      
      PictureService.saveForStudent(state.currentStudentId, state.uploadedPictures);
      UIService.hideAllModals();
      
      // Update the table and reset state
      UIService.renderStudentsTable(StudentService.getAll());
      state.currentStudentId = null;
      state.uploadedPictures = [];
    },

    // Delete confirmation
    handleDeleteConfirmation() {
      if (state.currentStudentId) {
        StudentService.delete(state.currentStudentId);
        UIService.hideModal(elements.confirmationModal);
        state.currentStudentId = null;
        UIService.renderStudentsTable(StudentService.getAll());
      }
    },

    // Logout
    handleLogout(e) {
      e.preventDefault();
      if (confirm('Are you sure you want to logout?')) {
        window.location.href = '/Login Page.html';
      }
    }
  };

  /**
   * Set up event listeners for all interactive elements
   */
  function setupEventListeners() {
    // Enroll student
    if (elements.btnEnrollStudent) {
      elements.btnEnrollStudent.addEventListener('click', () => {
        UIService.resetForm(elements.enrollStudentForm);
        UIService.showModal(elements.enrollModal);
      });
    }

    // Modal close buttons
    if (elements.closeEnrollModal) {
      elements.closeEnrollModal.addEventListener('click', () => UIService.hideModal(elements.enrollModal));
    }
    
    if (elements.closePicturesModal) {
      elements.closePicturesModal.addEventListener('click', () => UIService.hideModal(elements.picturesModal));
    }
    
    if (elements.closeEditModal) {
      elements.closeEditModal.addEventListener('click', () => UIService.hideModal(elements.editModal));
    }
    
    if (elements.closeEditPicturesModal) {
      elements.closeEditPicturesModal.addEventListener('click', () => UIService.hideModal(elements.editPicturesModal));
    }

    // Form submissions
    if (elements.enrollStudentForm) {
      elements.enrollStudentForm.addEventListener('submit', EventHandlers.handleEnrollSubmit);
    }
    
    if (elements.editStudentForm) {
      elements.editStudentForm.addEventListener('submit', EventHandlers.handleEditSubmit);
    }

    // Search functionality
    if (elements.searchBtn) {
      elements.searchBtn.addEventListener('click', () => {
        const searchTerm = elements.searchInput.value.trim();
        const filteredStudents = searchTerm ? 
          StudentService.search(searchTerm) : 
          StudentService.getAll();
        
        UIService.renderStudentsTable(filteredStudents);
      });
    }

    if (elements.searchInput) {
      elements.searchInput.addEventListener('input', EventHandlers.handleSearch);
    }

    // Year level sorting
    if (elements.sortYearLevel) {
      elements.sortYearLevel.addEventListener('click', EventHandlers.handleSortByYearLevel);
    }

    // Picture upload buttons
    if (elements.uploadPicturesBtn) {
      elements.uploadPicturesBtn.addEventListener('click', EventHandlers.handleUploadPicturesClick);
    }
    
    if (elements.editUploadPicturesBtn) {
      elements.editUploadPicturesBtn.addEventListener('click', EventHandlers.handleUploadPicturesClick);
    }

    // File input
    if (elements.fileInput) {
      elements.fileInput.addEventListener('change', EventHandlers.handleFileSelection);
    }

    // Save pictures buttons
    if (elements.savePicturesBtn) {
      elements.savePicturesBtn.addEventListener('click', EventHandlers.handleSavePictures);
    }
    
    if (elements.saveEditPicturesBtn) {
      elements.saveEditPicturesBtn.addEventListener('click', EventHandlers.handleSaveEditPictures);
    }

    // Confirmation modal buttons
    if (elements.confirmYesBtn) {
      elements.confirmYesBtn.addEventListener('click', EventHandlers.handleDeleteConfirmation);
    }
    
    if (elements.confirmNoBtn) {
      elements.confirmNoBtn.addEventListener('click', () => UIService.hideModal(elements.confirmationModal));
    }

    // Logout button
    if (elements.logoutBtn) {
      elements.logoutBtn.addEventListener('click', EventHandlers.handleLogout);
    }
  }

  /**
   * Initialize the application
   */
  function init() {
    // Initial data
    const initialStudents = [
      { id: '24-00001', firstName: 'John', lastName: 'Doe', yearLevel: '1st Year', phone: '09123456789' },
      { id: '24-00002', firstName: 'Jane', lastName: 'Smith', yearLevel: '2nd Year', phone: '09123456788' }
    ];

    const initialPictures = {
      default: [
        'https://placehold.co/100x100?text=Photo1',
        'https://placehold.co/100x100?text=Photo2',
        'https://placehold.co/100x100?text=Photo3'
      ]
    };

    // Initialize storage
    StorageService.init(STORAGE_KEYS.STUDENTS, initialStudents);
    StorageService.init(STORAGE_KEYS.PICTURES, initialPictures);
    
    // Set up event listeners
    setupEventListeners();
    
    // Render initial students table
    UIService.renderStudentsTable(StudentService.getAll());
    
    console.log('Student Management System initialized successfully');
  }

  // Start the application
  init();
});