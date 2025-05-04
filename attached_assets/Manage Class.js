// Manage Class.js - with localStorage integration

// Load courses from localStorage or use default
let courses = JSON.parse(localStorage.getItem('courses')) || [
    { code: 'ITC321', description: 'Applications Development' },
    { code: 'ITP323', description: 'Capstone Project 1' },
    { code: 'ITP324', description: 'Information Assurance and Security 2' },
    { code: 'ITP325', description: 'Social and Professional Issues' },
    { code: 'ITP326', description: 'Systems Administration' }
];

// Load classes from localStorage or use default
let classes = JSON.parse(localStorage.getItem('classes')) || [
    {
        id: 1,
        courseCode: "ITC321",
        classCode: "F77",
        description: "Applications Development",
        roomNumber: "311",
        schedule: "7-8 AM MW, 8-9AM MWF",
        instructor: "Lebron James",
        timeSlots: [
            { days: ["Mon", "Wed"], startTime: "7", startAmPm: "AM", endTime: "8", endAmPm: "AM" },
            { days: ["Mon", "Wed", "Fri"], startTime: "8", startAmPm: "AM", endTime: "9", endAmPm: "AM" }
        ]
    },
    {
        id: 2,
        courseCode: "ITP323",
        classCode: "F78",
        description: "Capstone Project 1",
        roomNumber: "312",
        schedule: "1-2PM MWF",
        instructor: "Stephen Curry",
        timeSlots: [
            { days: ["Mon", "Wed", "Fri"], startTime: "1", startAmPm: "PM", endTime: "2", endAmPm: "PM" }
        ]
    },
    {
        id: 3,
        courseCode: "ITP324",
        classCode: "F79",
        description: "Information Assurance and Security 2",
        roomNumber: "310",
        schedule: "11AM-PM MW, 12-1PM MWF",
        instructor: "Kobe Bryant",
        timeSlots: [
            { days: ["Mon", "Wed"], startTime: "11", startAmPm: "AM", endTime: "12", endAmPm: "PM" },
            { days: ["Mon", "Wed", "Fri"], startTime: "12", startAmPm: "PM", endTime: "1", endAmPm: "PM" }
        ]
    },
    {
        id: 4,
        courseCode: "ITP325",
        classCode: "F80",
        description: "Social and Professional Issues",
        roomNumber: "301",
        schedule: "10:30AM-12PM TTh",
        instructor: "Kobe Bryant",
        timeSlots: [
            { days: ["Tue", "Thu"], startTime: "10:30", startAmPm: "AM", endTime: "12", endAmPm: "PM" }
        ]
    },
    {
        id: 5,
        courseCode: "ITP326",
        classCode: "F89",
        description: "Systems Administration",
        roomNumber: "301",
        schedule: "10 AM-12 PM MonTue",
        instructor: "Lebron James",
        timeSlots: [
            { days: ["Mon", "Tue"], startTime: "10", startAmPm: "AM", endTime: "12", endAmPm: "PM" }
        ]
    }
];

// Save classes to localStorage
function saveClasses() {
    localStorage.setItem('classes', JSON.stringify(classes));
}

// Check if classes already exist in localStorage
if (!localStorage.getItem('classes')) {
    saveClasses();
}

let timeSlotCounter = 0;
let classToDelete = null;

// Initialize the page
window.onload = function() {
    populateCourseDropdown();
    renderClassTable();
    updateClassCount();
    
    // Add event listener for logout
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
}

function updateClassCount() {
    document.getElementById('class-count').textContent = classes.length;
}

function populateCourseDropdown() {
    // Refresh courses from localStorage to ensure we have the latest data
    courses = JSON.parse(localStorage.getItem('courses')) || courses;
    
    const courseSelect = document.getElementById('courseDescription');
    courseSelect.innerHTML = '<option value="">Course Description</option>';
    
    courses.forEach(course => {
        const option = document.createElement('option');
        option.value = course.description;
        option.textContent = course.description;
        option.dataset.code = course.code;
        courseSelect.appendChild(option);
    });

    // Add event listener to update course code when description changes
    courseSelect.addEventListener('change', function() {
        const selectedOption = this.options[this.selectedIndex];
        if (selectedOption && selectedOption.dataset.code) {
            document.getElementById('courseCode').value = selectedOption.dataset.code;
        } else {
            document.getElementById('courseCode').value = '';
        }
    });
}

function renderClassTable() {
    const tableBody = document.getElementById('classTableBody');
    tableBody.innerHTML = '';
    
    classes.forEach(cls => {
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${cls.courseCode}</td>
            <td>${cls.classCode}</td>
            <td>${cls.description}</td>
            <td>${cls.roomNumber}</td>
            <td>${cls.schedule}</td>
            <td>${cls.instructor}</td>
            <td class="action-icons">
                <button class="btn-delete" onclick="deleteClass(${cls.id})"><i class="fa-solid fa-trash-can fa-lg"></i></button>
                <button class="btn-edit" onclick="editClass(${cls.id})"><i class="fa-solid fa-pen-to-square fa-lg"></i></button>
            </td>
        `;
        tableBody.appendChild(row);
    });
}

function showAddClassModal() {
    document.getElementById('modalTitle').innerText = 'Add Class';
    document.getElementById('classForm').reset();
    document.getElementById('classId').value = '';
    
    // Clear time slots
    document.getElementById('timeSlots').innerHTML = '';
    timeSlotCounter = 0;
    
    // Add one empty time slot by default
    addTimeSlot();
    
    document.getElementById('classModal').style.display = 'block';
}

function addTimeSlot(slot = null) {
    const timeSlots = document.getElementById('timeSlots');
    const timeSlotId = `timeSlot_${timeSlotCounter}`;
    
    const timeSlotDiv = document.createElement('div');
    timeSlotDiv.className = 'time-slot';
    timeSlotDiv.id = timeSlotId;
    
    const days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
    let dayButtons = '';
    
    days.forEach(day => {
        const isSelected = slot && slot.days.includes(day) ? 'selected' : '';
        dayButtons += `
            <button type="button" class="day-btn ${isSelected}" data-day="${day}" data-slot="${timeSlotId}" onclick="toggleDay(this)">
                ${day.substring(0, 1)}
            </button>
        `;
    });
    
    const startTime = slot ? slot.startTime : '';
    const startAmPm = slot ? slot.startAmPm : 'AM';
    const endTime = slot ? slot.endTime : '';
    const endAmPm = slot ? slot.endAmPm : 'AM';
    
    timeSlotDiv.innerHTML = `
        <div>
            <div class="day-selector">
                ${dayButtons}
            </div>
            <div class="time-selector">
                <input type="text" class="form-control time-input" placeholder="00:00" value="${startTime}" 
                       data-slot="${timeSlotId}" data-type="start">
                <select class="am-pm-selector" data-slot="${timeSlotId}" data-type="startAmPm">
                    <option value="AM" ${startAmPm === 'AM' ? 'selected' : ''}>AM</option>
                    <option value="PM" ${startAmPm === 'PM' ? 'selected' : ''}>PM</option>
                </select>
                <span class="time-separator">-</span>
                <input type="text" class="form-control time-input" placeholder="00:00" value="${endTime}" 
                       data-slot="${timeSlotId}" data-type="end">
                <select class="am-pm-selector" data-slot="${timeSlotId}" data-type="endAmPm">
                    <option value="AM" ${endAmPm === 'AM' ? 'selected' : ''}>AM</option>
                    <option value="PM" ${endAmPm === 'PM' ? 'selected' : ''}>PM</option>
                </select>
            </div>
        </div>
        <div class="time-slot-actions">
            <button type="button" class="remove-time-slot" onclick="removeTimeSlot('${timeSlotId}')">
                <i class="fas fa-times"></i>
            </button>
        </div>
    `;
    
    timeSlots.appendChild(timeSlotDiv);
    timeSlotCounter++;
}

function toggleDay(button) {
    button.classList.toggle('selected');
}

function removeTimeSlot(slotId) {
    const timeSlots = document.getElementById('timeSlots');
    const slot = document.getElementById(slotId);
    
    // Don't remove if it's the last time slot
    if (timeSlots.children.length > 1) {
        timeSlots.removeChild(slot);
    } else {
        alert("At least one time slot is required");
    }
}

function getTimeSlotData() {
    const timeSlots = [];
    const slotDivs = document.getElementById('timeSlots').children;
    
    for (let i = 0; i < slotDivs.length; i++) {
        const slotId = slotDivs[i].id;
        const selectedDays = Array.from(slotDivs[i].querySelectorAll('.day-btn.selected'))
            .map(btn => btn.getAttribute('data-day'));
        
        const startTime = slotDivs[i].querySelector(`input[data-slot="${slotId}"][data-type="start"]`).value;
        const startAmPm = slotDivs[i].querySelector(`select[data-slot="${slotId}"][data-type="startAmPm"]`).value;
        const endTime = slotDivs[i].querySelector(`input[data-slot="${slotId}"][data-type="end"]`).value;
        const endAmPm = slotDivs[i].querySelector(`select[data-slot="${slotId}"][data-type="endAmPm"]`).value;
        
        if (selectedDays.length > 0 && startTime && endTime) {
            timeSlots.push({
                days: selectedDays,
                startTime,
                startAmPm,
                endTime,
                endAmPm
            });
        }
    }
    
    return timeSlots;
}

function formatSchedule(timeSlots) {
    if (!timeSlots || timeSlots.length === 0) {
        return "";
    }
    
    return timeSlots.map(slot => {
        const days = slot.days.map(day => day.substring(0, 1)).join('');
        return `${slot.startTime}${slot.startAmPm}-${slot.endTime}${slot.endAmPm} ${days}`;
    }).join(', ');
}

function closeClassModal() {
    document.getElementById('classModal').style.display = 'none';
}

function editClass(id) {
    const cls = classes.find(c => c.id === id);
    if (cls) {
        document.getElementById('modalTitle').innerText = 'Edit Class';
        document.getElementById('classId').value = cls.id;
        
        // Find the description option that matches
        const descOption = Array.from(document.getElementById('courseDescription').options)
            .find(option => option.text === cls.description);
        if (descOption) {
            document.getElementById('courseDescription').value = descOption.value;
        }
        
        document.getElementById('courseCode').value = cls.courseCode;
        document.getElementById('classCode').value = cls.classCode;
        document.getElementById('roomNumber').value = cls.roomNumber;
        document.getElementById('instructorSelect').value = cls.instructor;
        
        // Clear existing time slots
        document.getElementById('timeSlots').innerHTML = '';
        timeSlotCounter = 0;
        
        // Add time slots from the class
        if (cls.timeSlots && cls.timeSlots.length > 0) {
            cls.timeSlots.forEach(slot => {
                addTimeSlot(slot);
            });
        } else {
            // Add one empty time slot if none exist
            addTimeSlot();
        }
        
        document.getElementById('classModal').style.display = 'block';
    }
}

function saveClass() {
    const id = document.getElementById('classId').value;
    const courseDescription = document.getElementById('courseDescription');
    const description = courseDescription.options[courseDescription.selectedIndex].text;
    const courseCode = document.getElementById('courseCode').value;
    const classCode = document.getElementById('classCode').value;
    const roomNumber = document.getElementById('roomNumber').value;
    const instructorSelect = document.getElementById('instructorSelect');
    const instructor = instructorSelect.options[instructorSelect.selectedIndex].text;
    
    // Validate inputs
    if (!courseCode || !classCode || !roomNumber || !instructor) {
        alert("Please fill in all required fields");
        return;
    }
    
    // Get time slots data
    const timeSlots = getTimeSlotData();
    
    if (timeSlots.length === 0) {
        alert("Please add at least one time slot with days selected");
        return;
    }
    
    // Create schedule string
    const schedule = formatSchedule(timeSlots);
    
    if (id) {
        // Update existing class
        const index = classes.findIndex(c => c.id === parseInt(id));
        if (index !== -1) {
            classes[index] = {
                id: parseInt(id),
                courseCode,
                classCode,
                description,
                roomNumber,
                schedule,
                instructor,
                timeSlots
            };
        }
    } else {
        // Add new class
        const newId = classes.length > 0 ? Math.max(...classes.map(c => c.id)) + 1 : 1;
        classes.push({
            id: newId,
            courseCode,
            classCode,
            description,
            roomNumber,
            schedule,
            instructor,
            timeSlots
        });
    }
    
    // Save to localStorage
    saveClasses();
    
    renderClassTable();
    updateClassCount();
    closeClassModal();
}

function deleteClass(id) {
    classToDelete = id;
    document.getElementById('confirmationModal').style.display = 'block';
}

function confirmDelete() {
    if (classToDelete !== null) {
        classes = classes.filter(c => c.id !== classToDelete);
        // Save to localStorage
        saveClasses();
        renderClassTable();
        updateClassCount();
        closeConfirmationModal();
        classToDelete = null;
    }
}

function closeConfirmationModal() {
    document.getElementById('confirmationModal').style.display = 'none';
}