/**
 * Direct Class Form Handler
 * Handles adding time slots to the schedule builder without relying on the main classes.js
 */

document.addEventListener('DOMContentLoaded', function() {
    console.log('Direct class form handler initialized');
    
    // Set up the add time button handler if it exists
    const addTimeBtn = document.getElementById('addTimeBtn');
    if (addTimeBtn) {
        console.log('Add time button handler set up');
        
        addTimeBtn.addEventListener('click', function() {
            const startTime = document.getElementById('startTime').value;
            const endTime = document.getElementById('endTime').value;
            const selectedDays = getSelectedDays();
            
            // Validation
            if (!startTime || !endTime) {
                alert('Please select both start and end times');
                return;
            }
            
            if (selectedDays.length === 0) {
                alert('Please select at least one day');
                return;
            }
            
            // Generate a unique ID for this slot
            const slotId = 'slot_' + new Date().getTime();
            
            // Create a new time slot object
            const slot = {
                id: slotId,
                days: selectedDays,
                startTime: startTime,
                endTime: endTime
            };
            
            // Add the time slot to the schedule
            if (typeof addTimeSlot === 'function') {
                addTimeSlot(slot);
            } else {
                // Fallback if the main function isn't available
                addTimeSlotFallback(slot);
            }
            
            // Reset inputs
            document.getElementById('startTime').value = '';
            document.getElementById('endTime').value = '';
            resetSelectedDays();
        });
    }
    
    // Set up day button click handlers if the schedule builder functions aren't available
    setupDayButtonHandlers();
    
    // Reset days button
    const resetDaysBtn = document.getElementById('resetDaysBtn');
    if (resetDaysBtn) {
        resetDaysBtn.addEventListener('click', resetSelectedDays);
    }
});

/**
 * Get the currently selected days
 * @returns {Array} Array of selected day codes
 */
function getSelectedDays() {
    const selectedDays = [];
    const dayButtons = document.querySelectorAll('.day-btn.active');
    dayButtons.forEach(button => {
        selectedDays.push(button.dataset.day);
    });
    return selectedDays;
}

/**
 * Reset the selected days
 */
function resetSelectedDays() {
    const dayButtons = document.querySelectorAll('.day-btn');
    dayButtons.forEach(button => {
        button.classList.remove('active');
    });
}

/**
 * Set up day button handlers if the main toggle function isn't available
 */
function setupDayButtonHandlers() {
    if (typeof toggleDay !== 'function') {
        const dayButtons = document.querySelectorAll('.day-btn');
        dayButtons.forEach(button => {
            button.addEventListener('click', function() {
                this.classList.toggle('active');
            });
        });
    }
}

/**
 * Fallback function to add a time slot if the main one isn't available
 * @param {Object} slot - Time slot to add
 */
function addTimeSlotFallback(slot) {
    const scheduleDisplay = document.getElementById('scheduleDisplay');
    const scheduleField = document.getElementById('schedule');
    
    if (!scheduleDisplay || !scheduleField) return;
    
    // Clear the "No schedule set" message if it exists
    if (scheduleDisplay.querySelector('.text-muted')) {
        scheduleDisplay.innerHTML = '';
    }
    
    // Create a new slot element
    const slotElement = document.createElement('div');
    slotElement.className = 'schedule-slot';
    slotElement.dataset.slotId = slot.id;
    
    // Format time for display
    const formattedStartTime = formatTime(slot.startTime);
    const formattedEndTime = formatTime(slot.endTime);
    
    slotElement.innerHTML = `
        <span class="days">${slot.days.join(', ')}</span>
        <span class="time">${formattedStartTime} - ${formattedEndTime}</span>
        <button type="button" class="btn-remove-slot">
            <i class="fas fa-times"></i>
        </button>
    `;
    
    scheduleDisplay.appendChild(slotElement);
    
    // Add remove button handler
    const removeButton = slotElement.querySelector('.btn-remove-slot');
    removeButton.addEventListener('click', function() {
        slotElement.remove();
        updateScheduleField();
    });
    
    // Update the hidden schedule field
    updateScheduleField();
}

/**
 * Update the hidden schedule field with the current slots
 */
function updateScheduleField() {
    const scheduleDisplay = document.getElementById('scheduleDisplay');
    const scheduleField = document.getElementById('schedule');
    
    if (!scheduleDisplay || !scheduleField) return;
    
    // Get all slots
    const slots = scheduleDisplay.querySelectorAll('.schedule-slot');
    
    if (slots.length === 0) {
        scheduleDisplay.innerHTML = '<span class="text-muted">No schedule set</span>';
        scheduleField.value = '';
        return;
    }
    
    // Build the schedule string
    let scheduleString = '';
    
    slots.forEach((slot, index) => {
        const days = slot.querySelector('.days').textContent;
        const time = slot.querySelector('.time').textContent;
        
        scheduleString += `${days.replace(/,\s*/g, '')} ${time}`;
        
        if (index < slots.length - 1) {
            scheduleString += ', ';
        }
    });
    
    scheduleField.value = scheduleString;
}

/**
 * Format a time string for display
 * @param {string} timeString - Time in HH:MM format
 * @returns {string} Formatted time (12-hour format with AM/PM)
 */
function formatTime(timeString) {
    if (!timeString) return '';
    
    // Convert 24 hour time to 12 hour format with AM/PM
    const [hours, minutes] = timeString.split(':');
    const hour = parseInt(hours, 10);
    const suffix = hour >= 12 ? 'PM' : 'AM';
    const displayHour = hour % 12 === 0 ? 12 : hour % 12;
    
    return `${displayHour}:${minutes} ${suffix}`;
}