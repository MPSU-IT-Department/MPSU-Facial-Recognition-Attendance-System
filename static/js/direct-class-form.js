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
        
        // Use a single click handler to prevent multiple alerts
        addTimeBtn.addEventListener('click', handleAddTimeClick);
    }
    
    // Set up day button handlers if needed
    setupDayButtonHandlers();
    
    // Reset days button
    const resetDaysBtn = document.getElementById('resetDaysBtn');
    if (resetDaysBtn) {
        resetDaysBtn.addEventListener('click', function(e) {
            e.preventDefault(); // Prevent form submission
            resetSelectedDays();
        });
    }
});

/**
 * Handle the add time button click
 */
function handleAddTimeClick() {
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
    
    // Validate time range
    if (startTime >= endTime) {
        alert('End time must be after start time');
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
        // Show success notification
        showNotification('Time slot added successfully!');
    } else {
        // Fallback if the main function isn't available
        addTimeSlotFallback(slot);
        // Show success notification
        showNotification('Time slot added successfully!');
    }
    
    // Update the hidden schedule field with the new format
    const scheduleField = document.getElementById('schedule');
    if (scheduleField) {
        // Set a default value for the schedule even if there are no slots
        if (!scheduleField.value) {
            const currentDays = selectedDays.join('');
            scheduleField.value = `${currentDays} ${formatTime(startTime)} - ${formatTime(endTime)}`;
        }
    }
    
    // Reset inputs but keep the times for convenience
    resetSelectedDays();
}

/**
 * Get the currently selected days
 * @returns {Array} Array of selected day codes
 */
function getSelectedDays() {
    const selectedDays = [];
    const dayCheckboxes = document.querySelectorAll('.day-checkbox:checked');
    dayCheckboxes.forEach(checkbox => {
        selectedDays.push(checkbox.getAttribute('data-day'));
    });
    return selectedDays;
}

/**
 * Reset the selected days
 */
function resetSelectedDays() {
    const dayCheckboxes = document.querySelectorAll('.day-checkbox');
    dayCheckboxes.forEach(checkbox => {
        checkbox.checked = false;
    });
    console.log('Days reset');
}

/**
 * Set up day button handlers
 */
function setupDayButtonHandlers() {
    // Initialize the reset days button
    const resetDaysBtn = document.getElementById('resetDaysBtn');
    if (resetDaysBtn) {
        resetDaysBtn.addEventListener('click', resetSelectedDays);
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

/**
 * Show a notification message that fades out
 * @param {string} message - The message to display
 * @param {string} type - The notification type ('success', 'error', 'info')
 */
function showNotification(message, type = 'success') {
    // Check if notification container exists, if not create it
    let notificationContainer = document.getElementById('notification-container');
    
    if (!notificationContainer) {
        // Create notification container
        notificationContainer = document.createElement('div');
        notificationContainer.id = 'notification-container';
        notificationContainer.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
        `;
        document.body.appendChild(notificationContainer);
    }
    
    // Create notification element
    const notification = document.createElement('div');
    notification.className = `notification notification-${type}`;
    notification.textContent = message;
    
    // Add styles to the notification
    notification.style.cssText = `
        background-color: ${type === 'success' ? '#17ce9a' : type === 'error' ? '#dc3545' : '#17a2b8'};
        color: white;
        padding: 12px 20px;
        margin-bottom: 10px;
        border-radius: 4px;
        box-shadow: 0 2px 5px rgba(0, 0, 0, 0.2);
        opacity: 0;
        transition: opacity 0.3s ease-in-out;
    `;
    
    // Add notification to container
    notificationContainer.appendChild(notification);
    
    // Fade in the notification
    setTimeout(() => {
        notification.style.opacity = '1';
    }, 10);
    
    // Remove notification after 3 seconds
    setTimeout(() => {
        notification.style.opacity = '0';
        
        // Remove element after fade out
        setTimeout(() => {
            notificationContainer.removeChild(notification);
            
            // Remove container if empty
            if (notificationContainer.children.length === 0) {
                document.body.removeChild(notificationContainer);
            }
        }, 300);
    }, 3000);
}