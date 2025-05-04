/**
 * Schedule Builder
 * Handles building and parsing class schedules
 * Integrates with the class form to handle the schedule field
 */

// Wait for the DOM to be fully loaded
document.addEventListener('DOMContentLoaded', () => {
    // Set up the schedule builder if it exists on the page
    setupScheduleBuilder();
});

// Global variables to store schedule state
let timeSlots = [];
let selectedDays = new Set();
let timeSlotCounter = 0;

/**
 * Setup the schedule builder interface
 * @param {string} existingSchedule - Optional existing schedule to parse and display
 */
function setupScheduleBuilder(existingSchedule = null) {
    console.log('Setting up schedule builder...');
    
    // DOM element references
    const dayButtons = document.querySelectorAll('.day-btn');
    const resetDaysBtn = document.getElementById('resetDaysBtn');
    const addTimeBtn = document.getElementById('addTimeBtn');
    const scheduleDisplay = document.getElementById('scheduleDisplay');
    const startTimeInput = document.getElementById('startTime');
    const endTimeInput = document.getElementById('endTime');
    const scheduleField = document.getElementById('schedule');
    
    // Reset state
    timeSlots = [];
    selectedDays = new Set();
    timeSlotCounter = 0;
    
    // If these elements don't exist, we're not on a page with the schedule builder
    if (!dayButtons.length || !resetDaysBtn || !addTimeBtn || !scheduleDisplay || 
        !startTimeInput || !endTimeInput || !scheduleField) {
        console.log('Schedule builder elements not found on this page');
        return;
    }
    
    // Set up event listeners for day buttons
    dayButtons.forEach(button => {
        button.addEventListener('click', () => {
            toggleDay(button);
        });
    });
    
    // Reset days button
    resetDaysBtn.addEventListener('click', () => {
        dayButtons.forEach(btn => {
            btn.classList.remove('active');
            selectedDays.clear();
        });
    });
    
    // Add time slot button
    addTimeBtn.addEventListener('click', () => {
        const startTime = startTimeInput.value;
        const endTime = endTimeInput.value;
        
        // Validation
        if (!startTime || !endTime) {
            alert('Please select both start and end times');
            return;
        }
        
        if (selectedDays.size === 0) {
            alert('Please select at least one day');
            return;
        }
        
        // Add the time slot
        addTimeSlot({
            id: `slot_${timeSlotCounter++}`,
            days: Array.from(selectedDays),
            startTime: startTime,
            endTime: endTime
        });
        
        // Reset inputs
        startTimeInput.value = '';
        endTimeInput.value = '';
        dayButtons.forEach(btn => {
            btn.classList.remove('active');
        });
        selectedDays.clear();
    });
    
    // Parse existing schedule if provided
    if (existingSchedule) {
        parseExistingSchedule(existingSchedule);
    } else {
        updateScheduleDisplay();
    }
}

/**
 * Toggle a day in the UI and selected days set
 * @param {HTMLElement} button - The day button element
 */
function toggleDay(button) {
    const day = button.dataset.day;
    
    if (button.classList.contains('active')) {
        button.classList.remove('active');
        selectedDays.delete(day);
    } else {
        button.classList.add('active');
        selectedDays.add(day);
    }
}

/**
 * Add a time slot to the schedule
 * @param {Object} slot - Time slot with days, start time, and end time
 */
function addTimeSlot(slot) {
    timeSlots.push(slot);
    updateScheduleDisplay();
}

/**
 * Remove a time slot from the schedule
 * @param {string} slotId - The ID of the slot to remove
 */
function removeTimeSlot(slotId) {
    timeSlots = timeSlots.filter(slot => slot.id !== slotId);
    updateScheduleDisplay();
}

/**
 * Update the schedule display in the UI
 */
function updateScheduleDisplay() {
    const scheduleDisplay = document.getElementById('scheduleDisplay');
    const scheduleField = document.getElementById('schedule');
    
    if (!scheduleDisplay || !scheduleField) return;
    
    if (timeSlots.length === 0) {
        scheduleDisplay.innerHTML = '<span class="text-muted">No schedule set</span>';
        scheduleField.value = '';
        return;
    }
    
    // Create the schedule display
    scheduleDisplay.innerHTML = '';
    
    timeSlots.forEach(slot => {
        const slotElement = document.createElement('div');
        slotElement.className = 'schedule-slot';
        slotElement.innerHTML = `
            <span class="days">${slot.days.join(', ')}</span>
            <span class="time">${formatTime(slot.startTime)} - ${formatTime(slot.endTime)}</span>
            <button type="button" class="btn-remove-slot" data-slot-id="${slot.id}">
                <i class="fas fa-times"></i>
            </button>
        `;
        
        scheduleDisplay.appendChild(slotElement);
        
        // Add event listener for remove button
        const removeButton = slotElement.querySelector('.btn-remove-slot');
        removeButton.addEventListener('click', () => {
            removeTimeSlot(slot.id);
        });
    });
    
    // Update the hidden input field with formatted schedule
    scheduleField.value = formatSchedule();
    console.log('Schedule updated:', scheduleField.value);
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
 * Format the schedule for storage
 * @returns {string} Formatted schedule string
 */
function formatSchedule() {
    if (timeSlots.length === 0) return '';
    
    // Format each time slot and join with commas
    return timeSlots.map(slot => {
        const days = slot.days.join('');
        return `${days} ${formatTime(slot.startTime)}-${formatTime(slot.endTime)}`;
    }).join(', ');
}

/**
 * Parse an existing schedule string and set up the UI
 * @param {string} scheduleString - Schedule in the format 'M 9:00 AM-10:30 AM, W 1:00 PM-2:30 PM'
 */
function parseExistingSchedule(scheduleString) {
    if (!scheduleString) return;
    
    console.log('Parsing existing schedule:', scheduleString);
    
    // Reset timeSlots
    timeSlots = [];
    
    // Split by commas to get individual slots
    const slots = scheduleString.split(',').map(s => s.trim());
    
    slots.forEach((slot, index) => {
        try {
            // Match pattern: 'M 9:00 AM-10:30 AM' or 'MWF 9:00 AM-10:30 AM'
            const parts = slot.match(/([A-Za-z]+)\s+(.*?)\s*-\s*(.*)/);
            
            if (parts && parts.length === 4) {
                const dayString = parts[1];
                const startTimeStr = parts[2];
                const endTimeStr = parts[3];
                
                // Parse days - each character is a day
                const days = [];
                for (let i = 0; i < dayString.length; i++) {
                    days.push(dayString[i]);
                }
                
                // Parse times - convert from 12-hour to 24-hour format
                const startTime = parse12HourTime(startTimeStr);
                const endTime = parse12HourTime(endTimeStr);
                
                if (startTime && endTime) {
                    addTimeSlot({
                        id: `slot_${timeSlotCounter++}`,
                        days: days,
                        startTime: startTime,
                        endTime: endTime
                    });
                }
            }
        } catch (error) {
            console.error(`Error parsing schedule slot: ${slot}`, error);
        }
    });
    
    // Update the UI
    updateScheduleDisplay();
}

/**
 * Parse a 12-hour time format string to 24-hour format
 * @param {string} timeStr - Time in 12-hour format (e.g., '9:00 AM')
 * @returns {string} Time in 24-hour format (e.g., '09:00')
 */
function parse12HourTime(timeStr) {
    try {
        timeStr = timeStr.trim();
        
        // Check if it has AM/PM
        const isAM = timeStr.toUpperCase().includes('AM');
        const isPM = timeStr.toUpperCase().includes('PM');
        
        // Remove the AM/PM
        timeStr = timeStr.replace(/AM|PM|am|pm/g, '').trim();
        
        // Split into hours and minutes
        let [hours, minutes] = timeStr.split(':').map(part => part.trim());
        hours = parseInt(hours, 10);
        
        // Convert to 24-hour format
        if (isPM && hours < 12) {
            hours += 12;
        } else if (isAM && hours === 12) {
            hours = 0;
        }
        
        // Format with leading zeros
        return `${hours.toString().padStart(2, '0')}:${minutes}`;
    } catch (error) {
        console.error('Error parsing time:', timeStr, error);
        return '';
    }
}

// Make the setup function available globally
window.setupScheduleBuilder = setupScheduleBuilder;