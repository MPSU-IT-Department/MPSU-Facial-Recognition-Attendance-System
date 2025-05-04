/**
 * Direct Class Form Handler
 * This script handles the class form submission and schedule building
 * independently of the main application.
 */

// Wait for DOM to be fully loaded
document.addEventListener('DOMContentLoaded', function() {
    console.log('Direct class form handler initialized');
    
    // Set up the day button click handlers
    setupDayButtons();
    
    // Set up the Add time slot button
    setupAddTimeButton();
    
    // Set up the form submission handler
    setupFormSubmission();
    
    // Set up the course selection handler
    setupCourseSelection();
});

// Set up the day buttons
function setupDayButtons() {
    const dayButtons = document.querySelectorAll('.day-btn');
    dayButtons.forEach(button => {
        button.addEventListener('click', function() {
            this.classList.toggle('active');
            const day = this.dataset.day;
            const isActive = this.classList.contains('active');
            console.log(`Day button clicked: ${day}, Active: ${isActive}`);
        });
    });
    
    // Reset days button
    const resetDaysBtn = document.getElementById('resetDaysBtn');
    if (resetDaysBtn) {
        resetDaysBtn.addEventListener('click', function() {
            document.querySelectorAll('.day-btn.active').forEach(btn => {
                btn.classList.remove('active');
            });
            console.log('Days reset');
        });
    }
}

// Set up the Add time slot button
function setupAddTimeButton() {
    const addTimeBtn = document.getElementById('addTimeBtn');
    if (addTimeBtn) {
        addTimeBtn.addEventListener('click', function(e) {
            e.preventDefault();
            addScheduleTimeSlot();
        });
        console.log('Add time button handler set up');
    }
}

// Add a schedule time slot
function addScheduleTimeSlot() {
    console.log('Adding schedule time slot');
    
    // Get selected days
    const selectedDayButtons = document.querySelectorAll('.day-btn.active');
    const selectedDays = Array.from(selectedDayButtons).map(btn => btn.dataset.day);
    
    if (selectedDays.length === 0) {
        alert('Please select at least one day');
        return;
    }
    
    // Get times
    const startTime = document.getElementById('startTime').value;
    const endTime = document.getElementById('endTime').value;
    
    if (!startTime || !endTime) {
        alert('Please select start and end times');
        return;
    }
    
    if (startTime >= endTime) {
        alert('End time must be after start time');
        return;
    }
    
    // Format time for display (12-hour format)
    const startDisplay = formatTimeFor12Hour(startTime);
    const endDisplay = formatTimeFor12Hour(endTime);
    const displayText = `${selectedDays.join('')} ${startDisplay}-${endDisplay}`;
    
    console.log('Created schedule display text:', displayText);
    
    // Update the schedule display
    const scheduleDisplay = document.getElementById('scheduleDisplay');
    if (scheduleDisplay) {
        // Clear the "No schedule set" message if present
        if (scheduleDisplay.querySelector('.text-muted')) {
            scheduleDisplay.innerHTML = '';
        }
        
        // Create the tag element
        const tag = document.createElement('div');
        tag.className = 'schedule-tag';
        tag.innerHTML = `${displayText}<span class="remove-schedule" data-index="${Date.now()}">&times;</span>`;
        scheduleDisplay.appendChild(tag);
        
        // Add event listener to the remove button
        const removeBtn = tag.querySelector('.remove-schedule');
        if (removeBtn) {
            removeBtn.addEventListener('click', function() {
                tag.remove();
                updateScheduleInput();
                
                // If no schedule tags left, show "No schedule set" message
                if (scheduleDisplay.children.length === 0) {
                    scheduleDisplay.innerHTML = '<span class="text-muted">No schedule set</span>';
                }
            });
        }
    }
    
    // Update the hidden input
    updateScheduleInput();
    
    // Clear time inputs for next entry
    document.getElementById('startTime').value = '';
    document.getElementById('endTime').value = '';
}

// Update the hidden schedule input
function updateScheduleInput() {
    const scheduleDisplay = document.getElementById('scheduleDisplay');
    const scheduleInput = document.getElementById('schedule');
    
    if (scheduleDisplay && scheduleInput) {
        const scheduleTags = scheduleDisplay.querySelectorAll('.schedule-tag');
        
        if (scheduleTags.length > 0) {
            const scheduleTexts = Array.from(scheduleTags).map(tag => {
                // Clone to safely remove the "×" button
                const clone = tag.cloneNode(true);
                const removeBtn = clone.querySelector('.remove-schedule');
                if (removeBtn) removeBtn.remove();
                return clone.textContent.trim();
            });
            
            // Join the schedule texts with commas
            scheduleInput.value = scheduleTexts.join(', ');
            console.log('Updated schedule input:', scheduleInput.value);
        } else {
            scheduleInput.value = '';
        }
    }
}

// Format time string for 12-hour display
function formatTimeFor12Hour(timeStr) {
    try {
        const [hours, minutes] = timeStr.split(':');
        const hour = parseInt(hours, 10);
        const ampm = hour >= 12 ? 'PM' : 'AM';
        const hour12 = hour % 12 || 12; // Convert 0 to 12 for 12 AM
        return `${hour12}:${minutes} ${ampm}`;
    } catch (e) {
        console.error('Error formatting time:', e);
        return timeStr;
    }
}

// Set up the form submission handler
function setupFormSubmission() {
    const classForm = document.getElementById('class-form');
    if (classForm) {
        classForm.addEventListener('submit', function(e) {
            e.preventDefault();
            console.log('Form submission intercepted');
            
            // Validate the form
            if (validateForm()) {
                // Submit the form via AJAX
                submitForm();
            }
            
            return false;
        });
    }
}

// Validate the form
function validateForm() {
    console.log('Validating form');
    
    // Get form fields
    const classCodeInput = document.getElementById('classCode');
    const roomNumberInput = document.getElementById('roomNumber');
    const scheduleInput = document.getElementById('schedule');
    const instructorIdInput = document.getElementById('instructorId');
    
    // Check class code
    if (!classCodeInput || !classCodeInput.value.trim()) {
        alert('Please enter a class code');
        return false;
    }
    
    // Check room number
    if (!roomNumberInput || !roomNumberInput.value.trim()) {
        alert('Please enter a room number');
        return false;
    }
    
    // Check schedule
    if (!scheduleInput || !scheduleInput.value.trim()) {
        alert('Please add at least one schedule time slot');
        return false;
    }
    
    // Check instructor
    if (!instructorIdInput || !instructorIdInput.value) {
        alert('Please select an instructor');
        return false;
    }
    
    // Ensure the schedule is properly formatted
    updateScheduleInput();
    
    return true;
}

// Submit the form via AJAX
function submitForm() {
    console.log('Submitting form');
    
    // Get form data
    const classId = document.getElementById('classId').value;
    const classCode = document.getElementById('classCode').value;
    const description = document.getElementById('description').value;
    const roomNumber = document.getElementById('roomNumber').value;
    const schedule = document.getElementById('schedule').value;
    const instructorId = parseInt(document.getElementById('instructorId').value);
    
    // Create the data object
    const classData = {
        classCode: classCode,
        description: description,
        roomNumber: roomNumber,
        schedule: schedule,
        instructorId: instructorId
    };
    
    console.log('Class data being submitted:', classData);
    
    // Determine if creating new or updating existing
    const isEditing = classId && classId.trim() !== '';
    const url = isEditing ? `/classes/api/update/${classId}` : '/classes/api/create';
    const method = isEditing ? 'PUT' : 'POST';
    
    // Send the AJAX request
    fetch(url, {
        method: method,
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify(classData)
    })
    .then(response => {
        if (!response.ok) {
            throw new Error(`HTTP error! Status: ${response.status}`);
        }
        return response.json();
    })
    .then(data => {
        console.log('Response received:', data);
        
        if (data.success) {
            // Show success message
            alert('Class saved successfully!');
            
            // Close the modal
            const modal = document.getElementById('class-modal');
            if (modal) {
                modal.style.display = 'none';
                document.body.classList.remove('modal-open');
            }
            
            // Reload the page after a short delay
            setTimeout(() => {
                window.location.reload();
            }, 500);
        } else {
            // Show error message
            alert('Error: ' + (data.message || 'Failed to save class'));
        }
    })
    .catch(error => {
        console.error('Error saving class:', error);
        alert('An error occurred while saving the class. Please try again.');
    });
}

// Set up course selection handler
function setupCourseSelection() {
    const courseSelect = document.getElementById('course');
    if (courseSelect) {
        courseSelect.addEventListener('change', function() {
            const selectedValue = this.value;
            
            if (!selectedValue) {
                document.getElementById('classCode').value = '';
                document.getElementById('description').value = '';
                return;
            }
            
            try {
                const courseData = JSON.parse(selectedValue);
                
                // Set description
                document.getElementById('description').value = courseData.description;
                
                // Auto-generate a suggested class code (course code + section)
                const classCodeInput = document.getElementById('classCode');
                // Format as CourseCode-Section (e.g., "ITP321-A")
                classCodeInput.value = courseData.code + "-A";
                
                console.log('Course selected:', courseData);
            } catch (error) {
                console.error('Error parsing course data:', error);
            }
        });
    }
}