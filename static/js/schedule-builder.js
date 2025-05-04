/**
 * Schedule Builder JS
 * Manages day selection, time slots, and generates formatted schedules
 */
document.addEventListener('DOMContentLoaded', function() {
    // Elements
    const dayButtons = document.querySelectorAll('.day-btn');
    const startTimeInput = document.getElementById('startTime');
    const endTimeInput = document.getElementById('endTime');
    const addTimeBtn = document.getElementById('addTimeBtn');
    const scheduleDisplay = document.getElementById('scheduleDisplay');
    const scheduleInput = document.getElementById('schedule');
    
    // State
    let scheduleItems = [];
    
    // Initialize - check if this is an edit with existing schedule
    function initScheduleBuilder() {
        const existingSchedule = scheduleInput.value;
        if (existingSchedule) {
            parseExistingSchedule(existingSchedule);
        }
    }
    
    // Parse existing schedule (e.g. "MWF 9:00-10:30 AM, TTh 1:00-2:30 PM")
    function parseExistingSchedule(scheduleStr) {
        // Clear any existing items
        scheduleItems = [];
        
        // Split by comma to get different day groups
        const scheduleGroups = scheduleStr.split(',').map(s => s.trim());
        
        scheduleGroups.forEach(group => {
            // Extract days and time range
            const match = group.match(/^([A-Za-z]+)\s+(\d+:\d+(?:\s*[AP]M)?)-(\d+:\d+(?:\s*[AP]M)?)$/);
            if (match) {
                const [_, days, startTimeStr, endTimeStr] = match;
                
                // Convert to 24-hour format for the inputs
                const startTime = convertTimeStringTo24Hour(startTimeStr);
                const endTime = convertTimeStringTo24Hour(endTimeStr);
                
                // Add schedule item
                scheduleItems.push({
                    days: days.split(''),  // Convert string to array of day characters
                    startTime,
                    endTime,
                    display: group
                });
            }
        });
        
        // Update display
        updateScheduleDisplay();
    }
    
    // Convert AM/PM time to 24-hour format
    function convertTimeStringTo24Hour(timeStr) {
        // Handle different formats
        let time = timeStr.trim();
        let hours, minutes;
        
        // Check if AM/PM is in the string
        if (time.match(/[AP]M$/i)) {
            // Parse 12-hour format
            const timeMatch = time.match(/(\d+):(\d+)\s*([AP]M)/i);
            if (timeMatch) {
                hours = parseInt(timeMatch[1], 10);
                minutes = parseInt(timeMatch[2], 10);
                const period = timeMatch[3].toUpperCase();
                
                // Convert to 24-hour
                if (period === 'PM' && hours < 12) {
                    hours += 12;
                } else if (period === 'AM' && hours === 12) {
                    hours = 0;
                }
            }
        } else {
            // Parse 24-hour format or just hours:minutes
            const timeMatch = time.match(/(\d+):(\d+)/);
            if (timeMatch) {
                hours = parseInt(timeMatch[1], 10);
                minutes = parseInt(timeMatch[2], 10);
            }
        }
        
        // Format as HH:MM
        return hours.toString().padStart(2, '0') + ':' + minutes.toString().padStart(2, '0');
    }
    
    // Convert 24-hour time to 12-hour AM/PM format
    function formatTimeFor12Hour(time) {
        if (!time) return '';
        
        const [hours, minutes] = time.split(':').map(Number);
        let period = 'AM';
        let hour = hours;
        
        if (hours >= 12) {
            period = 'PM';
            hour = hours === 12 ? 12 : hours - 12;
        }
        
        if (hours === 0) {
            hour = 12;
        }
        
        return `${hour}:${minutes.toString().padStart(2, '0')} ${period}`;
    }
    
    // Toggle day selection
    dayButtons.forEach(btn => {
        btn.addEventListener('click', function() {
            this.classList.toggle('active');
        });
    });
    
    // Add time slot button click
    if (addTimeBtn) {
        addTimeBtn.addEventListener('click', addTimeSlot);
    }
    
    // Add a time slot
    function addTimeSlot() {
        // Get selected days
        const selectedDays = Array.from(document.querySelectorAll('.day-btn.active'))
            .map(btn => btn.dataset.day);
        
        if (selectedDays.length === 0) {
            alert('Please select at least one day');
            return;
        }
        
        // Get times
        const startTime = startTimeInput.value;
        const endTime = endTimeInput.value;
        
        if (!startTime || !endTime) {
            alert('Please select start and end times');
            return;
        }
        
        if (startTime >= endTime) {
            alert('End time must be after start time');
            return;
        }
        
        // Format for display (12-hour format)
        const startDisplay = formatTimeFor12Hour(startTime);
        const endDisplay = formatTimeFor12Hour(endTime);
        const display = `${selectedDays.join('')} ${startDisplay}-${endDisplay}`;
        
        // Add to schedule items
        scheduleItems.push({
            days: selectedDays,
            startTime,
            endTime,
            display
        });
        
        // Update display
        updateScheduleDisplay();
        
        // Only clear time inputs, but keep the selected days
        // This allows adding multiple time slots for the same days
        startTimeInput.value = '';
        endTimeInput.value = '';
    }
    
    // Update the schedule display
    function updateScheduleDisplay() {
        if (scheduleItems.length === 0) {
            scheduleDisplay.innerHTML = '<span class="text-muted">No schedule set</span>';
            scheduleInput.value = '';
            return;
        }
        
        // Clear the display
        scheduleDisplay.innerHTML = '';
        
        // Create HTML and set hidden input value
        let formattedSchedule = [];
        
        scheduleItems.forEach((item, index) => {
            formattedSchedule.push(item.display);
            
            // Create tag
            const tag = document.createElement('div');
            tag.className = 'schedule-tag';
            tag.innerHTML = `
                ${item.display}
                <span class="remove-schedule" data-index="${index}">&times;</span>
            `;
            scheduleDisplay.appendChild(tag);
        });
        
        // Set hidden input value
        scheduleInput.value = formattedSchedule.join(', ');
    }
    
    // Remove a schedule item
    document.addEventListener('click', function(e) {
        if (e.target.classList.contains('remove-schedule')) {
            const index = parseInt(e.target.dataset.index, 10);
            scheduleItems.splice(index, 1);
            updateScheduleDisplay();
        }
    });
    
    // Reset inputs after adding a schedule
    function resetInputs() {
        // Clear day selection
        document.querySelectorAll('.day-btn.active').forEach(btn => {
            btn.classList.remove('active');
        });
        
        // Clear time inputs
        startTimeInput.value = '';
        endTimeInput.value = '';
    }
    
    // Reset only time inputs, keeping selected days
    function resetTimeInputs() {
        startTimeInput.value = '';
        endTimeInput.value = '';
    }
    
    // Add event listener for the Reset Days button
    const resetDaysBtn = document.getElementById('resetDaysBtn');
    if (resetDaysBtn) {
        resetDaysBtn.addEventListener('click', function() {
            document.querySelectorAll('.day-btn.active').forEach(btn => {
                btn.classList.remove('active');
            });
        });
    }
    
    // Initialize on load
    initScheduleBuilder();
    
    // When editing a class, this function will be called to set up the schedule builder
    window.setupScheduleBuilder = function(scheduleString) {
        scheduleInput.value = scheduleString;
        parseExistingSchedule(scheduleString);
    };
});