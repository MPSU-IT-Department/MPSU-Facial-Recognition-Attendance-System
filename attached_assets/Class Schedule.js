// Utility to get classes from localStorage
function getAllClasses() {
    return JSON.parse(localStorage.getItem('classes') || '[]');
}

// Utility to get students from localStorage
function getAllStudents() {
    return JSON.parse(localStorage.getItem('students') || '[]');
}

// Global variables
let currentClassId = null;
let studentToUnenroll = null;
const confirmationModal = new bootstrap.Modal(document.getElementById('confirmationModal'));

// DOM Ready
document.addEventListener('DOMContentLoaded', function() {
    // Event listeners for navigation
    document.getElementById('back-to-classes').addEventListener('click', showClassesView);
    document.getElementById('back-to-class-detail').addEventListener('click', () => {
        showClassDetailView(currentClassId);
    });
    document.getElementById('enroll-student-btn').addEventListener('click', showStudentSelectionView);
    
    // Event listeners for confirmation modal
    document.getElementById('confirm-yes').addEventListener('click', handleConfirmUnenroll);
    
    // Event delegation for dynamically created elements
    document.addEventListener('click', function(e) {
        // View class button
        if (e.target.closest('.view-class')) {
            const btn = e.target.closest('.view-class');
            const classId = btn.dataset.classId;
            showClassDetailView(classId);
        }
        
        // Unenroll button
        if (e.target.closest('.unenroll-btn')) {
            const btn = e.target.closest('.unenroll-btn');
            studentToUnenroll = {
                classId: currentClassId,
                studentId: btn.dataset.studentId
            };
            confirmationModal.show();
        }
        
        // Enroll button in student selection view
        if (e.target.closest('.enroll-btn')) {
            const btn = e.target.closest('.enroll-btn');
            enrollStudent(btn.dataset.studentId);
        }
    });
    
    // Initialize the view
    showClassesView();
});

// Show Classes View
function showClassesView() {
    document.getElementById('classes-view').classList.remove('d-none');
    document.getElementById('class-detail-view').classList.add('d-none');
    document.getElementById('student-selection-view').classList.add('d-none');
    currentClassId = null;

    // Update the number of students for each class
    const students = getAllStudents();
    const classes = getAllClasses();
    const tableBody = document.querySelector('#classes-view table tbody');
    tableBody.innerHTML = '';
    classes.forEach(classData => {
        const numStudents = students.filter(s => Array.isArray(s.enrolledClasses) && s.enrolledClasses.includes(classData.id)).length;
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${classData.description}</td>
            <td>${classData.roomNumber}</td>
            <td>${classData.schedule}</td>
            <td>${numStudents}</td>
            <td>
                <button class="btn btn-light view-class" data-class-id="${classData.id}" data-class-name="${classData.description}">
                    <i class="fas fa-eye"></i>
                </button>
            </td>
        `;
        tableBody.appendChild(row);
    });
}

// Show Class Detail View
function showClassDetailView(classId) {
    currentClassId = classId;
    const classes = getAllClasses();
    const classData = classes.find(c => c.id == classId);
    document.getElementById('class-detail-title').textContent = classData.description;

    // Get students enrolled in this class
    const students = getAllStudents().filter(s => Array.isArray(s.enrolledClasses) && s.enrolledClasses.includes(Number(classId)));
    const studentsList = document.getElementById('enrolled-students-list');
    studentsList.innerHTML = '';

    if (students.length === 0) {
        const row = document.createElement('tr');
        row.innerHTML = '<td colspan="5" class="text-center">No students enrolled</td>';
        studentsList.appendChild(row);
    } else {
        students.forEach(student => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${student.firstName} ${student.lastName}</td>
                <td>${student.id}</td>
                <td>${student.yearLevel}</td>
                <td>${student.phone}</td>
                <td>
                    <button class="btn btn-danger unenroll-btn" data-student-id="${student.id}">
                        Unenroll
                    </button>
                </td>
            `;
            studentsList.appendChild(row);
        });
    }

    document.getElementById('classes-view').classList.add('d-none');
    document.getElementById('class-detail-view').classList.remove('d-none');
    document.getElementById('student-selection-view').classList.add('d-none');
}

// Show Student Selection View
function showStudentSelectionView() {
    const students = getAllStudents();
    const enrolledStudentIds = students.filter(s => Array.isArray(s.enrolledClasses) && s.enrolledClasses.includes(Number(currentClassId))).map(s => s.id);
    const studentsList = document.getElementById('all-students-list');
    studentsList.innerHTML = '';

    students.forEach(student => {
        const isEnrolled = Array.isArray(student.enrolledClasses) && student.enrolledClasses.includes(Number(currentClassId));
        const row = document.createElement('tr');
        row.innerHTML = `
            <td>${student.firstName} ${student.lastName}</td>
            <td>${student.id}</td>
            <td>${student.yearLevel}</td>
            <td>${student.phone}</td>
            <td>
                ${isEnrolled ? 
                    '<button class="btn btn-secondary" disabled>Enrolled</button>' :
                    `<button class="btn btn-success enroll-btn" data-student-id="${student.id}">Enroll</button>`
                }
            </td>
        `;
        studentsList.appendChild(row);
    });

    document.getElementById('classes-view').classList.add('d-none');
    document.getElementById('class-detail-view').classList.add('d-none');
    document.getElementById('student-selection-view').classList.remove('d-none');
}

// Handle confirmation of unenrolling a student
function handleConfirmUnenroll() {
    if (studentToUnenroll) {
        // Remove class from student's enrolledClasses
        const students = getAllStudents();
        const student = students.find(s => s.id === studentToUnenroll.studentId);
        if (student && Array.isArray(student.enrolledClasses)) {
            student.enrolledClasses = student.enrolledClasses.filter(cid => cid !== Number(studentToUnenroll.classId));
            localStorage.setItem('students', JSON.stringify(students));
        }
        confirmationModal.hide();
        showClassDetailView(studentToUnenroll.classId);
        studentToUnenroll = null;
    }
}

// Enroll a student to the current class
function enrollStudent(studentId) {
    const students = getAllStudents();
    const student = students.find(s => s.id === studentId);
    if (student) {
        if (!Array.isArray(student.enrolledClasses)) student.enrolledClasses = [];
        if (!student.enrolledClasses.includes(Number(currentClassId))) {
            student.enrolledClasses.push(Number(currentClassId));
            localStorage.setItem('students', JSON.stringify(students));
        }
    }
    showStudentSelectionView();
}