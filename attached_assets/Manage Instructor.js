/**
 * Instructor Management System
 * Handles CRUD operations for instructor data with localStorage
 */
console.log("JS file loaded!");

document.addEventListener('DOMContentLoaded', () => {
  // DOM element references - cached for performance
  const elements = {
    instructorsTable: document.getElementById('instructors-table'),
    instructorCount: document.getElementById('instructor-count'),
    searchInput: document.querySelector('.search-box input'),
    logoutBtn: document.getElementById('logout-btn'),
    // Forms
    editInstructorForm: document.getElementById('editInstructorForm'),
    addInstructorForm: document.getElementById('addInstructorForm'),
    // Modals
    confirmationModal: document.getElementById('confirmationModal'),
    editInstructorModal: document.getElementById('editInstructorModal'),
    addInstructorModal: document.getElementById('addInstructorModal'),
    instructorPicturesModal: document.getElementById('instructorPicturesModal'),
    editPicturesModal: document.getElementById('editPicturesModal'),
    // Buttons
    btnAddInstructor: document.getElementById('btnAddInstructor'),
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
    instructorToDelete: null,
    newInstructorData: null,
    uploadedPictures: [],
    currentEditingInstructor: null,
    MAX_PICTURES: 6,
    MIN_PICTURES: 3
  };

  // Constants
  const STORAGE_KEYS = {
    INSTRUCTORS: 'instructors',
    INSTRUCTOR_PICTURES: 'instructorPictures',
    CLASSES: 'classes',
    INSTRUCTOR_ATTENDANCE: 'instructorAttendance'
  };

  // Initial data
  const initialInstructors = [
    { id: 'INS-001', firstName: 'Kobe', lastName: 'Bryant', email: 'Kobe@gmail.com', phone: '09234572631', password: 'password123' },
    { id: 'INS-002', firstName: 'Lebron', lastName: 'James', email: 'Lebron@gmail.com', phone: '09123437465', password: 'password123' },
    { id: 'INS-003', firstName: 'Stephen', lastName: 'Curry', email: 'Curry@gmail.com', phone: '09832323552', password: 'password123' }
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
   * Instructor Service - Handles instructor CRUD operations
   */
  const InstructorService = {
    getAll() {
      return StorageService.get(STORAGE_KEYS.INSTRUCTORS);
    },

    getById(id) {
      return this.getAll().find(instructor => instructor.id === id);
    },

    create(instructor) {
      const instructors = this.getAll();
      instructors.push(instructor);
      return StorageService.save(STORAGE_KEYS.INSTRUCTORS, instructors);
    },

    update(id, updatedData) {
      const instructors = this.getAll();
      const index = instructors.findIndex(instructor => instructor.id === id);
      
      if (index !== -1) {
        const oldName = `${instructors[index].firstName} ${instructors[index].lastName}`;
        const newName = `${updatedData.firstName} ${updatedData.lastName}`;
        
        instructors[index] = { ...instructors[index], ...updatedData };
        StorageService.save(STORAGE_KEYS.INSTRUCTORS, instructors);
        
        // Update related records
        ClassService.updateInstructorReferences(oldName, newName);
        AttendanceService.updateInstructorReferences(oldName, newName);
        
        return true;
      }
      return false;
    },

    delete(id) {
      const instructors = this.getAll();
      const instructorToDelete = this.getById(id);
      
      if (instructorToDelete) {
        const instructorName = `${instructorToDelete.firstName} ${instructorToDelete.lastName}`;
        
        // Remove instructor from related records
        ClassService.removeInstructorReferences(instructorName);
        AttendanceService.removeInstructor(instructorName);
        PictureService.removeForInstructor(id);
        
        // Remove the instructor
        const updatedInstructors = instructors.filter(instructor => instructor.id !== id);
        return StorageService.save(STORAGE_KEYS.INSTRUCTORS, updatedInstructors);
      }
      return false;
    },

    search(term) {
      const instructors = this.getAll();
      const searchTerm = term.toLowerCase();
      
      return instructors.filter(instructor => 
        instructor.firstName.toLowerCase().includes(searchTerm) || 
        instructor.lastName.toLowerCase().includes(searchTerm) ||
        instructor.email.toLowerCase().includes(searchTerm) ||
        instructor.phone.includes(searchTerm)
      );
    },

    generateNewId() {
      const instructors = this.getAll();
      if (instructors.length === 0) return 'INS-001';
      
      const lastId = instructors[instructors.length - 1].id;
      const lastNumber = parseInt(lastId.split('-')[1]);
      return `INS-${(lastNumber + 1).toString().padStart(3, '0')}`;
    }
  };

  /**
   * Picture Service - Handles instructor pictures
   */
  const PictureService = {
    getForInstructor(instructorId) {
      const picturesData = StorageService.get(STORAGE_KEYS.INSTRUCTOR_PICTURES, {});
      return picturesData[instructorId] || picturesData.default || [];
    },

    saveForInstructor(instructorId, pictures) {
      const picturesData = StorageService.get(STORAGE_KEYS.INSTRUCTOR_PICTURES, {});
      picturesData[instructorId] = pictures;
      return StorageService.save(STORAGE_KEYS.INSTRUCTOR_PICTURES, picturesData);
    },

    removeForInstructor(instructorId) {
      const picturesData = StorageService.get(STORAGE_KEYS.INSTRUCTOR_PICTURES, {});
      delete picturesData[instructorId];
      return StorageService.save(STORAGE_KEYS.INSTRUCTOR_PICTURES, picturesData);
    }
  };

  /**
   * Class Service - Handles class-related operations
   */
  const ClassService = {
    updateInstructorReferences(oldName, newName) {
      const classes = StorageService.get(STORAGE_KEYS.CLASSES);
      
      const updatedClasses = classes.map(cls => 
        cls.instructor === oldName ? { ...cls, instructor: newName } : cls
      );
      
      StorageService.save(STORAGE_KEYS.CLASSES, updatedClasses);
    },

    removeInstructorReferences(instructorName) {
      const classes = StorageService.get(STORAGE_KEYS.CLASSES);
      
      const updatedClasses = classes.map(cls => 
        cls.instructor === instructorName ? { ...cls, instructor: 'Unassigned' } : cls
      );
      
      StorageService.save(STORAGE_KEYS.CLASSES, updatedClasses);
    }
  };

  /**
   * Attendance Service - Handles attendance-related operations
   */
  const AttendanceService = {
    updateInstructorReferences(oldName, newName) {
      const attendance = StorageService.get(STORAGE_KEYS.INSTRUCTOR_ATTENDANCE, {});
      
      if (attendance[oldName]) {
        attendance[newName] = attendance[oldName];
        delete attendance[oldName];
        StorageService.save(STORAGE_KEYS.INSTRUCTOR_ATTENDANCE, attendance);
      }
    },

    removeInstructor(instructorName) {
      const attendance = StorageService.get(STORAGE_KEYS.INSTRUCTOR_ATTENDANCE, {});
      delete attendance[instructorName];
      StorageService.save(STORAGE_KEYS.INSTRUCTOR_ATTENDANCE, attendance);
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
    renderInstructorsTable(instructors) {
      if (!elements.instructorsTable || !elements.instructorCount) return;
      
      elements.instructorsTable.innerHTML = '';
      elements.instructorCount.textContent = instructors.length;

      instructors.forEach(instructor => {
        const row = document.createElement('tr');
        row.setAttribute('data-id', instructor.id);
        
        row.innerHTML = `
          <td>${instructor.firstName} ${instructor.lastName}</td>
          <td>${instructor.email}</td>
          <td>${instructor.phone}</td>
          <td class="action-icons">
            <button class="btn-delete" data-id="${instructor.id}">
              <i class="fas fa-trash-alt"></i>
            </button>
            <button class="btn-edit" data-id="${instructor.id}">
              <i class="fas fa-edit"></i>
            </button>
          </td>
        `;

        elements.instructorsTable.appendChild(row);
      });

      // Set up event handlers for the newly created buttons
      this.setupActionButtons();
    },

    setupActionButtons() {
      // Setup delete buttons
      document.querySelectorAll('.btn-delete').forEach(button => {
        button.addEventListener('click', function() {
          state.instructorToDelete = this.getAttribute('data-id');
          UIService.showModal(elements.confirmationModal);
        });
      });

      // Setup edit buttons
      document.querySelectorAll('.btn-edit').forEach(button => {
        button.addEventListener('click', function() {
          const instructorId = this.getAttribute('data-id');
          const instructor = InstructorService.getById(instructorId);
          
          if (instructor) {
            state.currentEditingInstructor = instructor;
            
            // Fill the edit form
            document.getElementById('edit-instructor-id').value = instructor.id;
            document.getElementById('edit-first-name').value = instructor.firstName;
            document.getElementById('edit-last-name').value = instructor.lastName;
            document.getElementById('edit-email').value = instructor.email;
            document.getElementById('edit-phone').value = instructor.phone;
            document.getElementById('edit-password').value = instructor.password;
            document.getElementById('edit-confirm-password').value = instructor.password;
            
            UIService.showModal(elements.editInstructorModal);
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
      if (!elements.addInstructorForm) return;
      
      elements.addInstructorForm.reset();
      if (elements.picturePreview) {
        elements.picturePreview.innerHTML = '';
      }
    },

    showPicturesModal() {
      if (!elements.instructorPicturesModal || !elements.picturePreview) {
        console.error('Pictures modal or preview container not found');
        return;
      }
      
      state.uploadedPictures = [];
      elements.picturePreview.innerHTML = '';
      this.showModal(elements.instructorPicturesModal);
      this.updateSaveButtonState();
    },

    showEditPicturesModal() {
      if (!state.currentEditingInstructor || !elements.editPicturePreview) return;
      
      // Get the current pictures for this instructor
      const pictures = PictureService.getForInstructor(state.currentEditingInstructor.id);
      
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
    handleAddInstructorSubmit(e) {
      e.preventDefault();
      
      const firstName = document.getElementById('add-first-name').value.trim();
      const lastName = document.getElementById('add-last-name').value.trim();
      const email = document.getElementById('add-email').value.trim();
      const phone = document.getElementById('add-phone').value.trim();
      const password = document.getElementById('add-password').value;
      const confirmPassword = document.getElementById('add-confirm-password').value;

      if (!firstName || !lastName || !email || !phone || !password) {
        alert('Please fill in all required fields');
        return;
      }

      if (password !== confirmPassword) {
        alert('Passwords do not match!');
        return;
      }

      // Email validation
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        alert('Please enter a valid email address');
        return;
      }

      // Generate a new ID
      const newId = InstructorService.generateNewId();

      state.newInstructorData = {
        id: newId,
        firstName,
        lastName,
        email,
        phone,
        password
      };

      UIService.hideModal(elements.addInstructorModal);
      UIService.showPicturesModal();
    },

    handleEditInstructorSubmit(e) {
      e.preventDefault();
      
      const instructorId = document.getElementById('edit-instructor-id').value;
      const firstName = document.getElementById('edit-first-name').value.trim();
      const lastName = document.getElementById('edit-last-name').value.trim();
      const email = document.getElementById('edit-email').value.trim();
      const phone = document.getElementById('edit-phone').value.trim();
      const password = document.getElementById('edit-password').value;
      const confirmPassword = document.getElementById('edit-confirm-password').value;

      if (!firstName || !lastName || !email || !phone) {
        alert('Please fill in all required fields');
        return;
      }

      if (password !== confirmPassword) {
        alert('Passwords do not match!');
        return;
      }

      // Email validation
      const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
      if (!emailRegex.test(email)) {
        alert('Please enter a valid email address');
        return;
      }

      InstructorService.update(instructorId, { firstName, lastName, email, phone, password });
      UIService.hideModal(elements.editInstructorModal);
      UIService.showEditPicturesModal();
    },

    handleSearch(e) {
      const searchTerm = e.target.value.trim();
      const filteredInstructors = InstructorService.search(searchTerm);
      UIService.renderInstructorsTable(filteredInstructors);
    },

    // Button actions
    handleDeleteConfirmation() {
      if (state.instructorToDelete) {
        InstructorService.delete(state.instructorToDelete);
        UIService.hideModal(elements.confirmationModal);
        state.instructorToDelete = null;
        UIService.renderInstructorsTable(InstructorService.getAll());
      }
    },

    handleSaveNewInstructor() {
      if (state.newInstructorData && state.uploadedPictures.length >= state.MIN_PICTURES) {
        InstructorService.create(state.newInstructorData);
        PictureService.saveForInstructor(state.newInstructorData.id, state.uploadedPictures);
        
        state.newInstructorData = null;
        state.uploadedPictures = [];
        UIService.resetAddForm();
        UIService.hideModal(elements.instructorPicturesModal);
        UIService.renderInstructorsTable(InstructorService.getAll());
      } else {
        alert(`Please upload at least ${state.MIN_PICTURES} pictures before saving.`);
      }
    },

    handleSaveEditedInstructorPictures() {
      if (state.currentEditingInstructor && state.uploadedPictures.length >= state.MIN_PICTURES) {
        PictureService.saveForInstructor(state.currentEditingInstructor.id, state.uploadedPictures);
        
        state.currentEditingInstructor = null;
        state.uploadedPictures = [];
        UIService.hideModal(elements.editPicturesModal);
        UIService.renderInstructorsTable(InstructorService.getAll());
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
    StorageService.init(STORAGE_KEYS.INSTRUCTORS, initialInstructors);
    StorageService.init(STORAGE_KEYS.INSTRUCTOR_PICTURES, dummyPictures);
    
    // Render the instructors table
    UIService.renderInstructorsTable(InstructorService.getAll());
    
    // Debug DOM elements to ensure they're being found correctly
    console.log('DOM Elements check:', {
      picturePreview: elements.picturePreview,
      editPicturePreview: elements.editPicturePreview,
      instructorPicturesModal: elements.instructorPicturesModal,
      editPicturesModal: elements.editPicturesModal,
      fileInput: elements.fileInput
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

    // Add instructor
    if (elements.btnAddInstructor) {
      elements.btnAddInstructor.addEventListener('click', () => {
        UIService.resetAddForm();
        UIService.showModal(elements.addInstructorModal);
      });
    }

    // Modal close buttons
    if (elements.closeAddModal) {
      elements.closeAddModal.addEventListener('click', () => UIService.hideModal(elements.addInstructorModal));
    }
    if (elements.closeEditModal) {
      elements.closeEditModal.addEventListener('click', () => UIService.hideModal(elements.editInstructorModal));
    }
    if (elements.closePicturesModal) {
      elements.closePicturesModal.addEventListener('click', () => UIService.hideModal(elements.instructorPicturesModal));
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
      elements.btnSavePictures.addEventListener('click', EventHandlers.handleSaveNewInstructor);
    }
    if (elements.btnSaveEditPictures) {
      elements.btnSaveEditPictures.addEventListener('click', EventHandlers.handleSaveEditedInstructorPictures);
    }

    // Forms
    if (elements.addInstructorForm) {
      elements.addInstructorForm.addEventListener('submit', EventHandlers.handleAddInstructorSubmit);
    }
    if (elements.editInstructorForm) {
      elements.editInstructorForm.addEventListener('submit', EventHandlers.handleEditInstructorSubmit);
    }

    // Search
    if (elements.searchInput) {
      elements.searchInput.addEventListener('input', EventHandlers.handleSearch);
    }

    // Sidebar menu
    document.querySelectorAll('.sidebar-menu li').forEach(item => {
      item.addEventListener('click', function() {
        const menuText = this.textContent.trim();
        EventHandlers.handleSidebarNavigation(menuText);
      });
    });
  }

  // Initialize the application
  init();
});